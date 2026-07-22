"""Proxy-aware HTTP helpers for Hermes execute_code blocks.

These functions create httpx clients with SOCKS5 transports when
TOR_ENABLED=1 is set in the environment. When Tor is disabled or
unavailable, they fall back to direct connections.

socksio is already installed in the Hermes venv — no extra deps needed.

Usage in an execute_code block:

    import os
    os.environ["TOR_ENABLED"] = "1"

    from hermes_tor.proxy_http import tor_get, tor_post, check_tor_connection

    # Verify Tor is working
    status = check_tor_connection()
    print(f"Using Tor: {status['using_tor']}")

    # Make anonymous requests
    data = tor_get("https://httpbin.org/ip")
    print(data["text"])

Environment variables:
    TOR_ENABLED  — "1"/"true"/"yes" to route through Tor (default: disabled)
    TOR_PROXY    — SOCKS5 proxy URL (default: socks5://127.0.0.1:9050)
"""
import logging
import os
from typing import Any

import httpx

from hermes_tor.daemon import authenticated_socks_proxy_url

logger = logging.getLogger(__name__)

DEFAULT_PROXY = "socks5://127.0.0.1:9050"


def _is_tor_enabled() -> bool:
    """Check if Tor routing is enabled via environment variable."""
    return os.environ.get("TOR_ENABLED", "").lower() in ("1", "true", "yes")


def _get_proxy_url() -> str:
    """Get the listener port and return fresh authentication for this request."""
    from urllib.parse import urlsplit

    configured = urlsplit(os.environ.get("TOR_PROXY", DEFAULT_PROXY))
    if configured.scheme != "socks5" or configured.hostname not in {
        "127.0.0.1",
        "localhost",
    }:
        raise ValueError("TOR_PROXY must identify the local socks5 Tor listener")
    return authenticated_socks_proxy_url(configured.port or 9050)


def _get_transport(use_tor: bool = True):
    """Return a SOCKS5 transport if Tor is enabled, None for direct connection.

    Uses httpx.HTTPTransport with socks5 proxy. socksio is already
    installed in the Hermes venv — it handles the SOCKS protocol
    without additional dependencies.
    """
    if use_tor and _is_tor_enabled():
        return httpx.HTTPTransport(proxy=_get_proxy_url())
    return None


def tor_get(url: str, use_tor: bool = True, timeout: float = 30.0, **kwargs) -> dict:
    """HTTP GET through Tor (or direct if Tor disabled).

    Args:
        url: Target URL.
        use_tor: If False, always use direct connection.
        timeout: Request timeout in seconds.
        **kwargs: Passed to httpx.Client.get().

    Returns:
        dict with status_code, text, headers, url keys.
    """
    transport = _get_transport(use_tor)
    with httpx.Client(
        transport=transport,
        timeout=timeout,
        follow_redirects=True,
    ) as client:
        resp = client.get(url, **kwargs)
        resp.raise_for_status()
        return {
            "status_code": resp.status_code,
            "headers": dict(resp.headers),
            "text": resp.text,
            "url": str(resp.url),
        }


def tor_post(
    url: str,
    use_tor: bool = True,
    timeout: float = 30.0,
    **kwargs,
) -> dict:
    """HTTP POST through Tor (or direct if Tor disabled)."""
    transport = _get_transport(use_tor)
    with httpx.Client(
        transport=transport,
        timeout=timeout,
        follow_redirects=True,
    ) as client:
        resp = client.post(url, **kwargs)
        resp.raise_for_status()
        return {
            "status_code": resp.status_code,
            "headers": dict(resp.headers),
            "text": resp.text,
            "url": str(resp.url),
        }


def tor_request(
    method: str,
    url: str,
    use_tor: bool = True,
    timeout: float = 30.0,
    **kwargs,
) -> dict:
    """Generic HTTP request through Tor."""
    transport = _get_transport(use_tor)
    with httpx.Client(
        transport=transport,
        timeout=timeout,
        follow_redirects=True,
    ) as client:
        resp = client.request(method, url, **kwargs)
        resp.raise_for_status()
        return {
            "status_code": resp.status_code,
            "headers": dict(resp.headers),
            "text": resp.text,
            "url": str(resp.url),
        }


def check_tor_connection(timeout: float = 30.0) -> dict:
    """Check if we can reach the internet through Tor.

    Hits https://check.torproject.org/ through the SOCKS5 proxy.
    Parses the response to determine if traffic is routing through Tor.

    Returns:
        dict with keys: tor_available, using_tor, exit_ip, error
    """
    result = {
        "tor_available": False,
        "using_tor": False,
        "exit_ip": None,
        "error": None,
    }

    if not _is_tor_enabled():
        result["error"] = "TOR_ENABLED is not set to 1/true/yes"
        return result

    try:
        data = tor_get("https://check.torproject.org/", timeout=timeout)
        result["tor_available"] = True

        text = data["text"]
        if "Congratulations" in text and "Tor" in text:
            result["using_tor"] = True

        # Try to extract exit IP
        import re
        ip_match = re.search(
            r"IP address appears to be:\s*<strong>([\d.]+)</strong>",
            text,
            re.IGNORECASE,
        )
        if ip_match:
            result["exit_ip"] = ip_match.group(1)

    except Exception as e:
        result["error"] = str(e)

    return result


def inject_tor_env(socks_proxy_url: str = DEFAULT_PROXY):
    """Set environment variables so subagents use Tor automatically.

    Subagents run in ThreadPoolExecutor threads — they inherit
    the parent's os.environ. Call this before delegate_task().

    Args:
        socks_proxy_url: SOCKS5 proxy URL (default: socks5://127.0.0.1:9050)
    """
    os.environ["TOR_PROXY"] = socks_proxy_url
    os.environ["TOR_ENABLED"] = "1"
    logger.info("Tor environment injected: TOR_ENABLED=1, TOR_PROXY=%s", socks_proxy_url)


def clear_tor_env():
    """Remove Tor environment variables."""
    os.environ.pop("TOR_PROXY", None)
    os.environ.pop("TOR_ENABLED", None)
    logger.info("Tor environment cleared")
