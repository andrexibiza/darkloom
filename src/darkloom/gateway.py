"""Hermes gateway integration with a bounded Darkloom ownership model.

The Tor lifecycle remains the mature implementation in ``_gateway_runtime``.
This module owns the current compatibility boundary: generic process proxies
are Darkloom-managed; platform-specific overrides remain upstream-owned; and
unverified Hermes transports are reported without being disabled.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional
from urllib.parse import urlsplit

from darkloom import _gateway_runtime as _runtime
from darkloom.constants import DEFAULT_SOCKS_PORT

logger = logging.getLogger(__name__)

_GENERIC_PROXY_NAMES = ("ALL_PROXY", "HTTPS_PROXY", "HTTP_PROXY", "TOR_PROXY")
_PLATFORM_PROXY_NAMES = (
    "TELEGRAM_PROXY",
    "DISCORD_PROXY",
    "MATRIX_PROXY",
    "PHOTON_PROXY",
    "WHATSAPP_PROXY",
    "SLACK_PROXY",
    "GRPC_PROXY",
)
PROXY_ENV_VARS = tuple(
    dict.fromkeys(
        name
        for upper in _GENERIC_PROXY_NAMES
        for name in (upper, upper.lower())
    )
)
OBSERVED_PLATFORM_PROXY_VARS = tuple(
    dict.fromkeys(
        name
        for upper in _PLATFORM_PROXY_NAMES
        for name in (upper, upper.lower())
    )
)
NO_PROXY_ENV_VARS = ("NO_PROXY", "no_proxy")


@dataclass(frozen=True)
class ProxyPolicy:
    """One immutable routing decision for Darkloom-owned process traffic."""

    url: str
    strict: bool
    loopback_bypass: tuple[str, ...] = ("localhost", "127.0.0.1", "::1")


class ProxyPolicyError(RuntimeError):
    """The Darkloom-owned process environment violates proxy policy."""


def _strict_mode(environment: Mapping[str, str]) -> bool:
    return environment.get("TOR_STRICT_MODE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _validate_no_proxy(value: str, name: str, policy: ProxyPolicy) -> None:
    if not value.strip() or not policy.strict:
        return
    entries = {
        part.strip().strip("[]").lower()
        for part in value.split(",")
        if part.strip()
    }
    if not entries.issubset(policy.loopback_bypass):
        raise ProxyPolicyError(
            f"{name} may contain only {', '.join(policy.loopback_bypass)} in strict mode"
        )


def _validate_generic_proxy(name: str, value: str, policy: ProxyPolicy) -> None:
    candidate = value.strip()
    if not candidate:
        raise ProxyPolicyError(f"{name} is set but empty")
    if candidate.lower() in {"direct", "direct://", "none", "off"}:
        raise ProxyPolicyError(f"{name} disables Darkloom proxy routing")
    parsed = urlsplit(candidate)
    if parsed.scheme not in {"socks5", "socks5h"} or not parsed.hostname or parsed.port is None:
        raise ProxyPolicyError(f"{name} has an unsupported proxy value: {candidate!r}")
    if candidate != policy.url:
        raise ProxyPolicyError(
            f"{name} conflicts with immutable Darkloom proxy policy {policy.url!r}"
        )


def establish_proxy_policy(
    socks_port: int = DEFAULT_SOCKS_PORT,
    *,
    strict: Optional[bool] = None,
    environment: Optional[Mapping[str, str]] = None,
) -> ProxyPolicy:
    """Validate only environment variables that Darkloom owns.

    Platform-specific proxy variables are upstream routing state. Darkloom
    observes them for reporting but does not overwrite or reject them merely
    because they are unsupported or unverified.
    """

    env = os.environ if environment is None else environment
    if not 1 <= socks_port <= 65535:
        raise ProxyPolicyError(f"invalid SOCKS port: {socks_port}")
    policy = ProxyPolicy(
        url=f"socks5://127.0.0.1:{socks_port}",
        strict=_strict_mode(env) if strict is None else strict,
    )
    if policy.strict:
        for name in NO_PROXY_ENV_VARS:
            if name in env:
                _validate_no_proxy(env[name], name, policy)
        for name in PROXY_ENV_VARS:
            if name in env:
                _validate_generic_proxy(name, env[name], policy)
    return policy


def _policy_environment(
    policy: ProxyPolicy,
    environment: Optional[Mapping[str, str]] = None,
) -> dict[str, str]:
    del environment  # Platform-specific variables remain untouched by design.
    values = {name: policy.url for name in PROXY_ENV_VARS}
    values.update(
        {
            "TOR_PROXY": policy.url,
            "tor_proxy": policy.url,
            "TOR_ENABLED": "1",
            "NO_PROXY": ",".join(policy.loopback_bypass),
            "no_proxy": ",".join(policy.loopback_bypass),
        }
    )
    return values


def require_verified_proxy_clients(
    policy: ProxyPolicy,
    *client_names: str,
) -> tuple[str, ...]:
    """Report unverified upstream clients without disabling their features."""

    if not policy.strict:
        return ()
    gaps = tuple(sorted(set(client_names) - {"httpx"}))
    if gaps:
        logger.warning(
            "Darkloom has no runtime routing proof for upstream clients: %s; "
            "native Hermes behavior is preserved",
            ", ".join(gaps),
        )
    return gaps


GATEWAY_ENV_VARS = _policy_environment(
    ProxyPolicy(f"socks5://127.0.0.1:{DEFAULT_SOCKS_PORT}", strict=False)
)
GATEWAY_ENV_VARS["TOR_HEALTH"] = "1"

# Patch the mature runtime module's global seams before exposing its lifecycle.
_runtime.ProxyPolicy = ProxyPolicy
_runtime.ProxyPolicyError = ProxyPolicyError
_runtime._GENERIC_PROXY_NAMES = _GENERIC_PROXY_NAMES
_runtime._PLATFORM_PROXY_NAMES = _PLATFORM_PROXY_NAMES
_runtime.PROXY_ENV_VARS = PROXY_ENV_VARS
_runtime.NO_PROXY_ENV_VARS = NO_PROXY_ENV_VARS
_runtime._strict_mode = _strict_mode
_runtime._policy_environment = _policy_environment
_runtime.establish_proxy_policy = establish_proxy_policy
_runtime.require_verified_proxy_clients = require_verified_proxy_clients
_runtime.GATEWAY_ENV_VARS = GATEWAY_ENV_VARS

inject_gateway_env = _runtime.inject_gateway_env
clear_gateway_env = _runtime.clear_gateway_env
block_gateway_env = _runtime.block_gateway_env
create_httpx_client = _runtime.create_httpx_client
skip_llm_proxy = _runtime.skip_llm_proxy
is_llm_skipped = _runtime.is_llm_skipped
write_gateway_env_file = _runtime.write_gateway_env_file
remove_gateway_env_file = _runtime.remove_gateway_env_file
TorWatchdog = _runtime.TorWatchdog
is_tor_installed = _runtime.is_tor_installed
_is_proxy_aware_gateway_command = _runtime._is_proxy_aware_gateway_command


def start_tor_for_gateway(*args, **kwargs):
    """Start Darkloom's verified Tor boundary, preserving upstream features.

    Keep the mature runtime's patchable seams synchronized with this public
    module. This preserves existing callers and tests that monkeypatch
    ``darkloom.gateway.is_tor_installed`` or
    ``darkloom.gateway.require_verified_proxy_clients`` before startup.
    """

    _runtime.is_tor_installed = is_tor_installed
    _runtime.require_verified_proxy_clients = require_verified_proxy_clients
    return _runtime.start_tor_for_gateway(*args, **kwargs)


def main() -> None:
    """Start Tor, then run a known proxy-aware Hermes gateway command."""

    import argparse

    parser = argparse.ArgumentParser(
        description="Start Darkloom Tor, then launch the Hermes gateway"
    )
    parser.add_argument("--port", type=int, default=DEFAULT_SOCKS_PORT)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--no-env-file", action="store_true")
    parser.add_argument("gateway_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    gateway_cmd = list(args.gateway_args)
    if gateway_cmd and gateway_cmd[0] == "--":
        gateway_cmd = gateway_cmd[1:]
    if not gateway_cmd:
        parser.error("expected a Hermes gateway command after --")

    manager = start_tor_for_gateway(
        socks_port=args.port,
        bootstrap_timeout=args.timeout,
        write_env=not args.no_env_file,
    )
    print(f"[darkloom] verified Tor SOCKS boundary on 127.0.0.1:{args.port}")
    print(
        "[darkloom] native Hermes transports outside the verified boundary "
        "remain enabled without a Darkloom routing claim"
    )
    try:
        from darkloom.policy import authorize_subprocess

        authorize_subprocess(proxy_aware=_is_proxy_aware_gateway_command(gateway_cmd))
        result = subprocess.run(gateway_cmd)
        raise SystemExit(result.returncode)
    finally:
        watchdog = getattr(manager, "_watchdog", None)
        if watchdog:
            watchdog.stop()
        manager.stop()
        clear_gateway_env()


__all__ = [
    "GATEWAY_ENV_VARS",
    "NO_PROXY_ENV_VARS",
    "OBSERVED_PLATFORM_PROXY_VARS",
    "PROXY_ENV_VARS",
    "ProxyPolicy",
    "ProxyPolicyError",
    "TorWatchdog",
    "block_gateway_env",
    "clear_gateway_env",
    "create_httpx_client",
    "establish_proxy_policy",
    "inject_gateway_env",
    "is_llm_skipped",
    "is_tor_installed",
    "main",
    "remove_gateway_env_file",
    "require_verified_proxy_clients",
    "skip_llm_proxy",
    "start_tor_for_gateway",
    "write_gateway_env_file",
]


if __name__ == "__main__":
    main()
