"""Bridge configuration — parsing, validation, and file management.

Bridges are user-provided. Sources:
  1. Telegram: @GetBridgesBot (send /bridges)
  2. Web: https://bridges.torproject.org/bridges?transport=obfs4
  3. Email: bridges@torproject.org (from Gmail/Riseup, body: "get transport obfs4")

Bridges are stored one-per-line in ~/.hermes/tor/bridges.txt.
"""
import ipaddress
import logging
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# obfs4 bridges: obfs4 <IP>:<PORT> <FINGERPRINT> [cert=...] [iat-mode=...]
OBFS4_RE = re.compile(
    r"^obfs4\s+(?P<address>[\d.]+:\d+)\s+(?P<fingerprint>[A-Fa-f0-9]+)"
)

# BridgeDB's obfs4 result format. This deliberately uses fullmatch so a valid
# prefix cannot disguise trailing HTML, script, or an additional response.
OBFS4_RESULT_RE = re.compile(
    r"obfs4\s+[\d.]+:(?:[1-9]\d{0,4})\s+[A-Fa-f0-9]{40}"
    r"\s+cert=\S+\s+iat-mode=[01]"
)

# Vanilla bridges: <IP>:<PORT> <FINGERPRINT>
VANILLA_RE = re.compile(
    r"^(?P<address>[\d.]+:\d+)\s+(?P<fingerprint>[A-Fa-f0-9]{40})"
)


@dataclass
class Bridge:
    """A single Tor bridge entry."""

    transport: str  # "obfs4", "vanilla", "snowflake", etc.
    address: str    # "1.2.3.4:443"
    fingerprint: str
    raw: str        # Original bridge line (used directly in torrc)

    @property
    def line(self) -> str:
        return self.raw


def parse_bridge_line(line: str) -> Optional[Bridge]:
    """Parse a single bridge line into a Bridge object.

    Returns None for comments, blank lines, or unrecognized formats.
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    # Try obfs4 first (most common)
    m = OBFS4_RE.match(line)
    if m:
        return Bridge(
            transport="obfs4",
            address=m.group("address"),
            fingerprint=m.group("fingerprint"),
            raw=line,
        )

    # Try vanilla
    m = VANILLA_RE.match(line)
    if m:
        return Bridge(
            transport="vanilla",
            address=m.group("address"),
            fingerprint=m.group("fingerprint"),
            raw=line,
        )

    # Snowflake bridges
    if line.startswith("snowflake"):
        logger.debug("Snowflake bridge (no fingerprint parsing): %s", line[:80])
        return Bridge(
            transport="snowflake",
            address="",
            fingerprint="",
            raw=line,
        )

    # Unknown format — still pass through to torrc as-is
    logger.warning("Unrecognized bridge format, passing through: %s", line[:80])
    return Bridge(
        transport="unknown",
        address="",
        fingerprint="",
        raw=line,
    )


def validate_bridge(line: str) -> bool:
    """Check if a bridge line is syntactically valid."""
    return parse_bridge_line(line) is not None


def parse_bridge_set(text: str, *, transport: str | None = None) -> list[Bridge]:
    """Parse an all-or-nothing set of bridge lines from an external source.

    Unlike :func:`parse_bridge_line`, which is intentionally tolerant when
    reading a user-managed file, this rejects comments, markup, unknown
    transports, and mixed malformed content.  Callers can therefore validate
    an entire response before replacing a known-good configuration.
    """
    lines = text.splitlines()
    if not lines:
        raise ValueError("bridge result is empty")

    bridges: list[Bridge] = []
    for line in lines:
        if not line.strip():
            continue
        bridge = parse_bridge_line(line)
        if (
            bridge is None
            or bridge.transport == "unknown"
            or (transport is not None and bridge.transport != transport)
        ):
            raise ValueError("bridge result contains an invalid line")
        if bridge.transport == "obfs4" and not OBFS4_RESULT_RE.fullmatch(bridge.raw):
            raise ValueError("bridge result contains a malformed obfs4 line")
        if bridge.transport == "obfs4":
            host, port = bridge.address.rsplit(":", 1)
            try:
                ipaddress.IPv4Address(host)
            except ipaddress.AddressValueError as exc:
                raise ValueError("bridge result contains an invalid address") from exc
            if not 1 <= int(port) <= 65535:
                raise ValueError("bridge result contains an invalid port")
        bridges.append(bridge)

    if not bridges:
        raise ValueError("bridge result contains no bridges")
    return bridges


def load_bridges_from_file(path: Path) -> list[Bridge]:
    """Load bridges from a text file (one per line, # for comments)."""
    if not path.exists():
        logger.warning("No bridges file at %s — Tor will use public relays", path)
        return []

    bridges = []
    for line in path.read_text().splitlines():
        bridge = parse_bridge_line(line)
        if bridge:
            bridges.append(bridge)

    logger.info("Loaded %d bridges from %s", len(bridges), path)
    return bridges


def save_bridges_to_file(path: Path, bridge_lines: list[str], append: bool = False):
    """Atomically save bridge lines to a private file.

    Args:
        path: File path.
        bridge_lines: List of full bridge lines.
        append: If True, append to existing file instead of overwriting.
    """
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    new_lines = [line.strip() for line in bridge_lines]
    content = ""
    if append and path.exists():
        content = path.read_text()
        if content and not content.endswith("\n"):
            content += "\n"
    content += "".join(f"{line}\n" for line in new_lines)

    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as temporary_file:
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise

    logger.info("Wrote %d bridges to %s (append=%s)", len(new_lines), path, append)


def format_bridges_for_torrc(bridges: list[Bridge]) -> list[str]:
    """Convert Bridge objects to torrc-compatible 'Bridge <line>' format."""
    return [f"Bridge {b.raw}" for b in bridges]
