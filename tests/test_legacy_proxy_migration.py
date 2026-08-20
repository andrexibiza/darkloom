"""Regression tests for migration from Darkloom-owned platform proxy keys."""

from __future__ import annotations

import os
from pathlib import Path

from darkloom import gateway


def _active_assignments(path: Path) -> dict[str, str]:
    assignments: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parsed = gateway._dotenv_assignment(line)
        if parsed is not None:
            key, value = parsed
            assignments[key] = value
    return assignments


def _legacy_dotenv(proxy: str) -> str:
    values = {name: proxy for name in gateway.OBSERVED_PLATFORM_PROXY_VARS}
    values.update(
        {
            "ALL_PROXY": proxy,
            "HTTP_PROXY": proxy,
            "HTTPS_PROXY": proxy,
            "TOR_PROXY": proxy,
            "TOR_ENABLED": "1",
            "TOR_HEALTH": "1",
        }
    )
    return "TOKEN=keep-me\n" + "".join(
        f"{key}={value}\n" for key, value in sorted(values.items())
    )


def test_write_retires_only_complete_legacy_platform_proxy_footprint(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        _legacy_dotenv("socks5://127.0.0.1:9050"),
        encoding="utf-8",
    )

    gateway.write_gateway_env_file(19050, env_path=env_path)

    content = env_path.read_text(encoding="utf-8")
    assignments = _active_assignments(env_path)
    assert assignments["TOKEN"] == "keep-me"
    assert assignments["ALL_PROXY"] == "socks5://127.0.0.1:19050"
    assert not set(gateway.OBSERVED_PLATFORM_PROXY_VARS) & assignments.keys()
    assert content.count(gateway._LEGACY_PROXY_COMMENT) == len(
        gateway.OBSERVED_PLATFORM_PROXY_VARS
    )


def test_write_preserves_partial_or_user_authored_platform_proxy_state(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "SLACK_PROXY=http://127.0.0.1:8118\n"
        "DISCORD_PROXY=socks5://127.0.0.1:9150\n"
        "TOKEN=keep-me\n",
        encoding="utf-8",
    )

    gateway.write_gateway_env_file(19050, env_path=env_path)

    assignments = _active_assignments(env_path)
    assert assignments["SLACK_PROXY"] == "http://127.0.0.1:8118"
    assert assignments["DISCORD_PROXY"] == "socks5://127.0.0.1:9150"
    assert assignments["TOKEN"] == "keep-me"
    assert gateway._LEGACY_PROXY_COMMENT not in env_path.read_text(encoding="utf-8")


def test_inject_retires_complete_legacy_process_footprint(monkeypatch):
    old_proxy = "socks5://127.0.0.1:9050"
    for name in gateway.OBSERVED_PLATFORM_PROXY_VARS:
        monkeypatch.setenv(name, old_proxy)
    monkeypatch.setenv("TOR_ENABLED", "1")

    policy = gateway.ProxyPolicy(
        "socks5://127.0.0.1:19050",
        strict=False,
    )
    gateway.inject_gateway_env(19050, policy=policy)
    try:
        for name in gateway.OBSERVED_PLATFORM_PROXY_VARS:
            assert name not in os.environ
        assert os.environ["ALL_PROXY"] == policy.url
    finally:
        gateway.clear_gateway_env()
