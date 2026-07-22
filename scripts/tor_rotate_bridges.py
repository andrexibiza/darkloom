#!/usr/bin/env python3
"""Hermes cron script: fetch fresh Tor bridges daily.

Run: hermes cron create "0 0 * * *" --name "Tor Bridge Rotation" --script tor_rotate_bridges.py --no-agent

Bridges from @GetBridgesBot or BridgeDB web are written to ~/.hermes/tor/bridges.txt.
Non-zero exit triggers Hermes cron error alert.
Daily rotation ensures bridges stay fresh and unblocked.
"""
import sys
import time
from pathlib import Path

BRIDGES_PATH = Path.home() / ".hermes" / "tor" / "bridges.txt"


def fetch_bridges_web() -> list[str]:
    """Fetch obfs4 bridges from BridgeDB. Returns list of bridge lines."""
    import httpx
    url = "https://bridges.torproject.org/bridges?transport=obfs4"
    try:
        resp = httpx.get(url, timeout=30, follow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        print(f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}] Failed to fetch: {e}", file=sys.stderr)
        return []

    bridges = [line.strip() for line in resp.text.splitlines() if line.strip().startswith("obfs4")]
    return bridges


def main():
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    print(f"[{ts}] Bridge rotation check")

    bridges = fetch_bridges_web()
    if not bridges:
        print("No bridges fetched from BridgeDB — keeping existing configuration")
        print("Try @GetBridgesBot on Telegram instead")
        sys.exit(1)

    BRIDGES_PATH.parent.mkdir(parents=True, exist_ok=True)
    BRIDGES_PATH.write_text("\n".join(bridges) + "\n")
    print(f"Rotated {len(bridges)} bridges → {BRIDGES_PATH}")
    for i, b in enumerate(bridges, 1):
        print(f"  [{i}] {b[:90]}...")
    sys.exit(0)


if __name__ == "__main__":
    main()
