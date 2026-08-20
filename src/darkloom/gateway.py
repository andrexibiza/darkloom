"""Hermes gateway integration with a bounded Darkloom ownership model.

The Tor lifecycle remains the mature implementation in ``_gateway_runtime``.
This module owns the current compatibility boundary: generic process proxies
are Darkloom-managed; platform-specific overrides remain upstream-owned; and
unverified Hermes transports are reported without being disabled.
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, MutableMapping, Optional
from urllib.parse import urlsplit

from darkloom import _gateway_runtime as _runtime
from darkloom.constants import DEFAULT_SOCKS_PORT
from darkloom.secure_files import atomic_private_write, private_lock

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
_LEGACY_PROXY_COMMENT = "# darkloom-retired-legacy-platform-proxy: "


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
    try:
        port = parsed.port
    except ValueError as exc:
        raise ProxyPolicyError(
            f"{name} has an unsupported proxy value: {candidate!r}"
        ) from exc
    if (
        parsed.scheme not in {"socks5", "socks5h"}
        or not parsed.hostname
        or port is None
    ):
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


def _is_local_socks_proxy(value: str) -> bool:
    parsed = urlsplit(value.strip())
    try:
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme.lower() in {"socks5", "socks5h"}
        and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        and port is not None
    )


def _legacy_platform_proxy_value(
    values: Mapping[str, str],
    *,
    require_case_variants: bool = True,
) -> str | None:
    """Recognize only the complete footprint written by older Darkloom releases.

    A partial set may be user-authored upstream configuration and is preserved.
    """

    if values.get("TOR_ENABLED", "").strip().lower() not in {"1", "true", "yes", "on"}:
        return None
    names = OBSERVED_PLATFORM_PROXY_VARS if require_case_variants else _PLATFORM_PROXY_NAMES
    if not all(name in values for name in names):
        return None
    candidates = {values[name].strip() for name in names}
    if len(candidates) != 1:
        return None
    candidate = next(iter(candidates))
    return candidate if _is_local_socks_proxy(candidate) else None


def _retire_legacy_process_platform_proxies(
    environment: MutableMapping[str, str],
) -> tuple[str, ...]:
    proxy = _legacy_platform_proxy_value(environment)
    if proxy is None:
        return ()
    retired: list[str] = []
    for name in OBSERVED_PLATFORM_PROXY_VARS:
        if name in environment and environment.get(name, "").strip() == proxy:
            environment.pop(name, None)
            retired.append(name)
    return tuple(retired)


def _dotenv_assignment(line: str) -> tuple[str, str] | None:
    candidate = line.lstrip()
    if not candidate or candidate.startswith("#"):
        return None
    if candidate.startswith("export "):
        candidate = candidate[7:].lstrip()
    key, separator, value = candidate.partition("=")
    if not separator:
        return None
    return key.strip(), value.strip()


def _retire_legacy_dotenv_platform_proxies(
    lines: list[str],
) -> tuple[list[str], tuple[str, ...]]:
    occurrences: dict[str, list[tuple[int, str]]] = {}
    tor_enabled = ""
    for index, line in enumerate(lines):
        assignment = _dotenv_assignment(line)
        if assignment is None:
            continue
        key, value = assignment
        occurrences.setdefault(key, []).append((index, value))
        if key == "TOR_ENABLED":
            tor_enabled = value

    values: dict[str, str] = {"TOR_ENABLED": tor_enabled}
    for name in OBSERVED_PLATFORM_PROXY_VARS:
        matches = occurrences.get(name, [])
        if len(matches) != 1:
            return lines, ()
        values[name] = matches[0][1]

    proxy = _legacy_platform_proxy_value(values)
    if proxy is None:
        return lines, ()

    retired: list[str] = []
    migrated = list(lines)
    for name in OBSERVED_PLATFORM_PROXY_VARS:
        index, value = occurrences[name][0]
        if value != proxy:
            return lines, ()
        original = migrated[index]
        newline = "\n" if original.endswith("\n") else ""
        payload = original[:-1] if newline else original
        migrated[index] = f"{_LEGACY_PROXY_COMMENT}{payload}{newline}"
        retired.append(name)
    return migrated, tuple(retired)


GATEWAY_ENV_VARS = _policy_environment(
    ProxyPolicy(f"socks5://127.0.0.1:{DEFAULT_SOCKS_PORT}", strict=False)
)
GATEWAY_ENV_VARS["TOR_HEALTH"] = "1"

# Keep references to the mature implementation before replacing its public seams.
_runtime_inject_gateway_env = _runtime.inject_gateway_env
_runtime_clear_gateway_env = _runtime.clear_gateway_env
_runtime_block_gateway_env = _runtime.block_gateway_env
create_httpx_client = _runtime.create_httpx_client
skip_llm_proxy = _runtime.skip_llm_proxy
is_llm_skipped = _runtime.is_llm_skipped
TorWatchdog = _runtime.TorWatchdog
is_tor_installed = _runtime.is_tor_installed
_is_proxy_aware_gateway_command = _runtime._is_proxy_aware_gateway_command


def inject_gateway_env(
    socks_port: int = DEFAULT_SOCKS_PORT,
    *,
    policy: Optional[ProxyPolicy] = None,
) -> ProxyPolicy:
    retired = _retire_legacy_process_platform_proxies(os.environ)
    if retired:
        logger.warning(
            "Retired %d legacy Darkloom-owned platform proxy variables; "
            "platform routing is upstream-owned",
            len(retired),
        )
    return _runtime_inject_gateway_env(socks_port, policy=policy)


def clear_gateway_env() -> None:
    _runtime_clear_gateway_env()
    retired = _retire_legacy_process_platform_proxies(os.environ)
    if retired:
        logger.warning(
            "Retired %d restored legacy Darkloom-owned platform proxy variables",
            len(retired),
        )


def block_gateway_env() -> None:
    _retire_legacy_process_platform_proxies(os.environ)
    _runtime_block_gateway_env()


def write_gateway_env_file(
    socks_port: int = DEFAULT_SOCKS_PORT,
    env_path: Optional[Path] = None,
    healthy: bool = True,
) -> None:
    """Persist current generic proxy state and retire a proven legacy footprint."""

    path = Path.home() / ".hermes" / ".env" if env_path is None else Path(env_path)
    proxy_url = f"socks5://127.0.0.1:{socks_port}"
    tor_vars = _policy_environment(ProxyPolicy(proxy_url, strict=False), environment={})
    tor_vars["TOR_HEALTH"] = "1" if healthy else "0"
    if not healthy:
        tor_vars["TOR_ENABLED"] = "0"

    with private_lock(path):
        if path.is_symlink():
            raise OSError(f"refusing symbolic link: {path}")
        existing_lines = path.read_text().splitlines(keepends=True) if path.exists() else []
        migrated_lines, retired = _retire_legacy_dotenv_platform_proxies(existing_lines)
        retained = [
            line
            for line in migrated_lines
            if (_dotenv_assignment(line) or (None, None))[0] not in tor_vars
        ]
        if retained and not retained[-1].endswith(("\n", "\r")):
            retained[-1] += "\n"
        content = "".join(retained) + "".join(
            f"{key}={value}\n" for key, value in sorted(tor_vars.items())
        )
        atomic_private_write(path, content)

    if retired:
        logger.warning(
            "Retired %d legacy Darkloom-generated platform proxy assignments in %s",
            len(retired),
            path,
        )


def remove_gateway_env_file(env_path: Optional[Path] = None) -> None:
    """Remove current Darkloom keys and retire a proven legacy platform footprint."""

    path = Path.home() / ".hermes" / ".env" if env_path is None else Path(env_path)
    with private_lock(path):
        if path.is_symlink():
            raise OSError(f"refusing symbolic link: {path}")
        if not path.exists():
            return
        existing_lines = path.read_text().splitlines(keepends=True)
        migrated_lines, retired = _retire_legacy_dotenv_platform_proxies(existing_lines)
        managed = set(
            _policy_environment(
                ProxyPolicy(
                    f"socks5://127.0.0.1:{DEFAULT_SOCKS_PORT}",
                    strict=False,
                ),
                environment={},
            )
        ) | {"TOR_HEALTH"}
        content = "".join(
            line
            for line in migrated_lines
            if (_dotenv_assignment(line) or (None, None))[0] not in managed
        )
        atomic_private_write(path, content)

    if retired:
        logger.warning(
            "Retired %d legacy Darkloom-generated platform proxy assignments in %s",
            len(retired),
            path,
        )


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
_runtime.inject_gateway_env = inject_gateway_env
_runtime.clear_gateway_env = clear_gateway_env
_runtime.block_gateway_env = block_gateway_env
_runtime.write_gateway_env_file = write_gateway_env_file
_runtime.remove_gateway_env_file = remove_gateway_env_file


def start_tor_for_gateway(*args, **kwargs):
    """Start Darkloom's verified Tor boundary, preserving upstream features.

    Keep the mature runtime's patchable seams synchronized with this public
    module. This preserves existing callers and tests that monkeypatch
    ``darkloom.gateway.is_tor_installed`` or
    ``darkloom.gateway.require_verified_proxy_clients`` before startup.
    """

    _retire_legacy_process_platform_proxies(os.environ)
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
