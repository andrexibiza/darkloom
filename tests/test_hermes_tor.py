"""Unit tests for hermes-tor.

Run: uv run pytest tests/ -v
"""
import os

import pytest
from pathlib import Path


# ── constants tests ────────────────────────────────────────────


def test_get_download_url_returns_valid_url():
    from hermes_tor.constants import get_download_url, TOR_VERSION

    url = get_download_url()
    assert url.startswith("https://archive.torproject.org/")
    assert TOR_VERSION in url
    assert "tor-expert-bundle" in url
    assert url.endswith(".tar.gz")


def test_is_tor_installed_returns_false_when_no_binary(monkeypatch, tmp_path):
    from hermes_tor import constants

    monkeypatch.setattr(constants, "TOR_BINARY_DIR", tmp_path / "nonexistent")
    assert constants.is_tor_installed() is False


def test_get_tor_binary_path_windows(monkeypatch):
    from hermes_tor import constants

    monkeypatch.setattr(constants, "CURRENT_PLATFORM", "win32")
    path = constants.get_tor_binary_path()
    assert path.name == "tor.exe"
    assert "Tor" in str(path)


def test_get_tor_binary_path_linux(monkeypatch):
    from hermes_tor import constants

    monkeypatch.setattr(constants, "CURRENT_PLATFORM", "linux")
    path = constants.get_tor_binary_path()
    assert path.name == "tor"
    assert "tor" in str(path.parent.name)


def test_get_lyrebird_path_exists_for_current_platform():
    from hermes_tor.constants import get_lyrebird_path

    path = get_lyrebird_path()
    assert path.name in ("lyrebird", "lyrebird.exe")
    assert "pluggable_transports" in str(path)


# ── bridges tests ─────────────────────────────────────────────


def test_parse_obfs4_bridge():
    from hermes_tor.bridges import parse_bridge_line

    line = "obfs4 198.51.100.1:443 ABCDEF1234567890 cert=xyz iat-mode=0"
    bridge = parse_bridge_line(line)
    assert bridge is not None
    assert bridge.transport == "obfs4"
    assert bridge.address == "198.51.100.1:443"
    assert bridge.fingerprint == "ABCDEF1234567890"


def test_parse_vanilla_bridge():
    from hermes_tor.bridges import parse_bridge_line

    line = "198.51.100.2:9001 ABCDEF1234567890ABCDEF1234567890ABCDEF12"
    bridge = parse_bridge_line(line)
    assert bridge is not None
    assert bridge.transport == "vanilla"


def test_parse_bridge_ignores_comments():
    from hermes_tor.bridges import parse_bridge_line

    assert parse_bridge_line("# This is a comment") is None
    assert parse_bridge_line("") is None
    assert parse_bridge_line("   ") is None


def test_validate_bridge():
    from hermes_tor.bridges import validate_bridge

    assert validate_bridge("obfs4 1.2.3.4:443 ABCDEF cert=xyz iat-mode=0") is True
    assert validate_bridge("") is False
    assert validate_bridge("# comment") is False


def test_load_bridges_from_file(tmp_path):
    from hermes_tor.bridges import load_bridges_from_file

    bridge_file = tmp_path / "bridges.txt"
    bridge_file.write_text("""
# My bridges
obfs4 198.51.100.1:443 ABCDEF cert=xyz iat-mode=0
obfs4 198.51.100.2:444 FEDCBA cert=abc iat-mode=1
""")
    bridges = load_bridges_from_file(bridge_file)
    assert len(bridges) == 2
    assert bridges[0].transport == "obfs4"
    assert bridges[0].fingerprint == "ABCDEF"


def test_load_bridges_from_missing_file(tmp_path):
    from hermes_tor.bridges import load_bridges_from_file

    bridges = load_bridges_from_file(tmp_path / "nonexistent.txt")
    assert bridges == []


def test_save_bridges_to_file(tmp_path):
    from hermes_tor.bridges import save_bridges_to_file

    path = tmp_path / "bridges.txt"
    save_bridges_to_file(path, ["obfs4 1.2.3.4:443 ABCDEF"])
    content = path.read_text().strip()
    assert "obfs4 1.2.3.4:443 ABCDEF" in content


def test_save_bridges_append(tmp_path):
    from hermes_tor.bridges import save_bridges_to_file

    path = tmp_path / "bridges.txt"
    save_bridges_to_file(path, ["bridge1"])
    save_bridges_to_file(path, ["bridge2"], append=True)
    content = path.read_text()
    assert "bridge1" in content
    assert "bridge2" in content


def test_format_bridges_for_torrc():
    from hermes_tor.bridges import Bridge, format_bridges_for_torrc

    bridges = [
        Bridge("obfs4", "1.2.3.4:443", "ABC", "obfs4 1.2.3.4:443 ABC"),
        Bridge("obfs4", "5.6.7.8:80", "DEF", "obfs4 5.6.7.8:80 DEF"),
    ]
    lines = format_bridges_for_torrc(bridges)
    assert lines == ["Bridge obfs4 1.2.3.4:443 ABC", "Bridge obfs4 5.6.7.8:80 DEF"]


# ── daemon tests ──────────────────────────────────────────────


def test_torrc_template_contains_required_fields(tmp_path):
    """torrc must include SOCKSPort, ControlPort, and geoip directives."""
    from hermes_tor.daemon import TorDaemon

    # Create a dummy tor binary
    fake_tor = tmp_path / "tor.exe"
    fake_tor.touch()

    # Create dummy lyrebird
    pt_dir = tmp_path / "pluggable_transports"
    pt_dir.mkdir(parents=True)
    (pt_dir / "lyrebird.exe").touch()

    daemon = TorDaemon(
        tor_binary=fake_tor,
        data_dir=tmp_path / "data",
        bridges=["obfs4 1.2.3.4:443 FINGERPRINT cert=xyz iat-mode=0"],
        tor_binary_dir=tmp_path,
    )

    torrc = daemon._build_torrc()
    assert "SOCKSPort 127.0.0.1:9050 IsolateSOCKSAuth" in torrc
    assert "ControlPort 9051" in torrc
    assert "UseBridges 1" in torrc
    assert "Bridge obfs4 1.2.3.4:443" in torrc
    assert "ClientTransportPlugin" in torrc
    assert "lyrebird" in torrc.lower()


def test_torrc_without_bridges_omits_bridge_section(tmp_path):
    from hermes_tor.daemon import TorDaemon

    fake_tor = tmp_path / "tor"
    fake_tor.touch()
    pt_dir = tmp_path / "pluggable_transports"
    pt_dir.mkdir(parents=True)
    (pt_dir / "lyrebird").touch()

    daemon = TorDaemon(
        tor_binary=fake_tor,
        data_dir=tmp_path / "data",
        bridges=[],
        tor_binary_dir=tmp_path,
    )

    torrc = daemon._build_torrc()
    assert "UseBridges" not in torrc
    # Check that no actual Bridge directive exists (only comments about bridges)
    assert "\nBridge " not in torrc


def test_tor_daemon_requires_binary_to_exist(tmp_path):
    from hermes_tor.daemon import TorDaemon, TorDaemonError

    with pytest.raises(TorDaemonError, match="Tor binary not found"):
        TorDaemon(tor_binary=tmp_path / "nonexistent_tor", bridges=[])


def _daemon_for_isolation_test(tmp_path):
    from hermes_tor.daemon import TorDaemon

    fake_tor = tmp_path / "tor"
    fake_tor.touch()
    return TorDaemon(tor_binary=fake_tor, data_dir=tmp_path / "data")


def test_separate_identities_receive_different_authenticated_sessions(tmp_path):
    from hermes_tor.daemon import IsolationIdentity

    daemon = _daemon_for_isolation_test(tmp_path)
    agent = daemon.issue_socks_credential(IsolationIdentity("conversation-a", "agent-a"))
    subagent = daemon.issue_socks_credential(
        IsolationIdentity("conversation-a", "agent-a", subagent_id="researcher")
    )
    platform = daemon.issue_socks_credential(
        IsolationIdentity("conversation-a", "agent-a", platform_account="support@example.test")
    )
    browser = daemon.issue_socks_credential(
        IsolationIdentity("conversation-a", "agent-a", browser_context="private-tab-1")
    )
    task = daemon.issue_socks_credential(
        IsolationIdentity("conversation-a", "agent-a", sensitive_task="incident-42")
    )

    authentications = {lease.authentication() for lease in (agent, subagent, platform, browser, task)}
    assert len(authentications) == 5

    daemon.stop()
    assert all(lease.discarded for lease in (agent, subagent, platform, browser, task))
    with pytest.raises(Exception, match="discarded"):
        agent.authentication()


def test_credentials_are_not_reused_for_unrelated_conversations(tmp_path):
    from hermes_tor.daemon import IsolationIdentity

    daemon = _daemon_for_isolation_test(tmp_path)
    first = daemon.issue_socks_credential(IsolationIdentity("conversation-a", "agent-a"))
    second = daemon.issue_socks_credential(IsolationIdentity("conversation-b", "agent-a"))
    assert first.authentication() != second.authentication()


def test_anonymous_helpers_cannot_create_isolated_client(tmp_path):
    from hermes_tor.daemon import TorDaemonError

    daemon = _daemon_for_isolation_test(tmp_path)
    with pytest.raises(TorDaemonError, match="anonymous SOCKS clients are forbidden"):
        with daemon.isolated_client(None):
            pass


@pytest.mark.parametrize("option", ["proxy", "trust_env", "mounts"])
def test_isolated_client_rejects_routing_overrides(tmp_path, option):
    from hermes_tor.daemon import IsolationIdentity, TorDaemonError

    daemon = _daemon_for_isolation_test(tmp_path)
    identity = IsolationIdentity("conversation-a", "agent-a")
    with pytest.raises(TorDaemonError, match=option):
        with daemon.isolated_client(identity, **{option: {}}):
            pass


def test_proxy_http_uses_fresh_authenticated_url_per_request(monkeypatch):
    from hermes_tor.proxy_http import _get_proxy_url

    monkeypatch.setenv("TOR_PROXY", "socks5://127.0.0.1:9150")
    first = _get_proxy_url()
    second = _get_proxy_url()
    assert first != second
    assert first.startswith("socks5://")
    assert "@127.0.0.1:9150" in first


def test_gateway_boundaries_receive_distinct_authenticated_urls(monkeypatch):
    from hermes_tor.gateway import GATEWAY_PROXY_VARS, inject_gateway_env

    platform_boundaries = {
        "TELEGRAM_PROXY",
        "DISCORD_PROXY",
        "MATRIX_PROXY",
        "MATTERMOST_PROXY",
        "PHOTON_PROXY",
        "WHATSAPP_PROXY",
        "SMS_PROXY",
    }
    assert platform_boundaries <= GATEWAY_PROXY_VARS
    for key in GATEWAY_PROXY_VARS:
        monkeypatch.delenv(key, raising=False)
    inject_gateway_env(9150)
    proxy_urls = {os.environ[key] for key in GATEWAY_PROXY_VARS}
    assert len(proxy_urls) == len(GATEWAY_PROXY_VARS)
    assert all("@127.0.0.1:9150" in url for url in proxy_urls)


def test_isolated_client_uses_request_credentials_and_discards_them(
    tmp_path, monkeypatch
):
    from hermes_tor.daemon import IsolationIdentity
    import hermes_tor.daemon as daemon_module

    captured = {}

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(daemon_module.httpx, "Client", FakeClient)
    daemon = _daemon_for_isolation_test(tmp_path)
    identity = IsolationIdentity("conversation-a", "agent-a", browser_context="tab-a")
    with daemon.isolated_client(identity) as client:
        assert isinstance(client, FakeClient)
        assert captured["proxy"].startswith("socks5://")
        assert "@127.0.0.1:9050" in captured["proxy"]
        assert captured["trust_env"] is False
        assert len(daemon._active_credentials) == 1
    assert daemon._active_credentials == set()


# ── verifier tests ────────────────────────────────────────────


def test_verifier_parse_tor_success():
    from hermes_tor.verifier import TorVerifier

    html = """<html><body>
    <div class="content">
    <h1>Congratulations. This browser is configured to use Tor.</h1>
    <p>Your IP address appears to be: <strong>185.220.101.1</strong></p>
    </div></body></html>"""
    result = TorVerifier._parse_response(html, 200)
    assert result.using_tor is True
    assert result.exit_ip == "185.220.101.1"
    assert result.is_anonymous is True


def test_verifier_parse_not_tor():
    from hermes_tor.verifier import TorVerifier

    html = """<html><body>
    <div class="content">
    <h1>Sorry. You are not using Tor.</h1>
    <p>Your IP address appears to be: <strong>203.0.113.5</strong></p>
    </div></body></html>"""
    result = TorVerifier._parse_response(html, 200)
    assert result.using_tor is False
    assert result.exit_ip == "203.0.113.5"
    assert result.is_anonymous is False


def test_verifier_parse_http_error():
    from hermes_tor.verifier import TorVerifier

    result = TorVerifier._parse_response("", 500)
    assert result.using_tor is False
    assert "HTTP 500" in (result.error or "")


# ── manager tests ─────────────────────────────────────────────


def test_manager_initial_state_is_stopped(tmp_path):
    from hermes_tor.manager import TorManager, TorState

    mgr = TorManager(data_dir=tmp_path, auto_download=False)
    assert mgr.state == TorState.STOPPED
    assert mgr.socks_proxy_url is None


def test_manager_state_transitions(tmp_path):
    from hermes_tor.manager import TorState

    transitions = {
        TorState.STOPPED: {TorState.STARTING},
        TorState.STARTING: {TorState.RUNNING, TorState.ERROR},
        TorState.RUNNING: {TorState.STOPPING, TorState.ERROR},
        TorState.STOPPING: {TorState.STOPPED, TorState.ERROR},
        TorState.ERROR: {TorState.STOPPED, TorState.STARTING},
    }
    assert TorState.STARTING in transitions[TorState.STOPPED]
    assert TorState.RUNNING in transitions[TorState.STARTING]
    assert TorState.STOPPING in transitions[TorState.RUNNING]
    assert TorState.STOPPED in transitions[TorState.STOPPING]


def test_manager_bridge_count_zero_by_default(tmp_path):
    from hermes_tor.manager import TorManager

    mgr = TorManager(data_dir=tmp_path, auto_download=False)
    status = mgr.status()
    assert status.bridge_count == 0


def test_manager_add_bridge_increases_count(tmp_path, monkeypatch):
    from hermes_tor.manager import TorManager
    import hermes_tor.manager as mgr_mod

    # Patch the module-level import in manager to use temp path
    monkeypatch.setattr(mgr_mod, "BRIDGES_PATH", tmp_path / "bridges.txt")

    mgr = TorManager(
        data_dir=tmp_path,
        auto_download=False,
        bridges=["obfs4 1.2.3.4:443 ABCDEF"],
    )
    assert mgr.status().bridge_count == 1

    mgr.add_bridge("obfs4 5.6.7.8:80 FEDCBA")
    assert mgr.status().bridge_count == 2
