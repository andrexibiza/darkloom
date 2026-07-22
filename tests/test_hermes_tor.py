"""Unit tests for hermes-tor.

Run: uv run pytest tests/ -v
"""
import pytest
from pathlib import Path


# ── gateway proxy policy tests ────────────────────────────────


def test_gateway_policy_rejects_conflicting_platform_proxy():
    from hermes_tor.gateway import ProxyPolicyError, establish_proxy_policy

    env = {"TOR_STRICT_MODE": "1", "telegram_proxy": "direct://"}
    with pytest.raises(ProxyPolicyError, match="disables proxy routing"):
        establish_proxy_policy(environment=env)


def test_gateway_policy_allows_only_loopback_no_proxy():
    from hermes_tor.gateway import ProxyPolicyError, establish_proxy_policy

    establish_proxy_policy(
        environment={"TOR_STRICT_MODE": "1", "NO_PROXY": "localhost,127.0.0.1,::1"}
    )
    with pytest.raises(ProxyPolicyError, match="may contain only"):
        establish_proxy_policy(
            environment={"TOR_STRICT_MODE": "1", "no_proxy": "localhost,example.com"}
        )


def test_gateway_environment_is_restored_exactly(monkeypatch):
    from hermes_tor.gateway import clear_gateway_env, inject_gateway_env

    monkeypatch.setenv("ALL_PROXY", "previous-value")
    monkeypatch.delenv("all_proxy", raising=False)
    inject_gateway_env(19050)
    assert "all_proxy" in __import__("os").environ
    clear_gateway_env()
    assert __import__("os").environ["ALL_PROXY"] == "previous-value"
    assert "all_proxy" not in __import__("os").environ


def test_gateway_preserves_slack_http_bridge(monkeypatch):
    from hermes_tor.gateway import clear_gateway_env, inject_gateway_env

    bridge = "http://127.0.0.1:8118"
    monkeypatch.setenv("SLACK_PROXY", bridge)
    inject_gateway_env(19050)
    assert __import__("os").environ["SLACK_PROXY"] == bridge
    assert __import__("os").environ["ALL_PROXY"] == "socks5://127.0.0.1:19050"
    clear_gateway_env()


def test_strict_gateway_requires_preinstalled_tor(monkeypatch):
    import hermes_tor.gateway as gateway

    for name in (*gateway.PROXY_ENV_VARS, *gateway.NO_PROXY_ENV_VARS):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("TOR_STRICT_MODE", "1")
    monkeypatch.setattr(gateway, "is_tor_installed", lambda: False)
    with pytest.raises(gateway.ProxyPolicyError, match="preinstalled Tor binary"):
        gateway.start_tor_for_gateway(write_env=False)


def test_strict_gateway_rejects_unverified_platform_clients(monkeypatch):
    import hermes_tor.gateway as gateway

    for name in (*gateway.PROXY_ENV_VARS, *gateway.NO_PROXY_ENV_VARS):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("TOR_STRICT_MODE", "1")
    monkeypatch.setattr(gateway, "is_tor_installed", lambda: True)
    with pytest.raises(gateway.ProxyPolicyError, match="discord.*slack|slack.*discord"):
        gateway.start_tor_for_gateway(write_env=False)


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
    assert "SOCKSPort 9050" in torrc
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
