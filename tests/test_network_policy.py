"""Regression tests for strict-mode fail-closed guarantees."""

import socket
import subprocess

import pytest

from hermes_tor.policy import (
    NetworkChannel,
    NetworkPolicyError,
    authorize,
    authorize_raw_socket,
    authorize_subprocess,
)


@pytest.fixture(autouse=True)
def strict_without_ambient_proxies(monkeypatch):
    monkeypatch.setenv("TOR_STRICT_MODE", "1")
    for key in ("TOR_PROXY", "ALL_PROXY", "HTTPS_PROXY", "HTTP_PROXY"):
        monkeypatch.delenv(key, raising=False)


@pytest.mark.parametrize("channel", [
    NetworkChannel.UDP_VOICE,
    NetworkChannel.SMTP,
    NetworkChannel.IMAP,
    NetworkChannel.IRC,
])
def test_unsupported_channel_is_denied_before_socket_creation(monkeypatch, channel):
    opened = False

    def socket_spy(*args, **kwargs):
        nonlocal opened
        opened = True
        raise AssertionError("socket creation must not be reached")

    monkeypatch.setattr(socket, "socket", socket_spy)
    with pytest.raises(NetworkPolicyError, match="unsupported channel"):
        authorize(channel)
    assert opened is False


@pytest.mark.parametrize("channel", [
    NetworkChannel.HTTP,
    NetworkChannel.MCP,
    NetworkChannel.GATEWAY,
    NetworkChannel.PLATFORM,
    NetworkChannel.BROWSER,
    NetworkChannel.WEB_TOOL,
    NetworkChannel.LLM,
    NetworkChannel.RAW_SOCKET,
])
def test_every_direct_network_entry_point_defaults_to_deny(channel):
    with pytest.raises(NetworkPolicyError):
        authorize(channel, proxy_aware=False)


def test_unknown_channel_defaults_to_deny():
    with pytest.raises(NetworkPolicyError, match="unknown network channel"):
        authorize("new_unreviewed_transport")


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


def test_raw_socket_adapter_denied_before_socket_creation(monkeypatch):
    monkeypatch.setattr(socket, "socket", lambda *a, **k: pytest.fail("socket opened"))
    with pytest.raises(NetworkPolicyError, match="non-proxy-aware raw_socket"):
        authorize_raw_socket()


def test_proxy_aware_entry_points_are_explicitly_allowed(monkeypatch):
    monkeypatch.setenv("TOR_PROXY", "socks5://127.0.0.1:9050")
    for channel in (
        NetworkChannel.HTTP, NetworkChannel.MCP, NetworkChannel.GATEWAY,
        NetworkChannel.PLATFORM, NetworkChannel.BROWSER, NetworkChannel.WEB_TOOL,
        NetworkChannel.LLM, NetworkChannel.SUBPROCESS,
    ):
        authorize(channel)


def test_proxy_http_refuses_direct_client_before_httpx_construction(monkeypatch):
    from hermes_tor import proxy_http

    monkeypatch.setattr(proxy_http.httpx, "Client", lambda *a, **k: pytest.fail("client created"))
    with pytest.raises(NetworkPolicyError):
        proxy_http.tor_get("https://example.test", use_tor=False)


def test_gateway_wrapper_refuses_non_proxy_aware_launch(monkeypatch):
    monkeypatch.setenv("TOR_PROXY", "socks5://127.0.0.1:9050")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("process launched"))
    with pytest.raises(NetworkPolicyError):
        authorize_subprocess(proxy_aware=False)
