"""Regression tests for strict-mode fail-closed guarantees."""

import socket
import subprocess
from pathlib import Path

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
    with pytest.raises(TypeError, match="does not accept use_tor"):
        proxy_http.tor_get("https://example.test", use_tor=False)


def test_gateway_wrapper_refuses_non_proxy_aware_launch(monkeypatch):
    monkeypatch.setenv("TOR_PROXY", "socks5://127.0.0.1:9050")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("process launched"))
    with pytest.raises(NetworkPolicyError):
        authorize_subprocess(proxy_aware=False)


def test_gateway_command_must_be_verified_as_hermes_launcher(monkeypatch, tmp_path):
    from hermes_tor.gateway import _is_proxy_aware_gateway_command

    native = tmp_path / "native-helper"
    native.write_bytes(b"\x7fELF ignores proxy variables")
    native.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    assert not _is_proxy_aware_gateway_command(["native-helper", "gateway", "run"])

    launcher = tmp_path / "hermes"
    launcher.write_text("from hermes_cli.main import main\nmain()\n")
    launcher.chmod(0o755)
    assert _is_proxy_aware_gateway_command(["hermes", "gateway", "run"])
    assert not _is_proxy_aware_gateway_command(["hermes", "chat"])


def test_hermes_patch_guards_every_declared_network_entry_point():
    """Keep the integration patch in sync with the policy's channel list."""
    patch = (Path(__file__).parents[1] / "patches" /
             "0004-central-network-policy-fail-closed.patch").read_text()

    required_guards = {
        "Firecrawl": "authorize(\n+        NetworkChannel.WEB_TOOL",
        "auxiliary LLM": "NetworkChannel.LLM",
        "MCP": "NetworkChannel.MCP",
        "Discord voice": "authorize_raw_socket(NetworkChannel.UDP_VOICE)",
        "SMTP": "authorize_raw_socket(NetworkChannel.SMTP)",
        "IMAP": "authorize_raw_socket(NetworkChannel.IMAP)",
        "IRC": "authorize_raw_socket(NetworkChannel.IRC)",
        "Slack": "return authorized(proxy_url)",
        "execute_code": "execute_code process boundary before Popen",
    }
    for entry_point, guard in required_guards.items():
        assert guard in patch, f"missing policy guard for {entry_point}"


def test_hermes_patch_does_not_trust_ambient_proxy_for_children():
    patch = (Path(__file__).parents[1] / "patches" /
             "0004-central-network-policy-fail-closed.patch").read_text()

    assert 'if config.get("command") and not config.get("url"):' in patch
    assert patch.count("authorize_subprocess(proxy_aware=False") >= 2
    assert "execute_code process boundary before Popen" in patch


def test_hermes_patch_installs_llm_proxy_and_disables_webrtc_udp():
    patch = (Path(__file__).parents[1] / "patches" /
             "0004-central-network-policy-fail-closed.patch").read_text()

    assert 'for proxy_var in ("ALL_PROXY", "HTTPS_PROXY", "HTTP_PROXY")' in patch
    assert "proxy_aware=proxy_installed" in patch
    assert "--force-webrtc-ip-handling-policy=disable_non_proxied_udp" in patch


def test_slack_unsupported_proxy_is_a_strict_mode_denial():
    patch = (Path(__file__).parents[1] / "patches" /
             "0004-central-network-policy-fail-closed.patch").read_text()
    slack_hunk = patch[patch.index("diff --git a/plugins/platforms/slack/adapter.py"):]

    assert "return authorized(None)" in slack_hunk
    assert "proxy_aware=proxy is not None" in slack_hunk


@pytest.mark.parametrize("constructor", [
    '_wt._firecrawl_client = _wt.Firecrawl(**kwargs)',
    'imap = imaplib.IMAP4_SSL(',
])
def test_hermes_patch_authorizes_before_network_construction(constructor):
    patch = (Path(__file__).parents[1] / "patches" /
             "0004-central-network-policy-fail-closed.patch").read_text()
    constructor_offset = patch.index(constructor)
    preceding_hunk = patch[patch.rfind("@@", 0, constructor_offset):constructor_offset]
    assert "authorize" in preceding_hunk
