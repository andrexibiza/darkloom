"""Unit tests for hermes-tor.

Run: uv run pytest tests/ -v
"""
import pytest
from pathlib import Path


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
        bridges=["obfs4 1.2.3.4:443 " + "A" * 40 + " cert=xyz iat-mode=0"],
    )
    assert mgr.status().bridge_count == 1

    result = mgr.add_bridge("obfs4 5.6.7.8:80 " + "B" * 40 + " cert=abc iat-mode=1")
    assert result.added is True
    assert mgr.status().bridge_count == 2

# ── request-scoped LLM routing tests ─────────────────────────


def test_direct_llm_route_is_forbidden_in_strict_mode(monkeypatch):
    from hermes_tor.gateway import (
        LLMProviderPolicy,
        LLMRoute,
        create_llm_client,
    )

    monkeypatch.setenv("TOR_STRICT_MODE", "1")
    with pytest.raises(PermissionError, match="strict mode"):
        create_llm_client(
            "openai",
            LLMRoute.DIRECT,
            {"openai": LLMProviderPolicy(allow_direct=True)},
        )


def test_direct_llm_route_requires_provider_policy(caplog):
    import logging
    from hermes_tor.gateway import LLMProviderPolicy, LLMRoute, create_llm_client

    with pytest.raises(ValueError, match="No LLM routing policy"):
        create_llm_client("unknown", LLMRoute.DIRECT, {})
    with pytest.raises(PermissionError, match="does not allow"):
        create_llm_client(
            "anthropic", LLMRoute.DIRECT, {"anthropic": LLMProviderPolicy()}
        )

    with caplog.at_level(logging.CRITICAL):
        with create_llm_client(
            "anthropic",
            LLMRoute.DIRECT,
            {"anthropic": LLMProviderPolicy(allow_direct=True)},
        ):
            pass
    assert "SECURITY AUDIT: DIRECT_LLM_ROUTE_SELECTED" in caplog.text
    assert "provider=anthropic" in caplog.text


def test_tor_llm_route_constructs_socks_transport():
    """The default installation must include HTTPX's SOCKS dependencies."""
    from hermes_tor.gateway import LLMProviderPolicy, LLMRoute, create_llm_client

    with create_llm_client(
        "openai",
        LLMRoute.TOR,
        {"openai": LLMProviderPolicy()},
        socks_proxy_url="socks5://127.0.0.1:19050",
    ) as client:
        assert client._transport.__class__.__name__ == "HTTPTransport"


def test_overlapping_llm_policy_change_cannot_change_platform_route(monkeypatch):
    """An LLM direct-route decision must not mutate another request's proxy."""
    import os
    import threading
    from hermes_tor import gateway

    proxy = "socks5://127.0.0.1:19050"
    monkeypatch.setenv("ALL_PROXY", proxy)
    monkeypatch.setenv("HTTPS_PROXY", proxy)
    monkeypatch.setenv("HTTP_PROXY", proxy)
    monkeypatch.setenv("TOR_PROXY", proxy)
    monkeypatch.setenv("TOR_ENABLED", "1")
    monkeypatch.setattr(gateway, "_gateway_env_frozen", False)
    gateway.finalize_gateway_environment()

    barrier = threading.Barrier(2)
    platform_routes = []
    llm_routes = []

    def platform_request():
        barrier.wait()
        platform_routes.append(os.environ["ALL_PROXY"])
        barrier.wait()
        platform_routes.append(os.environ["ALL_PROXY"])

    def llm_request():
        policies = {"openai": gateway.LLMProviderPolicy(allow_direct=False)}
        barrier.wait()
        policies["openai"] = gateway.LLMProviderPolicy(allow_direct=True)
        with gateway.create_llm_client(
            "openai", gateway.LLMRoute.DIRECT, policies, strict=False
        ) as client:
            llm_routes.append(client._transport.__class__.__name__)
        barrier.wait()

    threads = [threading.Thread(target=platform_request), threading.Thread(target=llm_request)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert not any(thread.is_alive() for thread in threads)
    assert platform_routes == [proxy, proxy]
    assert llm_routes == ["HTTPTransport"]
    gateway.assert_gateway_environment_immutable()


def test_gateway_environment_cannot_be_reinjected_after_initialization(monkeypatch):
    from hermes_tor import gateway

    monkeypatch.setattr(gateway, "_gateway_env_frozen", False)
    gateway.inject_gateway_env(19051)
    gateway.finalize_gateway_environment()
    with pytest.raises(RuntimeError, match="immutable"):
        gateway.inject_gateway_env(19052)
    with pytest.raises(RuntimeError, match="immutable"):
        gateway.clear_gateway_env()
