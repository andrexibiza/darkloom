"""Bounded, preservation-first network policy for Darkloom-owned operations.

Strict mode is intentionally scoped. Darkloom fails closed for network I/O it
constructs or explicitly governs, but it does not disable native Hermes
capabilities merely because Darkloom has not verified their routing. Those
surfaces remain available and are reported as ``unsupported_preserved`` or
``unverified_preserved``.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class NetworkPolicyError(PermissionError):
    """Raised before a Darkloom-owned operation would violate policy."""


class NetworkChannel(str, Enum):
    HTTP = "http"
    MCP = "mcp"
    GATEWAY = "gateway"
    PLATFORM = "platform"
    BROWSER = "browser"
    WEB_TOOL = "web_tool"
    LLM = "llm"
    SUBPROCESS = "subprocess"
    RAW_SOCKET = "raw_socket"
    UDP_VOICE = "udp_voice"
    SMTP = "smtp"
    IMAP = "imap"
    IRC = "irc"
    TOR_BOOTSTRAP = "tor_bootstrap"
    TOR_CONTROL = "tor_control"


class CoverageStatus(str, Enum):
    VERIFIED = "verified"
    DARKLOOM_REQUIRED = "darkloom_required"
    UPSTREAM_NATIVE = "upstream_native"
    UNSUPPORTED_PRESERVED = "unsupported_preserved"
    UNVERIFIED_PRESERVED = "unverified_preserved"
    DIRECT_BOOTSTRAP = "direct_bootstrap"


@dataclass(frozen=True)
class NetworkDecision:
    channel: str
    allowed: bool
    status: CoverageStatus
    reason: str
    darkloom_owned: bool
    proxy_url: str | None = None


_PROXY_REQUIRED = {
    NetworkChannel.HTTP,
    NetworkChannel.MCP,
    NetworkChannel.GATEWAY,
    NetworkChannel.PLATFORM,
    NetworkChannel.BROWSER,
    NetworkChannel.WEB_TOOL,
    NetworkChannel.LLM,
    NetworkChannel.SUBPROCESS,
    NetworkChannel.RAW_SOCKET,
}
_UNSUPPORTED_PRESERVED = {
    NetworkChannel.UDP_VOICE,
    NetworkChannel.SMTP,
    NetworkChannel.IMAP,
    NetworkChannel.IRC,
}
_EXPLICIT_DIRECT = {NetworkChannel.TOR_BOOTSTRAP, NetworkChannel.TOR_CONTROL}
_TRUE = {"1", "true", "yes", "on"}


def is_strict_mode() -> bool:
    return os.environ.get("TOR_STRICT_MODE", "").strip().lower() in _TRUE


def enable_strict_mode() -> None:
    """Activate fail-closed policy for Darkloom-owned operations."""
    os.environ["TOR_STRICT_MODE"] = "1"


def configured_proxy() -> str | None:
    for key in ("TOR_PROXY", "ALL_PROXY", "HTTPS_PROXY", "HTTP_PROXY"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return None


def _valid_proxy(proxy_url: str | None) -> bool:
    if not proxy_url:
        return False
    parsed = urlparse(proxy_url)
    return (
        parsed.scheme.lower() in {"socks5", "socks5h", "http", "https"}
        and bool(parsed.hostname)
        and parsed.port is not None
    )


def evaluate(
    channel: NetworkChannel | str,
    *,
    proxy_url: str | None = None,
    proxy_aware: bool = True,
    local_only: bool = False,
    darkloom_owned: bool | None = None,
) -> NetworkDecision:
    """Return the policy decision without performing I/O.

    ``darkloom_owned`` is authoritative when supplied. When omitted, known
    Darkloom client channels are treated as owned, while unknown and explicitly
    unsupported Hermes channels are preserved rather than captured by policy.
    ``local_only`` is descriptive and never acts as a bypass.
    """
    raw = getattr(channel, "value", channel)
    name = str(raw)
    try:
        selected = NetworkChannel(channel)
    except ValueError:
        owned = bool(darkloom_owned)
        if is_strict_mode() and owned:
            return NetworkDecision(
                name,
                False,
                CoverageStatus.DARKLOOM_REQUIRED,
                f"strict mode denies unknown Darkloom-owned network channel: {name}",
                True,
            )
        return NetworkDecision(
            name,
            True,
            CoverageStatus.UNVERIFIED_PRESERVED,
            "unknown upstream capability preserved; no Darkloom routing claim",
            owned,
        )

    if selected in _UNSUPPORTED_PRESERVED:
        owned = bool(darkloom_owned)
        if is_strict_mode() and owned:
            return NetworkDecision(
                selected.value,
                False,
                CoverageStatus.DARKLOOM_REQUIRED,
                f"Darkloom cannot safely construct unsupported channel: {selected.value}",
                True,
            )
        return NetworkDecision(
            selected.value,
            True,
            CoverageStatus.UNSUPPORTED_PRESERVED,
            "native Hermes capability preserved outside Darkloom's verified boundary",
            False,
        )

    if selected in _EXPLICIT_DIRECT:
        return NetworkDecision(
            selected.value,
            True,
            CoverageStatus.DIRECT_BOOTSTRAP,
            "explicit Tor bootstrap/control path",
            True,
        )

    owned = selected in _PROXY_REQUIRED if darkloom_owned is None else darkloom_owned
    if not is_strict_mode():
        return NetworkDecision(
            selected.value,
            True,
            CoverageStatus.DARKLOOM_REQUIRED if owned else CoverageStatus.UPSTREAM_NATIVE,
            "strict mode disabled",
            owned,
            proxy_url or configured_proxy(),
        )

    if not owned:
        return NetworkDecision(
            selected.value,
            True,
            CoverageStatus.UNVERIFIED_PRESERVED,
            "upstream-owned capability preserved; no Darkloom routing claim",
            False,
        )
    if selected not in _PROXY_REQUIRED:
        return NetworkDecision(
            selected.value,
            False,
            CoverageStatus.DARKLOOM_REQUIRED,
            f"strict mode has no allow rule for Darkloom-owned {selected.value}",
            True,
        )
    if not proxy_aware:
        return NetworkDecision(
            selected.value,
            False,
            CoverageStatus.DARKLOOM_REQUIRED,
            f"strict mode denies non-proxy-aware {selected.value}",
            True,
        )
    proxy = proxy_url or configured_proxy()
    if not _valid_proxy(proxy):
        return NetworkDecision(
            selected.value,
            False,
            CoverageStatus.DARKLOOM_REQUIRED,
            f"strict mode requires a valid proxy for {selected.value}",
            True,
            proxy,
        )
    return NetworkDecision(
        selected.value,
        True,
        CoverageStatus.VERIFIED,
        "Darkloom-owned operation has an explicit proxy transport",
        True,
        proxy,
    )


def authorize(
    channel: NetworkChannel | str,
    *,
    proxy_url: str | None = None,
    proxy_aware: bool = True,
    local_only: bool = False,
    darkloom_owned: bool | None = None,
) -> NetworkDecision:
    """Authorize an operation and return its typed coverage decision."""
    decision = evaluate(
        channel,
        proxy_url=proxy_url,
        proxy_aware=proxy_aware,
        local_only=local_only,
        darkloom_owned=darkloom_owned,
    )
    if not decision.allowed:
        raise NetworkPolicyError(decision.reason)
    if decision.status in {
        CoverageStatus.UNSUPPORTED_PRESERVED,
        CoverageStatus.UNVERIFIED_PRESERVED,
    }:
        logger.warning("%s: %s", decision.channel, decision.reason)
    return decision


def authorize_subprocess(*, proxy_aware: bool, proxy_url: str | None = None) -> NetworkDecision:
    """Authorize a Darkloom-owned child launch before ``Popen``/``run``."""
    return authorize(
        NetworkChannel.SUBPROCESS,
        proxy_aware=proxy_aware,
        proxy_url=proxy_url,
        darkloom_owned=True,
    )


def authorize_raw_socket(
    channel: NetworkChannel | str = NetworkChannel.RAW_SOCKET,
    *,
    darkloom_owned: bool | None = None,
) -> NetworkDecision:
    """Authorize a raw socket without capturing unsupported Hermes features."""
    if darkloom_owned is None:
        try:
            selected = NetworkChannel(channel)
        except ValueError:
            selected = None
        darkloom_owned = selected not in _UNSUPPORTED_PRESERVED
    return authorize(channel, proxy_aware=False, darkloom_owned=darkloom_owned)
