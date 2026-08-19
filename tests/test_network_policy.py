"""Regression tests for bounded, preservation-first strict mode."""

import subprocess

import pytest

from darkloom.policy import (
    CoverageStatus,
    NetworkChannel,
    NetworkPolicyError,
    authorize,
    authorize_raw_socket,
    authorize_subprocess,
    evaluate,
)


@pytest.fixture(autouse=True)
def strict_without_ambient_proxies(monkeypatch):
    monkeypatch.setenv("TOR_STRICT_MODE", "1")
    for key in ("TOR_PROXY", "ALL_PROXY", "HTTPS_PROXY", "HTTP_PROXY"):
        monkeypatch.delenv(key, raising=False)


@pytest.mark.parametrize(
    "channel",
    [NetworkChannel.UDP_VOICE, NetworkChannel.SMTP, NetworkChannel.IMAP, NetworkChannel.IRC],
)
def test_unsupported_upstream_channel_is_preserved(channel):
    decision = authorize(channel)
    assert decision.allowed is True
    assert decision.status is CoverageStatus.UNSUPPORTED_PRESERVED
    assert decision.darkloom_owned is False


def test_discord_voice_raw_socket_guard_does_not_disable_feature():
    decision = authorize_raw_socket(NetworkChannel.UDP_VOICE)
    assert decision.allowed is True
    assert decision.status is CoverageStatus.UNSUPPORTED_PRESERVED


def test_darkloom_cannot_claim_and_construct_unsupported_channel():
    with pytest.raises(NetworkPolicyError, match="cannot safely construct"):
        authorize(NetworkChannel.UDP_VOICE, darkloom_owned=True)


@pytest.mark.parametrize(
    "channel",
    [
        NetworkChannel.HTTP,
        NetworkChannel.MCP,
        NetworkChannel.GATEWAY,
        NetworkChannel.PLATFORM,
        NetworkChannel.BROWSER,
        NetworkChannel.WEB_TOOL,
        NetworkChannel.LLM,
        NetworkChannel.RAW_SOCKET,
    ],
)
def test_darkloom_owned_entry_points_still_fail_closed(channel):
    with pytest.raises(NetworkPolicyError):
        authorize(channel, proxy_aware=False)


def test_unknown_upstream_channel_is_preserved():
    decision = authorize("new_upstream_transport")
    assert decision.allowed is True
    assert decision.status is CoverageStatus.UNVERIFIED_PRESERVED


def test_unknown_darkloom_owned_channel_is_denied():
    with pytest.raises(NetworkPolicyError, match="unknown Darkloom-owned"):
        authorize("new_darkloom_transport", darkloom_owned=True)


def test_non_proxy_aware_subprocess_denied_before_launch(monkeypatch):
    launched = False

    def popen_spy(*args, **kwargs):
        nonlocal launched
        launched = True
        raise AssertionError("process launch must not be reached")

    monkeypatch.setattr(subprocess, "Popen", popen_spy)
    with pytest.raises(NetworkPolicyError, match="non-proxy-aware subprocess"):
        authorize_subprocess(proxy_aware=False)
    assert launched is False


def test_raw_socket_owned_by_darkloom_is_denied():
    with pytest.raises(NetworkPolicyError, match="non-proxy-aware raw_socket"):
        authorize_raw_socket()


def test_proxy_aware_darkloom_entry_points_are_allowed(monkeypatch):
    monkeypatch.setenv("TOR_PROXY", "socks5://127.0.0.1:9050")
    for channel in (
        NetworkChannel.HTTP,
        NetworkChannel.MCP,
        NetworkChannel.GATEWAY,
        NetworkChannel.PLATFORM,
        NetworkChannel.BROWSER,
        NetworkChannel.WEB_TOOL,
        NetworkChannel.LLM,
        NetworkChannel.SUBPROCESS,
    ):
        decision = authorize(channel)
        assert decision.status is CoverageStatus.VERIFIED


def test_proxy_requires_port(monkeypatch):
    monkeypatch.setenv("TOR_PROXY", "socks5://127.0.0.1")
    with pytest.raises(NetworkPolicyError, match="valid proxy"):
        authorize(NetworkChannel.HTTP)


def test_evaluate_has_no_side_effects():
    decision = evaluate(NetworkChannel.SMTP)
    assert decision.allowed
    assert decision.reason
