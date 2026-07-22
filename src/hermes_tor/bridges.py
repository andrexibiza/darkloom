"""Bridge configuration — parsing, validation, and file management.

Bridges are user-provided. Sources:
  1. Telegram: @GetBridgesBot (send /bridges)
  2. Web: https://bridges.torproject.org/bridges?transport=obfs4
  3. Email: bridges@torproject.org (from Gmail/Riseup, body: "get transport obfs4")

Bridges are stored one-per-line in ~/.hermes/tor/bridges.txt.
"""
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from hermes_tor.secure_files import atomic_private_write, private_lock, secure_read

logger = logging.getLogger(__name__)

# obfs4 bridges: obfs4 <IP>:<PORT> <FINGERPRINT> [cert=...] [iat-mode=...]
OBFS4_RE = re.compile(
    r"^obfs4\s+(?P<address>[\d.]+:\d+)\s+(?P<fingerprint>[A-Fa-f0-9]+)"
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


def load_bridges_from_file(path: Path) -> list[Bridge]:
    """Load bridges from a text file (one per line, # for comments)."""
    if not path.exists():
        logger.warning("No bridges file at %s — Tor will use public relays", path)
        return []

    with private_lock(path):
        content = secure_read(path)

    bridges = []
    for line in content.splitlines():
        bridge = parse_bridge_line(line)
        if bridge:
            bridges.append(bridge)

    logger.info("Loaded %d bridges from %s", len(bridges), path)
    return bridges


def save_bridges_to_file(path: Path, bridge_lines: list[str], append: bool = False):
    """Save bridge lines to a file.

    Args:
        path: File path.
        bridge_lines: List of full bridge lines.
        append: If True, append to existing file instead of overwriting.
    """
    with private_lock(path):
        previous = secure_read(path) if append and path.exists() else ""
        content = previous + "".join(line.strip() + "\n" for line in bridge_lines)
        atomic_private_write(path, content)

    logger.info("Wrote %d bridges to %s (append=%s)", len(bridge_lines), path, append)


def format_bridges_for_torrc(bridges: list[Bridge]) -> list[str]:
    """Convert Bridge objects to torrc-compatible 'Bridge <line>' format."""
    return [f"Bridge {b.raw}" for b in bridges]
