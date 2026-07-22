"""MCP server exposing Tor management tools to Hermes.

Register with:
    hermes mcp add hermes-tor --command "python -m hermes_tor.mcp_server"

Provides 6 tools:
    tor_download    — Download Tor Expert Bundle
    tor_start       — Start Tor daemon with bridges
    tor_stop        — Stop Tor daemon
    tor_status      — Get current Tor status
    tor_verify      — Verify traffic routes through Tor
    tor_add_bridge  — Add a bridge line
"""
import json
import logging
import sys
from pathlib import Path

from hermes_tor.manager import TorManager, TorState
from hermes_tor.constants import BRIDGES_PATH, CURRENT_PLATFORM
from hermes_tor.privacy import classify_error, private_diagnostic, require_local_admin

from hermes_tor.privacy import get_logger

logger = get_logger(__name__)

# Module-level singleton — one TorManager per process
_manager: TorManager | None = None


def _error(error: object, component: str, code: str | None = None) -> str:
    """Serialize only the stable public classification to an MCP caller."""
    private_diagnostic(component, error)
    public = classify_error(error)
    return json.dumps({"ok": False, "error": {"code": code or public.code, "message": str(error) if code else public.message}})


def get_manager(auto_download: bool = True) -> TorManager:
    global _manager
    if _manager is None:
        _manager = TorManager(auto_download=auto_download)
        # Load existing bridges
        _manager.load_bridges()
    return _manager


# ── Tool handlers ─────────────────────────────────────────────

def tor_download() -> str:
    """Download the Tor Expert Bundle for the current platform.

    One-time setup. Downloads ~22-32MB. Subsequent calls return
    immediately if already installed.
    """
    try:
        mgr = get_manager()
        mgr.ensure_installed()
        return json.dumps({
            "ok": True,
            "installed": True,
            "platform": CURRENT_PLATFORM,
        })
    except Exception as e:
        return _error(e, "tor_download")


def tor_start(socks_port: int = 9050, timeout: float = 60.0) -> str:
    """Start the Tor daemon with configured bridges.

    Bridges are loaded from ~/.hermes/tor/bridges.txt.
    If no bridges are configured, Tor uses public relays.

    Get bridges from @GetBridgesBot on Telegram, then use
    tor_add_bridge to configure them before starting.
    """
    try:
        mgr = get_manager()
        mgr.socks_port = socks_port
        mgr.load_bridges()
        status = mgr.start(timeout=timeout)
    except Exception as exc:
        return _error(exc, "tor_start")
    if status.error:
        return _error(status.error, "tor_start", status.error_code)
    return json.dumps({
        "ok": True,
        "state": status.state.name,
        "socks_proxy_url": status.socks_proxy_url,
        "circuit_established": status.circuit_established,
        "bridge_count": status.bridge_count,
        "uptime_seconds": status.uptime_seconds,
    })


def tor_stop() -> str:
    """Stop the Tor daemon."""
    try:
        mgr = get_manager()
        status = mgr.stop()
        return json.dumps({"ok": True, "state": status.state.name})
    except Exception as exc:
        return _error(exc, "tor_stop")


def tor_status() -> str:
    """Get current Tor daemon status including bridge count and uptime."""
    try:
        status = get_manager().status()
        return json.dumps({
            "state": status.state.name,
            "socks_proxy_url": status.socks_proxy_url,
            "circuit_established": status.circuit_established,
            "bridge_count": status.bridge_count,
            "uptime_seconds": status.uptime_seconds,
            "ok": True,
        })
    except Exception as exc:
        return _error(exc, "tor_status")


def tor_verify() -> str:
    """Verify traffic routes through Tor.

    Hits https://check.torproject.org/ through the SOCKS5 proxy
    and reports whether the exit node is a Tor relay.
    """
    try:
        mgr = get_manager()
        result = mgr.verify()
    except Exception as exc:
        return _error(exc, "tor_verify")
    if result.error:
        return _error(result.error, "tor_verify")
    return json.dumps({
        "ok": True,
        "using_tor": result.using_tor,
        "is_anonymous": result.is_anonymous,
    })


def tor_add_bridge(bridge_line: str) -> str:
    """Add a Tor bridge line to the configuration.

    Bridges are persisted to ~/.hermes/tor/bridges.txt.
    After adding bridges, restart Tor with tor_stop + tor_start
    to use the new bridges.

    Get bridges from:
      1. Telegram: @GetBridgesBot (send /bridges)
      2. Web: https://bridges.torproject.org/bridges?transport=obfs4

    Example bridge lines:
      obfs4 1.2.3.4:443 FINGERPRINT cert=... iat-mode=0
    """
    try:
        mgr = get_manager()
        count = mgr.add_bridge(bridge_line)
    except Exception as exc:
        return _error(exc, "tor_add_bridge")
    return json.dumps({
        "ok": True,
        "added": True,
        "total_bridges": count,
        "hint": "Restart Tor with tor_stop + tor_start to use new bridges",
    })


def local_admin_diagnostics(token: str) -> str:
    """Non-MCP local interface for explicitly authorized sensitive details."""
    require_local_admin(token)
    mgr = get_manager()
    status = mgr.status()
    result = mgr.verify() if status.socks_proxy_url else None
    return json.dumps({
        "exit_ip": result.exit_ip if result else None,
        "data_dir": str(mgr.data_dir),
        "bridges_file": str(BRIDGES_PATH),
        "error": result.error if result else status.error,
    })


# ── MCP Tool definitions ──────────────────────────────────────

TOOLS = [
    {
        "name": "tor_download",
        "description": "Download the Tor Expert Bundle (~22-32MB). One-time setup for anonymous routing.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "tor_start",
        "description": "Start the Tor daemon with configured bridges. Loads bridges from ~/.hermes/tor/bridges.txt. Blocks until bootstrapped or timeout.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "socks_port": {
                    "type": "integer",
                    "description": "SOCKS5 port (default: 9050)",
                    "default": 9050,
                },
                "timeout": {
                    "type": "number",
                    "description": "Bootstrap timeout in seconds (default: 60)",
                    "default": 60.0,
                },
            },
        },
    },
    {
        "name": "tor_stop",
        "description": "Stop the Tor daemon gracefully.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "tor_status",
        "description": "Get current Tor daemon status: state, SOCKS5 URL, circuit status, bridge count, uptime.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "tor_verify",
        "description": "Verify traffic is routing through Tor without exposing network identity.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "tor_add_bridge",
        "description": "Add a Tor bridge line. Bridges are persisted to ~/.hermes/tor/bridges.txt. Get bridges from @GetBridgesBot on Telegram.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "bridge_line": {
                    "type": "string",
                    "description": "Full bridge line, e.g. 'obfs4 1.2.3.4:443 FINGERPRINT cert=... iat-mode=0'",
                },
            },
            "required": ["bridge_line"],
        },
    },
]

HANDLERS = {
    "tor_download": tor_download,
    "tor_start": tor_start,
    "tor_stop": tor_stop,
    "tor_status": tor_status,
    "tor_verify": tor_verify,
    "tor_add_bridge": tor_add_bridge,
}


# ── MCP Server entry point ────────────────────────────────────


def serve():
    """Run the MCP server via stdio.

    Hermes connects via:
      hermes mcp add hermes-tor --command "python -m hermes_tor.mcp_server"
    """
    try:
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
    except ImportError:
        print(
            "MCP SDK not installed. Run: pip install mcp\n"
            "Or install with: uv pip install -e '.[mcp]'",
            file=sys.stderr,
        )
        sys.exit(1)

    server = Server("hermes-tor")

    for tool_def in TOOLS:
        handler = HANDLERS[tool_def["name"]]
        name = tool_def["name"]
        desc = tool_def["description"]

        # Register with closure capturing the handler
        def _register(n, d, h):
            @server.tool(n, d)
            def tool_fn(**kwargs):
                return h(**kwargs)

        _register(name, desc, handler)

    import asyncio

    async def run():
        async with stdio_server() as (read, write):
            await server.run(read, write)

    asyncio.run(run())


if __name__ == "__main__":
    serve()
