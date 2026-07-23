#!/usr/bin/env python3
"""Opt-in Hermes cron script for attempting BridgeDB bridge acquisition.

Run: hermes cron create "0 0 * * *" --name "Tor Bridge Rotation" --script tor_rotate_bridges.py --no-agent

Automated acquisition tells BridgeDB when and from which network bridges are
requested. Scheduling requests also creates a timing pattern that may be
correlated with later Tor use. Bridge addresses are sensitive and are never
printed by this script. BridgeDB's public web workflow may require an
interactive challenge and does not promise an authenticated automation API;
therefore a scheduled run cannot promise fresh bridges on any cadence.

The existing bridge file is retained unless a complete plain-text obfs4 result
passes the shared strict parser. Non-zero exit triggers a Hermes cron alert.
"""
import sys
import time
from pathlib import Path

from darkloom.bridges import parse_bridge_set, save_bridges_to_file

BRIDGES_PATH = Path.home() / ".hermes" / "tor" / "bridges.txt"


def fetch_bridges_web() -> list[str]:
    """Fetch and completely validate a plain-text obfs4 BridgeDB result."""
    import httpx
    url = "https://bridges.torproject.org/bridges?transport=obfs4"
    try:
        resp = httpx.get(url, timeout=30, follow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        print(f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}] Failed to fetch: {e}", file=sys.stderr)
        return []

    content_type = resp.headers.get("content-type", "").partition(";")[0].strip().lower()
    if content_type != "text/plain":
        print("BridgeDB returned an unexpected response; keeping existing configuration", file=sys.stderr)
        return []

    try:
        return [bridge.line for bridge in parse_bridge_set(resp.text, transport="obfs4")]
    except ValueError:
        print("BridgeDB returned an invalid bridge set; keeping existing configuration", file=sys.stderr)
        return []


def main():
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    print(f"[{ts}] Bridge rotation check")

    bridges = fetch_bridges_web()
    if not bridges:
        print("No bridges fetched from BridgeDB — keeping existing configuration")
        print("Use a supported interactive BridgeDB workflow instead")
        sys.exit(1)

    save_bridges_to_file(BRIDGES_PATH, bridges)
    print(f"Stored {len(bridges)} validated bridges")
    sys.exit(0)


if __name__ == "__main__":
    main()
