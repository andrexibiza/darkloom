"""hermes-tor — Micro-TOR client for Hermes agents.

Route Hermes agent and subagent tool-level network traffic
through the Tor network using bridges for anonymity.

Modules:
    constants   — Platform detection, verified URLs, path resolution
    downloader  — Tor Expert Bundle downloader
    bridges     — Bridge parsing, validation, persistence
    daemon      — Tor subprocess lifecycle manager
    proxy_http  — SOCKS5-aware HTTP helpers for execute_code blocks
    verifier    — Anonymity verification via check.torproject.org
    manager     — Unified TorManager API with state machine
    mcp_server  — MCP server (6 tools) for Hermes integration
    gateway     — Hermes gateway integration (ALL_PROXY injection)
"""

__version__ = "0.1.0"
