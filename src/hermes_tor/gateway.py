"""Hermes gateway integration — Tor lifecycle + proxy injection.

This module bridges hermes-tor with the Hermes messaging gateway.
The gateway already has a centralized proxy resolver at
gateway.platforms.base.resolve_proxy_url() that checks:
  1. Platform-specific env var (TELEGRAM_PROXY, DISCORD_PROXY, etc.)
  2. HTTPS_PROXY / HTTP_PROXY / ALL_PROXY (and lowercase variants)
  3. macOS system proxy

By setting ALL_PROXY=socks5://127.0.0.1:9050 BEFORE the gateway starts,
every platform adapter that calls resolve_proxy_url() automatically
routes through Tor.

Usage:
    from hermes_tor.gateway import start_tor_for_gateway

    # Start Tor and inject ALL_PROXY before gateway connects
    mgr = start_tor_for_gateway()

    # ... gateway starts, all platforms route through Tor ...

    # Shutdown
    mgr.stop()

Or as a standalone pre-start wrapper:
    python -m hermes_tor.gateway -- hermes gateway run
"""

import logging
import os
import shutil
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from hermes_tor.constants import (
    BRIDGES_PATH,
    DEFAULT_SOCKS_PORT,
)
from hermes_tor.manager import TorManager, TorStatus
from hermes_tor.policy import NetworkChannel, authorize, authorize_subprocess

logger = logging.getLogger(__name__)

# Environment variables injected for gateway-wide Tor routing.
# ALL_PROXY is the catch-all that resolve_proxy_url() checks after
# platform-specific vars. Setting it means every platform adapter
# that calls resolve_proxy_url() picks up the SOCKS5 proxy.
GATEWAY_ENV_VARS = {
    "ALL_PROXY": f"socks5://127.0.0.1:{DEFAULT_SOCKS_PORT}",
    "HTTPS_PROXY": f"socks5://127.0.0.1:{DEFAULT_SOCKS_PORT}",
    "HTTP_PROXY": f"socks5://127.0.0.1:{DEFAULT_SOCKS_PORT}",
    "TOR_PROXY": f"socks5://127.0.0.1:{DEFAULT_SOCKS_PORT}",
    "TOR_ENABLED": "1",
}

# When TOR_SKIP_LLM=1, LLM API calls bypass Tor to avoid exit node blocking.
# OpenAI, Anthropic, and their CDNs (Cloudflare) block known Tor exit IPs
# with 403/429/CAPTCHA. The API key already identifies your account — Tor
# for LLM calls provides IP privacy but not account anonymity. Bypassing
# Tor for LLM calls preserves streaming performance (TTFT) while keeping
# all other traffic (messaging platforms, web tools, subagents) through Tor.
LLM_SKIP_VARS = {"ALL_PROXY", "HTTPS_PROXY", "HTTP_PROXY"}


def inject_gateway_env(socks_port: int = DEFAULT_SOCKS_PORT):
    """Set ALL_PROXY + HTTPS_PROXY + HTTP_PROXY for gateway-wide Tor routing.

    Must be called BEFORE the Hermes gateway initializes any platform
    connections. The gateway loads ~/.hermes/.env at startup, so
    writing ALL_PROXY to .env is an alternative to runtime injection.

    Platform adapters that use resolve_proxy_url() will automatically
    pick up ALL_PROXY and route through Tor:
      - Telegram:   ✅ TELEGRAM_PROXY > ALL_PROXY > HTTPS_PROXY
      - Discord:    ✅ DISCORD_PROXY  > ALL_PROXY > HTTPS_PROXY
      - Matrix:     ✅ MATRIX_PROXY   > ALL_PROXY > HTTPS_PROXY
      - Slack:      ⚠️ HTTP proxy only (SOCKS rejected by Slack SDK)
      - Photon:     ✅ After applying 0001-photon-proxy.patch
      - WhatsApp:   ✅ After applying 0002-whatsapp-proxy.patch
      - Email:      ❌ Raw SMTP/IMAP — no HTTP proxy support
    """
    proxy_url = f"socks5://127.0.0.1:{socks_port}"
    authorize(NetworkChannel.GATEWAY, proxy_url=proxy_url)
    for key, value in GATEWAY_ENV_VARS.items():
        os.environ[key] = value.replace(str(DEFAULT_SOCKS_PORT), str(socks_port))
    logger.info(
        "Gateway Tor environment injected: ALL_PROXY=%s, TOR_ENABLED=1, "
        "%d env vars set",
        proxy_url,
        len(GATEWAY_ENV_VARS),
    )


def clear_gateway_env():
    """Remove gateway Tor environment variables."""
    for key in GATEWAY_ENV_VARS:
        os.environ.pop(key, None)
    logger.info("Gateway Tor environment cleared")


def skip_llm_proxy():
    """Remove proxy vars so LLM API calls bypass Tor.

    Call this when LLM providers block Tor exit nodes (403/429 errors).
    Removes ALL_PROXY/HTTPS_PROXY/HTTP_PROXY from os.environ so the OpenAI
    SDK connects direct (or through VPN). All other traffic (platform
    adapters, web tools, subagents) still routes through Tor because
    platform-specific proxy vars are set independently.

    Only meaningful when TOR_ENABLED=1. Has no effect otherwise.
    """
    authorize(NetworkChannel.LLM, proxy_url=None, proxy_aware=False)
    if os.environ.get("TOR_ENABLED", "").lower() not in ("1", "true", "yes"):
        return
    for key in LLM_SKIP_VARS:
        os.environ.pop(key, None)
    os.environ["TOR_SKIP_LLM"] = "1"
    logger.warning(
        "TOR_SKIP_LLM=1 — LLM API calls will bypass Tor to avoid exit node blocking. "
        "Platform adapters still route through Tor via platform-specific proxy vars."
    )


def is_llm_skipped() -> bool:
    return os.environ.get("TOR_SKIP_LLM", "").lower() in ("1", "true", "yes")


def write_gateway_env_file(
    socks_port: int = DEFAULT_SOCKS_PORT,
    env_path: Optional[Path] = None,
):
    """Write ALL_PROXY and related vars to ~/.hermes/.env for persistent config.

    The Hermes gateway loads ~/.hermes/.env at startup (gateway/run.py line 1422).
    Writing these vars to .env means Tor routing persists across gateway restarts
    without needing to inject env vars at runtime.

    Args:
        socks_port: SOCKS5 port (default: 9050)
        env_path: Path to .env file (default: ~/.hermes/.env)
    """
    if env_path is None:
        env_path = Path.home() / ".hermes" / ".env"

    proxy_url = f"socks5://127.0.0.1:{socks_port}"

    # Read existing .env content
    existing = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                existing[key.strip()] = value.strip()

    # Merge Tor proxy vars (preserve existing non-Tor vars)
    tor_vars = {
        "ALL_PROXY": proxy_url,
        "HTTPS_PROXY": proxy_url,
        "HTTP_PROXY": proxy_url,
        "TOR_PROXY": proxy_url,
        "TOR_ENABLED": "1",
    }
    existing.update(tor_vars)

    # Write back
    lines = []
    for key, value in sorted(existing.items()):
        lines.append(f"{key}={value}")

    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("\n".join(lines) + "\n")
    logger.info("Gateway Tor config written to %s (%d vars)", env_path, len(tor_vars))


def remove_gateway_env_file(env_path: Optional[Path] = None):
    """Remove Tor proxy vars from ~/.hermes/.env."""
    if env_path is None:
        env_path = Path.home() / ".hermes" / ".env"

    if not env_path.exists():
        return

    tor_keys = set(GATEWAY_ENV_VARS.keys())
    lines = []
    for line in env_path.read_text().splitlines():
        line_stripped = line.strip()
        if line_stripped and not line_stripped.startswith("#") and "=" in line_stripped:
            key = line_stripped.split("=", 1)[0].strip()
            if key in tor_keys:
                continue
        lines.append(line)

    env_path.write_text("\n".join(lines) + ("\n" if lines else ""))
    logger.info("Gateway Tor config removed from %s", env_path)


# ═══════════════════════════════════════════════════════════════
# Self-Healing Tor Watchdog
# ═══════════════════════════════════════════════════════════════

class TorWatchdog:
    """Background thread that monitors Tor health and auto-restarts on failure.

    Self-healing: if Tor dies (process crash, OOM kill, port conflict),
    the watchdog detects it, kills any stale state, restarts the daemon,
    and re-injects proxy env vars. Gateway platform adapters will pick up
    the new connection on their next reconnect cycle.

    Circuit rotation: periodically sends NEWNYM to get fresh Tor circuits,
    preventing long-lived circuit fingerprinting.
    """

    def __init__(
        self,
        manager: TorManager,
        check_interval: float = 15.0,
        circuit_rotate_interval: float = 600.0,  # 10 minutes
        max_restart_attempts: int = 5,
        restart_backoff: float = 10.0,
    ):
        self._mgr = manager
        self._check_interval = check_interval
        self._circuit_rotate_interval = circuit_rotate_interval
        self._max_restart_attempts = max_restart_attempts
        self._restart_backoff = restart_backoff

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._restart_count = 0
        self._last_restart_time: float = 0
        self._last_circuit_rotation: float = 0

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def restart_count(self) -> int:
        return self._restart_count

    def start(self):
        """Start the watchdog background thread."""
        if self.is_running:
            return
        self._stop_event.clear()
        self._last_circuit_rotation = time.time()
        self._thread = threading.Thread(target=self._watchdog_loop, daemon=True, name="tor-watchdog")
        self._thread.start()
        logger.info(
            "Tor watchdog started (health every %.0fs, circuit rotate every %.0fs)",
            self._check_interval, self._circuit_rotate_interval,
        )

    def stop(self):
        """Stop the watchdog thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None
        logger.info("Tor watchdog stopped (restarts: %d)", self._restart_count)

    def _watchdog_loop(self):
        """Main loop: check health, rotate circuits, restart on failure."""
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=self._check_interval)
            if self._stop_event.is_set():
                break

            try:
                self._check_and_heal()
            except Exception:
                logger.exception("Watchdog check failed — will retry")

    def _check_and_heal(self):
        """Check Tor health. Restart if dead. Rotate circuit if due."""
        status = self._mgr.status()

        if status.state.name == "RUNNING" and status.circuit_established:
            self._restart_count = 0  # Reset counter on stable state

            # Circuit rotation
            now = time.time()
            if now - self._last_circuit_rotation > self._circuit_rotate_interval:
                self._rotate_circuit()
                self._last_circuit_rotation = now

        elif status.state.name == "ERROR" or not status.circuit_established:
            logger.warning(
                "Tor health check failed (state=%s, circuit=%s) — attempting restart",
                status.state.name, status.circuit_established,
            )
            self._restart_tor()

        elif status.state.name == "STOPPED":
            logger.warning("Tor daemon stopped unexpectedly — restarting")
            self._restart_tor()

    def _restart_tor(self):
        """Restart Tor daemon with exponential backoff."""
        if self._restart_count >= self._max_restart_attempts:
            logger.error(
                "Tor restart limit reached (%d/%d) — watchdog giving up. "
                "Manual intervention required.",
                self._restart_count, self._max_restart_attempts,
            )
            return

        self._restart_count += 1
        delay = self._restart_backoff * (2 ** (self._restart_count - 1))
        logger.warning(
            "Restarting Tor (attempt %d/%d, delay %.0fs)...",
            self._restart_count, self._max_restart_attempts, delay,
        )

        # Stop any stale daemon
        try:
            self._mgr.stop()
        except Exception:
            pass

        # Small delay before restart
        time.sleep(delay)

        # Restart
        try:
            status = self._mgr.start(timeout=60)
            if status.state.name == "RUNNING":
                logger.info("Tor restarted successfully (attempt %d)", self._restart_count)
                self._restart_count = 0

                # Re-inject env vars so new connections pick up the fresh proxy
                inject_gateway_env(self._mgr.socks_port)
                write_gateway_env_file(self._mgr.socks_port)

                self._last_restart_time = time.time()
            else:
                logger.error("Tor restart failed: %s", status.error)
        except Exception:
            logger.exception("Tor restart raised exception")

    def _rotate_circuit(self):
        """Request a new Tor circuit (fresh exit node).

        Sends NEWNYM signal via ControlPort if available.
        Falls back to daemon restart for circuit rotation.
        """
        try:
            from hermes_tor.policy import NetworkChannel, authorize
            authorize(NetworkChannel.TOR_CONTROL, local_only=True)
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect(("127.0.0.1", self._mgr.control_port))
            sock.sendall(b"AUTHENTICATE\r\nSIGNAL NEWNYM\r\nQUIT\r\n")
            response = sock.recv(1024)
            sock.close()
            if b"250" in response:
                logger.info("Tor circuit rotated via NEWNYM signal")
                return
        except Exception:
            logger.debug("NEWNYM via ControlPort failed, restarting daemon for fresh circuit")

        # Fallback: restart daemon for fresh circuit
        logger.info("Restarting Tor daemon for fresh circuit...")
        self._restart_tor()


def start_tor_for_gateway(
    socks_port: int = DEFAULT_SOCKS_PORT,
    bootstrap_timeout: float = 60.0,
    write_env: bool = True,
) -> TorManager:
    """Start Tor and inject gateway-wide proxy environment.

    This is the primary entry point for gateway integration.
    Call this BEFORE starting the Hermes gateway.

    Args:
        socks_port: SOCKS5 port (default: 9050)
        bootstrap_timeout: Max seconds to wait for Tor bootstrap
        write_env: If True, persist ALL_PROXY to ~/.hermes/.env

    Returns:
        TorManager instance (call .stop() to shut down)

    Raises:
        TorDaemonError: If Tor fails to bootstrap
    """
    mgr = TorManager(auto_download=True, socks_port=socks_port)

    # Load bridges if available
    bridge_count = mgr.load_bridges()
    if bridge_count == 0:
        logger.warning(
            "No bridges configured — Tor will use public relays. "
            "Get bridges from @GetBridgesBot on Telegram and save to %s",
            BRIDGES_PATH,
        )

    # Start Tor
    logger.info("Starting Tor for gateway (timeout=%ds)...", bootstrap_timeout)
    status = mgr.start(timeout=bootstrap_timeout)

    if status.state.name != "RUNNING":
        raise RuntimeError(f"Tor failed to start: {status.error}")

    # Inject environment
    inject_gateway_env(socks_port)

    # Persist to .env for gateway restarts
    if write_env:
        write_gateway_env_file(socks_port)

    logger.info(
        "Tor ready for gateway — SOCKS5 %s, circuit %s, bridges %d, uptime %.1fs",
        status.socks_proxy_url,
        "established" if status.circuit_established else "pending",
        status.bridge_count,
        status.uptime_seconds or 0,
    )

    # Start self-healing watchdog
    watchdog = TorWatchdog(
        manager=mgr,
        check_interval=15.0,           # health check every 15s
        circuit_rotate_interval=600.0,  # fresh circuit every 10 min
        max_restart_attempts=5,
        restart_backoff=10.0,
    )
    watchdog.start()

    # Attach watchdog to manager so caller can stop it
    mgr._watchdog = watchdog

    return mgr


def _is_proxy_aware_gateway_command(command: list[str]) -> bool:
    """Return whether *command* is the installed Hermes gateway launcher.

    Proxy environment variables are only meaningful for the patched Hermes
    process.  An arbitrary native executable can ignore them, so strict mode
    must not infer proxy support merely because this wrapper supplied env vars.
    """
    if len(command) < 3 or command[1:3] != ["gateway", "run"]:
        return False
    executable = shutil.which(command[0])
    if executable is None:
        return False
    try:
        launcher = Path(executable).read_text(encoding="utf-8", errors="ignore")
    except (OSError, UnicodeError):
        return False
    return "hermes_cli" in launcher and "import main" in launcher


# ── CLI entry point ────────────────────────────────────────────

def main():
    """Pre-start wrapper: start Tor, then exec the gateway.

    Usage:
        python -m hermes_tor.gateway -- hermes gateway run
        python -m hermes_tor.gateway --timeout 90 -- hermes gateway run

    The -- separator divides hermes-tor flags from gateway flags.
    Everything after -- is passed verbatim to the gateway process.
    """
    import argparse
    import subprocess

    parser = argparse.ArgumentParser(
        description="Start Tor, then launch Hermes gateway with ALL_PROXY set"
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_SOCKS_PORT,
        help=f"SOCKS5 port (default: {DEFAULT_SOCKS_PORT})",
    )
    parser.add_argument(
        "--timeout", type=float, default=60.0,
        help="Tor bootstrap timeout in seconds (default: 60)",
    )
    parser.add_argument(
        "--no-env-file", action="store_true",
        help="Skip writing ALL_PROXY to ~/.hermes/.env",
    )
    parser.add_argument(
        "gateway_args", nargs=argparse.REMAINDER,
        help="Arguments to pass to the gateway (after -- separator)",
    )

    args = parser.parse_args()

    # Strip the leading '--' separator if present
    gateway_cmd = args.gateway_args
    if gateway_cmd and gateway_cmd[0] == "--":
        gateway_cmd = gateway_cmd[1:]

    if not gateway_cmd:
        print("Usage: python -m hermes_tor.gateway -- hermes gateway run", file=sys.stderr)
        print("       python -m hermes_tor.gateway --timeout 90 -- hermes gateway run", file=sys.stderr)
        sys.exit(1)

    # Start Tor
    print(f"[hermes-tor] Starting Tor daemon (port {args.port}, timeout {args.timeout}s)...")
    try:
        mgr = start_tor_for_gateway(
            socks_port=args.port,
            bootstrap_timeout=args.timeout,
            write_env=not args.no_env_file,
        )
    except Exception as e:
        print(f"[hermes-tor] FATAL: Tor failed to start: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"[hermes-tor] Tor running — SOCKS5 on 127.0.0.1:{args.port}")
    print(f"[hermes-tor] ALL_PROXY injected — all gateway platforms will route through Tor")
    print(f"[hermes-tor] Self-healing watchdog active (health every 15s, circuit rotate every 10min)")
    print(f"[hermes-tor] Launching: {' '.join(gateway_cmd)}")
    print()

    # Exec the gateway
    try:
        authorize_subprocess(proxy_aware=_is_proxy_aware_gateway_command(gateway_cmd))
        result = subprocess.run(gateway_cmd)
        sys.exit(result.returncode)
    finally:
        print("[hermes-tor] Gateway exited — stopping Tor daemon...")
        # Stop watchdog first
        watchdog = getattr(mgr, '_watchdog', None)
        if watchdog:
            watchdog.stop()
        mgr.stop()
        clear_gateway_env()
        print("[hermes-tor] Tor stopped.")


if __name__ == "__main__":
    main()
