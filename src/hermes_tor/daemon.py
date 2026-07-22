"""Tor daemon lifecycle manager.

Manages a Tor subprocess with user-provided bridge configuration,
lyrebird (obfs4proxy successor) pluggable transports, and SOCKS5 proxy.

Key design decisions:
  - Lyrebird path is ABSOLUTE — raw tor.exe doesn't understand
    Tor Browser's ${pt_path} variable.
  - GeoIP files are required (bundled in Expert Bundle).
  - Bootstrap detection uses a background thread to read stdout
    because select.select() only works on sockets on Windows.
  - Process management uses terminate() on Windows, SIGINT on Linux.
"""
import logging
import os
import queue
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from hermes_tor.constants import (
    DEFAULT_SOCKS_PORT,
    DEFAULT_CONTROL_PORT,
    TOR_DATA_DIR,
    TOR_BINARY_DIR,
    get_lyrebird_path,
    get_geoip_paths,
)
from hermes_tor.bridges import Bridge

from hermes_tor.privacy import get_logger

logger = get_logger(__name__)

# Template with absolute paths filled at generation time.
# No ${pt_path} — we resolve paths ourselves.
TORRC_TEMPLATE = """\
# hermes-tor generated torrc — {generated_at}
# DO NOT EDIT MANUALLY — regenerated on each start.

SOCKSPort {socks_port}
ControlPort {control_port}
DataDirectory {data_dir}
Log notice stdout
RunAsDaemon 0
AvoidDiskWrites 1
CookieAuthentication 0
GeoIPFile {geoip_path}
GeoIPv6File {geoip6_path}

# Pluggable transports — lyrebird handles obfs2/3/4, meek, snowflake, scramblesuit, webtunnel
{transport_plugins}

# User-provided bridges
{bridge_section}
"""


class TorDaemonError(Exception):
    """Raised when Tor daemon operations fail."""


class TorDaemon:
    """Manages a Tor daemon subprocess with bridge configuration."""

    def __init__(
        self,
        tor_binary: Path,
        data_dir: Path | None = None,
        bridges: list[str] | None = None,
        socks_port: int = DEFAULT_SOCKS_PORT,
        control_port: int = DEFAULT_CONTROL_PORT,
        tor_binary_dir: Path | None = None,
    ):
        if not tor_binary.exists():
            raise TorDaemonError(f"Tor binary not found: {tor_binary}")

        self.tor_binary = tor_binary
        self.data_dir = data_dir or TOR_DATA_DIR
        self.bridges = bridges or []
        self.socks_port = socks_port
        self.control_port = control_port
        self.tor_binary_dir = tor_binary_dir or TOR_BINARY_DIR

        self._process: Optional[subprocess.Popen] = None
        self._torrc_path = self.data_dir / "torrc"
        self._start_time: Optional[float] = None

    # ── Public API ─────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    @property
    def socks_proxy_url(self) -> str:
        return f"socks5://127.0.0.1:{self.socks_port}"

    @property
    def uptime_seconds(self) -> float | None:
        if self._start_time is None:
            return None
        return time.time() - self._start_time

    def start(self, timeout: float = 60.0) -> None:
        """Start the Tor daemon. Blocks until bootstrapped or timeout.

        Raises TorDaemonError if Tor exits prematurely or fails to bootstrap.
        """
        if self.is_running:
            logger.info("Tor daemon already running (PID %s)", self._process.pid)
            return

        self._write_torrc()
        self._verify_prerequisites()

        cmd = [str(self.tor_binary), "-f", str(self._torrc_path)]
        logger.info("Starting Tor with redacted command arguments")

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        self._start_time = time.time()

        # Use a thread to read stdout because select.select()
        # only works on sockets on Windows, not pipes.
        line_queue: queue.Queue = queue.Queue()
        stop_reader = threading.Event()

        def reader():
            """Read Tor stdout line by line into the queue."""
            try:
                assert self._process and self._process.stdout
                for line in iter(self._process.stdout.readline, ""):
                    if stop_reader.is_set():
                        break
                    line_queue.put(line)
            except (ValueError, OSError):
                pass
            finally:
                line_queue.put(None)  # Sentinel: reader done

        reader_thread = threading.Thread(target=reader, daemon=True)
        reader_thread.start()

        # Wait for bootstrap
        deadline = time.time() + timeout
        bootstrapped = False
        last_line = ""

        try:
            while time.time() < deadline:
                # Check if process died
                if self._process.poll() is not None:
                    # Drain remaining lines
                    stop_reader.set()
                    remaining = []
                    while not line_queue.empty():
                        try:
                            remaining.append(line_queue.get_nowait())
                        except queue.Empty:
                            break
                    raise TorDaemonError(
                        f"Tor exited prematurely (code {self._process.returncode})."
                    )

                # Non-blocking read from queue
                try:
                    line = line_queue.get(timeout=0.1)
                    if line is None:  # Reader sentinel
                        break
                    line = line.rstrip()
                    if line:
                        logger.debug("Tor log event received")
                        last_line = line
                        if "Bootstrapped 100%" in line:
                            bootstrapped = True
                            break
                except queue.Empty:
                    pass

        finally:
            stop_reader.set()

        if not bootstrapped:
            self.stop()
            raise TorDaemonError(
                f"Tor failed to bootstrap within {timeout}s; "
                "check connectivity or replace the bridge configuration."
            )

        logger.info(
            "Tor daemon running (PID %s, SOCKS5 %s, uptime %.1fs)",
            self._process.pid,
            self.socks_proxy_url,
            self.uptime_seconds,
        )

    def stop(self, timeout: float = 10.0) -> None:
        """Stop the Tor daemon gracefully."""
        if not self._process:
            return

        pid = self._process.pid
        logger.info("Stopping Tor daemon (PID %s)...", pid)

        if self._process.poll() is None:
            # Graceful shutdown: SIGINT on Linux, terminate() on Windows
            if os.name == "nt":
                self._process.terminate()
            else:
                self._process.send_signal(signal.SIGINT)

            try:
                self._process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                logger.warning("Tor did not exit gracefully, force-killing")
                self._process.kill()
                self._process.wait(timeout=5)

        self._process = None
        self._start_time = None
        logger.info("Tor daemon stopped")

    def health_check(self) -> bool:
        """Check if SOCKS5 port is accepting connections."""
        if not self.is_running:
            return False

        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(("127.0.0.1", self.socks_port))
            sock.close()
            return result == 0
        except Exception:
            return False

    # ── Context manager ────────────────────────────────────────

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()
        return False

    # ── Internals ──────────────────────────────────────────────

    def _verify_prerequisites(self):
        """Check that required files exist before starting Tor."""
        lyrebird = get_lyrebird_path(self.tor_binary_dir)
        if not lyrebird.exists():
            raise TorDaemonError(
                f"Lyrebird (pluggable transport) not found at {lyrebird}.\n"
                f"The Tor Expert Bundle should include lyrebird. "
                f"Re-download with: hermes-tor download"
            )

        geoip, geoip6 = get_geoip_paths(self.tor_binary_dir)
        if not geoip.exists():
            logger.warning("GeoIP database not found at %s — country-based routing disabled", geoip)
        if not geoip6.exists():
            logger.warning("GeoIPv6 database not found at %s", geoip6)

    def _build_torrc(self) -> str:
        """Generate torrc content with absolute paths and user bridges."""
        lyrebird_path = get_lyrebird_path(self.tor_binary_dir)
        geoip_path, geoip6_path = get_geoip_paths(self.tor_binary_dir)

        # Transport plugins — use absolute path to lyrebird
        # lyrebird handles: obfs2, obfs3, obfs4, meek_lite, scramblesuit, webtunnel, snowflake
        transport_plugins = (
            f"ClientTransportPlugin obfs2,obfs3,obfs4,meek_lite,scramblesuit,webtunnel,snowflake "
            f"exec {lyrebird_path}"
        )

        # Bridge section
        if self.bridges:
            bridge_lines = "UseBridges 1\n"
            bridge_lines += "\n".join(f"Bridge {b}" for b in self.bridges)
        else:
            bridge_lines = (
                "# No bridges configured — Tor will use public relays.\n"
                "# To add bridges, save them to ~/.hermes/tor/bridges.txt\n"
                "# and restart. Get bridges from @GetBridgesBot on Telegram."
            )

        return TORRC_TEMPLATE.format(
            generated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            socks_port=self.socks_port,
            control_port=self.control_port,
            data_dir=self.data_dir,
            geoip_path=geoip_path,
            geoip6_path=geoip6_path,
            transport_plugins=transport_plugins,
            bridge_section=bridge_lines,
        )

    def _write_torrc(self):
        """Write torrc to disk."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        torrc_content = self._build_torrc()
        self._torrc_path.write_text(torrc_content)
        logger.debug("torrc written (%d bytes) to %s", len(torrc_content), self._torrc_path)
