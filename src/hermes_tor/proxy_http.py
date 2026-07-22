"""Proxy-aware, privacy-preserving HTTP helpers for execute-code blocks."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, NotRequired, TypeAlias, TypedDict
from urllib.parse import urlsplit, urlunsplit

import httpx

logger = logging.getLogger(__name__)

DEFAULT_PROXY = "socks5://127.0.0.1:9050"
DEFAULT_MAX_BODY_BYTES = 1_048_576


class ResponseTooLargeError(ValueError):
    """Raised before or during download when a response exceeds its limit."""


JSONValue: TypeAlias = None | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]
ResponseBody: TypeAlias = JSONValue | dict[str, str] | bytes


class SafeHTTPResponse(TypedDict):
    """The deliberately small, persistence-safe default response shape."""

    status_code: int
    headers: dict[str, str]
    url: str
    body: ResponseBody
    body_type: str
    size_bytes: int
    sensitive: NotRequired[bool]
    persistence: NotRequired[str]


_EXCLUDED_HEADERS = {
    "authorization",
    "authentication-info",
    "proxy-authenticate",
    "proxy-authentication-info",
    "set-cookie",
    "www-authenticate",
}


def _is_tor_enabled() -> bool:
    return os.environ.get("TOR_ENABLED", "").lower() in ("1", "true", "yes")


def _get_proxy_url() -> str:
    return os.environ.get("TOR_PROXY", DEFAULT_PROXY)


def _get_transport(use_tor: bool = True):
    if use_tor and _is_tor_enabled():
        return httpx.HTTPTransport(proxy=_get_proxy_url())
    return None


def _safe_url(url: httpx.URL | str) -> str:
    """Remove credentials, query parameters, and fragments from a URL."""
    parts = urlsplit(str(url))
    hostname = parts.hostname or ""
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    netloc = hostname
    if parts.port is not None:
        netloc += f":{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))


def _safe_headers(headers: httpx.Headers) -> dict[str, str]:
    result: dict[str, str] = {}
    for name, value in headers.items():
        lower = name.lower()
        if lower in _EXCLUDED_HEADERS or lower.startswith("proxy-"):
            continue
        if lower == "location":
            location = urlsplit(value)
            # Redirect paths sometimes embed bearer/reset tokens. Omit suspect
            # locations instead of attempting to redact secrets heuristically.
            if (
                location.username
                or location.password
                or location.query
                or location.fragment
                or re.search(r"(?:token|secret|password|session|auth|key)", location.path, re.I)
            ):
                continue
            result[name] = _safe_url(value)
        else:
            result[name] = value
    return result


def _parse_body(data: bytes, content_type: str) -> tuple[ResponseBody, str]:
    media_type = content_type.partition(";")[0].strip().lower()
    if media_type == "application/json" or media_type.endswith("+json"):
        try:
            return json.loads(data), "json"
        except (UnicodeDecodeError, json.JSONDecodeError):
            return data.decode("utf-8", errors="replace"), "text"
    if media_type.startswith("text/") or media_type in {
        "application/javascript",
        "application/xml",
        "application/xhtml+xml",
    } or media_type.endswith("+xml"):
        return data.decode("utf-8", errors="replace"), "text"
    # Binary content is represented by metadata unless raw-body capability is set.
    return {"content_type": media_type or "application/octet-stream"}, "binary"


def _read_limited(response: httpx.Response, max_body_bytes: int) -> bytes:
    if max_body_bytes < 0:
        raise ValueError("max_body_bytes must be non-negative")
    content_length = response.headers.get("content-length")
    if content_length:
        try:
            advertised_size = int(content_length)
        except ValueError:
            # Invalid Content-Length is untrusted input; enforce while streaming.
            pass
        else:
            if advertised_size > max_body_bytes:
                raise ResponseTooLargeError(
                    f"response Content-Length {content_length} exceeds "
                    f"max_body_bytes={max_body_bytes}"
                )

    chunks: list[bytes] = []
    size = 0
    for chunk in response.iter_bytes():
        size += len(chunk)
        if size > max_body_bytes:
            raise ResponseTooLargeError(
                f"streamed response exceeds max_body_bytes={max_body_bytes}"
            )
        chunks.append(chunk)
    return b"".join(chunks)


def tor_request(
    method: str,
    url: str,
    use_tor: bool = True,
    timeout: float = 30.0,
    *,
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
    include_sensitive_headers: bool = False,
    include_raw_body: bool = False,
    include_full_url: bool = False,
    **kwargs: Any,
) -> SafeHTTPResponse:
    """Make a request with bounded streaming and a privacy-safe response.

    The three ``include_*`` arguments are explicit capabilities. Enabling any of
    them marks the result ``sensitive`` and ``persistence='suppress'`` so callers
    can prevent transcript/log persistence.
    """
    transport = _get_transport(use_tor)
    with httpx.Client(transport=transport, timeout=timeout, follow_redirects=True) as client:
        with client.stream(method, url, **kwargs) as response:
            response.raise_for_status()
            data = _read_limited(response, max_body_bytes)
            body, body_type = _parse_body(data, response.headers.get("content-type", ""))
            if include_raw_body:
                body, body_type = data, "bytes"
            result: SafeHTTPResponse = {
                "status_code": response.status_code,
                "headers": (
                    dict(response.headers) if include_sensitive_headers else _safe_headers(response.headers)
                ),
                "url": str(response.url) if include_full_url else _safe_url(response.url),
                "body": body,
                "body_type": body_type,
                "size_bytes": len(data),
            }
            if include_sensitive_headers or include_raw_body or include_full_url:
                result["sensitive"] = True
                result["persistence"] = "suppress"
            return result


def tor_get(url: str, use_tor: bool = True, timeout: float = 30.0, **kwargs: Any) -> SafeHTTPResponse:
    """HTTP GET through Tor (or directly when Tor is disabled)."""
    return tor_request("GET", url, use_tor=use_tor, timeout=timeout, **kwargs)


def tor_post(url: str, use_tor: bool = True, timeout: float = 30.0, **kwargs: Any) -> SafeHTTPResponse:
    """HTTP POST through Tor (or directly when Tor is disabled)."""
    return tor_request("POST", url, use_tor=use_tor, timeout=timeout, **kwargs)


def check_tor_connection(timeout: float = 30.0) -> dict[str, Any]:
    """Check whether the configured proxy reaches the Tor check service."""
    result = {"tor_available": False, "using_tor": False, "exit_ip": None, "error": None}
    if not _is_tor_enabled():
        result["error"] = "TOR_ENABLED is not set to 1/true/yes"
        return result
    try:
        data = tor_get("https://check.torproject.org/", timeout=timeout)
        result["tor_available"] = True
        text = data["body"] if data["body_type"] == "text" else ""
        if "Congratulations" in text and "Tor" in text:
            result["using_tor"] = True
        ip_match = re.search(
            r"IP address appears to be:\s*<strong>([\d.]+)</strong>", text, re.IGNORECASE
        )
        if ip_match:
            result["exit_ip"] = ip_match.group(1)
    except Exception as exc:
        result["error"] = str(exc)
    return result


def inject_tor_env(socks_proxy_url: str = DEFAULT_PROXY):
    """Enable Tor for this process and inherited child environments."""
    os.environ["TOR_PROXY"] = socks_proxy_url
    os.environ["TOR_ENABLED"] = "1"
    logger.info("Tor environment injected: TOR_ENABLED=1, TOR_PROXY=%s", socks_proxy_url)


def clear_tor_env():
    """Remove Tor environment variables."""
    os.environ.pop("TOR_PROXY", None)
    os.environ.pop("TOR_ENABLED", None)
    logger.info("Tor environment cleared")
