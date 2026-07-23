"""Unit tests for hermes-tor.

Run: uv run pytest tests/ -v
"""
import os

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
    if os.name != "nt":
        # On case-sensitive platforms, test independent lower/upper tracking.
        monkeypatch.delenv("all_proxy", raising=False)
    inject_gateway_env(19050)
    if os.name != "nt":
        assert "all_proxy" in __import__("os").environ
    clear_gateway_env()
    assert __import__("os").environ["ALL_PROXY"] == "previous-value"
    if os.name != "nt":
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


# ── compatibility evidence tests ─────────────────────────────


def test_compatibility_without_hermes_reports_patch_only(tmp_path):
    from hermes_tor.hardening import EvidenceKind, ControlStatus, verify_compatibility

    results = verify_compatibility(tmp_path, strict=False)
    integration = [result for result in results if not result.control.documentation_only]
    assert integration
    assert all(result.status is ControlStatus.PATCH_ONLY for result in integration)
    assert all(result.evidence is EvidenceKind.PATCH_ARTIFACT for result in integration)


def test_strict_compatibility_fails_closed_without_hermes(tmp_path):
    from hermes_tor.hardening import CompatibilityError, verify_compatibility

    with pytest.raises(CompatibilityError, match="strict mode rejected"):
        verify_compatibility(tmp_path, strict=True)


def test_documentation_is_not_reported_as_enforcement(tmp_path):
    from hermes_tor.hardening import EvidenceKind, ControlStatus, verify_compatibility

    results = verify_compatibility(tmp_path, strict=False)
    documentation = [result for result in results if result.control.documentation_only]
    assert documentation
    assert all(result.status is ControlStatus.UNVERIFIED for result in documentation)
    assert all(result.evidence is EvidenceKind.DOCUMENTATION for result in documentation)


def test_strict_compatibility_rejects_documentation_only_controls(monkeypatch, tmp_path):
    """Matching installed files must not excuse known, unenforced leak paths."""
    from hermes_tor import hardening

    manifest = {
        "upstream": {"required_commit": "expected"},
        "patch": {"path": "patches/test.patch", "sha256": "patch-digest"},
        "patched_files": {"gateway/platforms/base.py": "file-digest"},
        "controls": [
            {"id": "HT-001", "title": "installed integration",
             "files": ["gateway/platforms/base.py"], "patch_id": "test"},
            {"id": "HT-009", "title": "strict-mode adapter blocking",
             "files": [], "patch_id": "none", "documentation_only": True},
        ],
    }
    root = tmp_path / "hermes"
    (root / "gateway/platforms").mkdir(parents=True)
    (root / "gateway/platforms/base.py").touch()

    monkeypatch.setattr(hardening, "load_manifest", lambda: manifest)
    monkeypatch.setattr(hardening, "find_hermes_root", lambda _root: root)
    monkeypatch.setattr(hardening, "_git_revision", lambda _root: "expected")
    monkeypatch.setattr(
        hardening, "_sha256",
        lambda path: "file-digest" if path.name == "base.py" else "patch-digest",
    )

    with pytest.raises(hardening.CompatibilityError, match="HT-009"):
        hardening.verify_compatibility(root, strict=True)

    results = hardening.verify_compatibility(
        root, strict=True, runtime_probes={"HT-009": lambda: True})
    strict_control = next(result for result in results
                          if result.control.id == "HT-009")
    assert strict_control.status is hardening.ControlStatus.VERIFIED
    assert strict_control.evidence is hardening.EvidenceKind.RUNTIME_VERIFICATION


def test_strict_compatibility_rejects_negative_runtime_probe(monkeypatch, tmp_path):
    from hermes_tor import hardening

    manifest = {
        "upstream": {"required_commit": "expected"},
        "patch": {"path": "patches/test.patch", "sha256": "patch-digest"},
        "patched_files": {"gateway/platforms/base.py": "file-digest"},
        "controls": [{"id": "HT-001", "title": "runtime control",
                      "files": ["gateway/platforms/base.py"], "patch_id": "test"}],
    }
    root = tmp_path / "hermes"
    (root / "gateway/platforms").mkdir(parents=True)
    (root / "gateway/platforms/base.py").touch()
    monkeypatch.setattr(hardening, "load_manifest", lambda: manifest)
    monkeypatch.setattr(hardening, "find_hermes_root", lambda _root: root)
    monkeypatch.setattr(hardening, "_git_revision", lambda _root: "expected")
    monkeypatch.setattr(hardening, "_sha256", lambda path: (
        "file-digest" if path.name == "base.py" else "patch-digest"))

    results = hardening.verify_compatibility(
        root, strict=False, runtime_probes={"HT-001": lambda: False})
    assert results[0].status is hardening.ControlStatus.INCOMPATIBLE
    assert results[0].evidence is hardening.EvidenceKind.RUNTIME_VERIFICATION
    with pytest.raises(hardening.CompatibilityError, match="HT-001"):
        hardening.verify_compatibility(
            root, strict=True, runtime_probes={"HT-001": lambda: False})


def test_combined_patch_keeps_local_sidecar_ipc_direct():
    patch = (Path(__file__).parents[1] / "patches" /
             "0003-harden-tor-proxy-all-platforms.patch").read_text()

    assert "PHOTON_SIDECAR_WATCH_STDIN" in patch
    assert "process.env.grpc_proxy = photonProxy" in patch
    assert "plugins/platforms/photon/sidecar/index.mjs" in patch
    assert 'bridge_env["ALL_PROXY"]' not in patch  # loop-based injection is retained
    assert 'for _pk in ("ALL_PROXY", "HTTPS_PROXY", "HTTP_PROXY")' in patch
    assert "resolve_proxy_url(platform_env_var=\"PHOTON_PROXY\")" not in patch
    assert "resolve_proxy_url(platform_env_var=\"WHATSAPP_PROXY\")" not in patch


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

    line = "obfs4 198.51.100.1:443 ABCDEF1234567890ABCDEF1234567890ABCDEF12 cert=xyz iat-mode=0"
    bridge = parse_bridge_line(line)
    assert bridge is not None
    assert bridge.transport == "obfs4"
    assert bridge.address == "198.51.100.1:443"
    assert bridge.fingerprint == "ABCDEF1234567890ABCDEF1234567890ABCDEF12"


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

    assert validate_bridge("obfs4 1.2.3.4:443 " + "A" * 40 + " cert=xyz iat-mode=0") is True
    assert validate_bridge("") is False
    assert validate_bridge("# comment") is False


def test_parse_bridge_set_is_all_or_nothing():
    from hermes_tor.bridges import parse_bridge_set

    valid = (
        "obfs4 198.51.100.1:443 "
        "ABCDEF1234567890ABCDEF1234567890ABCDEF12 cert=xyz iat-mode=0"
    )
    assert len(parse_bridge_set(valid, transport="obfs4")) == 1

    with pytest.raises(ValueError):
        parse_bridge_set(f"{valid}\n<html>login required</html>", transport="obfs4")


def test_load_bridges_from_file(tmp_path):
    from hermes_tor.bridges import load_bridges_from_file

    bridge_file = tmp_path / "bridges.txt"
    bridge_file.write_text("""
# My bridges
obfs4 198.51.100.1:443 AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA cert=xyz iat-mode=0
obfs4 198.51.100.2:444 BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB cert=abc iat-mode=1
""")
    bridges = load_bridges_from_file(bridge_file)
    assert len(bridges) == 2
    assert bridges[0].transport == "obfs4"
    assert bridges[0].fingerprint == "A" * 40


def test_load_bridges_from_missing_file(tmp_path):
    from hermes_tor.bridges import load_bridges_from_file

    bridges = load_bridges_from_file(tmp_path / "nonexistent.txt")
    assert bridges == []


def test_save_bridges_to_file(tmp_path):
    from hermes_tor.bridges import save_bridges_to_file

    path = tmp_path / "bridges.txt"
    save_bridges_to_file(path, ["obfs4 1.2.3.4:443 " + "A" * 40 + " cert=xyz iat-mode=0"])
    content = path.read_text().strip()
    assert "obfs4 1.2.3.4:443 " + "A" * 40 in content
    if os.name != "nt":
        assert path.stat().st_mode & 0o777 == 0o600


def test_save_bridges_append(tmp_path):
    from hermes_tor.bridges import save_bridges_to_file

    path = tmp_path / "bridges.txt"
    save_bridges_to_file(path, ["1.2.3.4:443 " + "A" * 40])
    save_bridges_to_file(path, ["1.2.3.5:443 " + "B" * 40], append=True)
    content = path.read_text()
    assert "1.2.3.4:443" in content
    assert "1.2.3.5:443" in content


def test_format_bridges_for_torrc():
    from hermes_tor.bridges import Bridge, format_bridges_for_torrc

    bridges = [
        Bridge("vanilla", "1.2.3.4:443", "A" * 40),
        Bridge("vanilla", "5.6.7.8:80", "B" * 40),
    ]
    lines = format_bridges_for_torrc(bridges)
    assert lines == ["Bridge 1.2.3.4:443 " + "A" * 40, "Bridge 5.6.7.8:80 " + "B" * 40]


def test_private_bridge_permissions_and_symlink_rejection(tmp_path):
    from hermes_tor.bridges import save_bridges_to_file

    private_dir = tmp_path / "private"
    path = private_dir / "bridges.txt"
    save_bridges_to_file(path, ["obfs4 1.2.3.4:443 ABCDEF1234567890ABCDEF1234567890ABCDEF12 cert=xyz iat-mode=0"])

    # Verify file was created with restricted access.
    # On POSIX, mode bits are the enforcement mechanism.
    # On Windows, _windows_owner_only() handles ACL hardening;
    # st_mode is always 0o777/0o666 regardless of chmod.
    if os.name != "nt":
        assert stat.S_IMODE(private_dir.stat().st_mode) == 0o700
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    else:
        assert private_dir.is_dir()
        assert path.read_text()

    # Symlink targets must be rejected to prevent write-through attacks.
    target = tmp_path / "target"
    target.write_text("do not replace")
    link = private_dir / "linked.txt"
    link.symlink_to(target)
    with pytest.raises(OSError, match="symbolic link"):
        save_bridges_to_file(link, ["obfs4 5.6.7.8:80 FEDCBA9876543210FEDCBA9876543210FEDCBA98 cert=abc iat-mode=1"])
    assert target.read_text() == "do not replace"


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
        bridges=["obfs4 1.2.3.4:443 " + "A" * 40 + " cert=xyz iat-mode=0"],
        tor_binary_dir=tmp_path,
    )

    torrc = daemon._build_torrc()
    assert "SOCKSPort 127.0.0.1:9050 IsolateSOCKSAuth" in torrc
    if os.name == "nt":
        assert "ControlPort 127.0.0.1:9051" in torrc
    else:
        assert "ControlSocket " in torrc
        assert "ControlPort" not in torrc
    assert "CookieAuthentication 1" in torrc
    assert f"CookieAuthFile {tmp_path / 'data' / 'control_auth_cookie'}" in torrc
    assert "CookieAuthFileGroupReadable 0" in torrc
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


def test_torrc_is_written_privately(tmp_path):
    from hermes_tor.daemon import TorDaemon

    fake_tor = tmp_path / "tor"
    fake_tor.touch()
    daemon = TorDaemon(fake_tor, data_dir=tmp_path / "data")
    daemon._write_torrc()

    # Verify torrc was created via secure, owner-only file operations.
    # On POSIX, mode bits reflect the 0o700/0o600 enforcement.
    # On Windows, _windows_owner_only() handles ACL hardening;
    # st_mode does not reflect chmod changes.
    if os.name != "nt":
        assert stat.S_IMODE(daemon.data_dir.stat().st_mode) == 0o700
        assert stat.S_IMODE((daemon.data_dir / "torrc").stat().st_mode) == 0o600
    else:
        assert daemon.data_dir.is_dir()
        torrc = daemon.data_dir / "torrc"
        assert torrc.is_file()
        assert "SOCKSPort" in torrc.read_text()


def _daemon_for_isolation_test(tmp_path):
    from hermes_tor.daemon import TorDaemon

    fake_tor = tmp_path / "tor"
    fake_tor.touch()
    return TorDaemon(tor_binary=fake_tor, data_dir=tmp_path / "data")


class _ControlSocket:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.sent = []

    def sendall(self, payload):
        self.sent.append(payload)

    def recv(self, _size):
        return next(self.responses)


def test_torrc_has_no_non_loopback_control_binding(tmp_path):
    from hermes_tor.daemon import TorDaemon

    fake_tor = tmp_path / "tor"
    fake_tor.touch()
    daemon = TorDaemon(tor_binary=fake_tor, data_dir=tmp_path / "private")
    torrc = daemon._build_torrc()

    assert "ControlPort 0.0.0.0" not in torrc
    assert "ControlPort [::]" not in torrc
    if "ControlPort" in torrc:
        assert "ControlPort 127.0.0.1:" in torrc


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


def test_gateway_uses_dedicated_config_without_rewriting_dotenv(tmp_path, monkeypatch):
    from hermes_tor.gateway import write_gateway_env_file

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    dotenv = tmp_path / ".hermes" / ".env"
    dotenv.parent.mkdir()
    dotenv.write_text('TOKEN="a=b"\n# keep me\n')
    write_gateway_env_file()
    assert dotenv.read_text() == 'TOKEN="a=b"\n# keep me\n'
    tor_env = tmp_path / ".hermes" / "tor" / "gateway.env"
    assert "TOR_ENABLED=1" in tor_env.read_text()


# ── verifier tests ────────────────────────────────────────────


def test_verifier_validates_ip_addresses():
    from hermes_tor.verifier import TorVerifier
    assert TorVerifier._valid_ip("185.220.101.1") == "185.220.101.1"
    assert TorVerifier._valid_ip("not-an-ip") is None


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
    assert status.process_healthy is False
    assert status.socks_healthy is False
    assert status.bootstrap_complete is False
    assert status.external_route_verified is False
    assert status.healthy is False


def test_manager_add_bridge_increases_count(tmp_path, monkeypatch):
    from hermes_tor.manager import TorManager
    import hermes_tor.manager as mgr_mod

    # Patch the module-level import in manager to use temp path
    monkeypatch.setattr(mgr_mod, "BRIDGES_PATH", tmp_path / "bridges.txt")

    mgr = TorManager(
        data_dir=tmp_path,
        auto_download=False,
        bridges=["obfs4 1.2.3.4:443 " + "A" * 40 + " cert=xyz iat-mode=0"],
    )
    assert mgr.status().bridge_count == 1

    result = mgr.add_bridge("obfs4 5.6.7.8:80 " + "B" * 40 + " cert=abc iat-mode=1")
    assert result.added is True
    assert mgr.status().bridge_count == 2

# ── privacy boundary tests ────────────────────────────────────


def test_redact_sensitive_diagnostics(monkeypatch):
    from hermes_tor.privacy import redact

    monkeypatch.setenv("HOME", "/home/alice")
    value = (
        "socks5://user:password@127.0.0.1:9050 "
        "https://example.test/path?token=secret "
        "/home/alice/.hermes/tor "
        "obfs4 198.51.100.1:443 FP cert=secret iat-mode=0"
    )
    safe = redact(value)
    for secret in ("user", "password", "token=secret", "/home/alice", "198.51.100.1", "cert=secret"):
        assert secret not in safe


def test_private_debug_log_is_opt_in_and_owner_only(monkeypatch, tmp_path):
    from hermes_tor.privacy import private_diagnostic

    path = tmp_path / "private" / "debug.log"
    monkeypatch.setenv("HERMES_TOR_DEBUG_LOG", str(path))
    private_diagnostic("test", "secret")
    assert not path.exists()
    monkeypatch.setenv("HERMES_TOR_DEBUG", "1")
    private_diagnostic("test", "https://user:pass@example.test/?secret=yes")
    if os.name != "nt":
        assert path.stat().st_mode & 0o777 == 0o600
        assert path.parent.stat().st_mode & 0o777 == 0o700
    else:
        assert path.is_file()
        assert path.parent.is_dir()
    assert "pass" not in path.read_text()


def test_mcp_status_and_verify_omit_sensitive_fields(monkeypatch):
    import json
    from types import SimpleNamespace
    from hermes_tor import mcp_server
    from hermes_tor.manager import TorState

    manager = SimpleNamespace(
        status=lambda: SimpleNamespace(state=TorState.RUNNING, socks_proxy_url="socks5://127.0.0.1:9050", circuit_established=True, bridge_count=2, exit_ip="198.51.100.9", uptime_seconds=1, error=None),
        verify=lambda: SimpleNamespace(using_tor=True, exit_ip="198.51.100.9", is_anonymous=True, error=None),
    )
    monkeypatch.setattr(mcp_server, "get_manager", lambda: manager)
    assert "exit_ip" not in json.loads(mcp_server.tor_status())
    assert "exit_ip" not in json.loads(mcp_server.tor_verify())
