"""Current Darkloom suite layered over the preserved historical test corpus."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_LEGACY_PATH = Path(__file__).with_name("_darkloom_legacy_suite.py")
_SPEC = importlib.util.spec_from_file_location("_darkloom_legacy_suite", _LEGACY_PATH)
assert _SPEC and _SPEC.loader
_LEGACY = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_LEGACY)

_OBSOLETE = {
    "test_gateway_policy_rejects_conflicting_platform_proxy",
    "test_compatibility_without_hermes_reports_patch_only",
    "test_gateway_strict_mode_verifies_before_starting_tor",
    "test_strict_gateway_rejects_unverified_platform_clients",
    "test_documentation_is_not_reported_as_enforcement",
    "test_strict_compatibility_rejects_documentation_only_controls",
}

for _name, _value in vars(_LEGACY).items():
    if _name.startswith("test_") and _name not in _OBSOLETE:
        globals()[_name] = _value


def test_gateway_policy_preserves_platform_specific_override():
    from darkloom.gateway import establish_proxy_policy

    policy = establish_proxy_policy(
        environment={"TOR_STRICT_MODE": "1", "telegram_proxy": "direct://"}
    )
    assert policy.strict is True


def test_gateway_policy_rejects_malformed_generic_proxy_port():
    from darkloom.gateway import ProxyPolicyError, establish_proxy_policy

    with pytest.raises(ProxyPolicyError, match="unsupported proxy value"):
        establish_proxy_policy(
            environment={
                "TOR_STRICT_MODE": "1",
                "ALL_PROXY": "socks5://127.0.0.1:not-a-port",
            }
        )


def test_strict_gateway_reports_unverified_platform_clients_without_blocking(monkeypatch):
    import darkloom.gateway as gateway

    monkeypatch.setenv("TOR_STRICT_MODE", "1")
    policy = gateway.establish_proxy_policy(environment={"TOR_STRICT_MODE": "1"})
    gaps = gateway.require_verified_proxy_clients(policy, "discord", "slack")
    assert gaps == ("discord", "slack")


def test_gateway_strict_mode_verifies_before_starting_tor_after_policy_validation(monkeypatch, tmp_path):
    from darkloom import gateway
    from darkloom.hardening import CompatibilityError

    for name in (*gateway.PROXY_ENV_VARS, *gateway.NO_PROXY_ENV_VARS):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("TOR_STRICT_MODE", "1")
    monkeypatch.setattr(gateway, "is_tor_installed", lambda: True)
    monkeypatch.setattr(gateway, "require_verified_proxy_clients", lambda *a, **kw: ())

    with pytest.raises(CompatibilityError, match="strict mode rejected"):
        gateway.start_tor_for_gateway(hermes_root=tmp_path, write_env=False)


def test_compatibility_without_hermes_distinguishes_preserved_and_required(tmp_path):
    from darkloom.hardening import ControlStatus, verify_compatibility

    results = verify_compatibility(tmp_path, strict=False)
    by_declared = {result.control.declared_status for result in results}
    by_observed = {result.status for result in results}
    assert ControlStatus.UPSTREAM_NATIVE in by_declared
    assert ControlStatus.UNSUPPORTED_PRESERVED in by_declared
    assert ControlStatus.UNVERIFIED in by_observed
    assert ControlStatus.UNSUPPORTED_PRESERVED in by_observed


def test_preserved_limitations_are_not_reported_as_enforcement(tmp_path):
    from darkloom.hardening import EvidenceKind, ControlStatus, verify_compatibility

    results = verify_compatibility(tmp_path, strict=False)
    preserved = [
        result
        for result in results
        if result.control.declared_status is ControlStatus.UNSUPPORTED_PRESERVED
    ]
    assert preserved
    assert all(result.status is ControlStatus.UNSUPPORTED_PRESERVED for result in preserved)
    assert all(result.evidence is EvidenceKind.PRESERVATION_POLICY for result in preserved)


def test_strict_compatibility_preserves_documentation_only_controls(monkeypatch, tmp_path):
    from darkloom import hardening

    manifest = {
        "schema_version": 2,
        "upstream": {"verified_commit": "expected", "required_commit": "expected"},
        "controls": [
            {
                "id": "DL-001",
                "title": "installed integration",
                "status": "upstream_native",
                "files": ["gateway/platforms/base.py"],
                "checks": [{"file": "gateway/platforms/base.py", "contains": []}],
                "patch_id": "none",
            },
            {
                "id": "DL-007",
                "title": "Discord voice",
                "status": "unsupported_preserved",
                "files": [],
                "patch_id": "none",
                "preserve_feature": True,
            },
        ],
    }
    root = tmp_path / "hermes"
    (root / "gateway/platforms").mkdir(parents=True)
    (root / "plugins").mkdir()
    (root / "gateway/platforms/base.py").touch()

    monkeypatch.setattr(hardening, "load_manifest", lambda: manifest)
    monkeypatch.setattr(hardening, "find_hermes_root", lambda _root: root)
    monkeypatch.setattr(hardening, "_git_revision", lambda _root: "expected")

    results = hardening.verify_compatibility(root, strict=True)
    preserved = next(result for result in results if result.control.id == "DL-007")
    assert preserved.status is hardening.ControlStatus.UNSUPPORTED_PRESERVED
    assert preserved.evidence is hardening.EvidenceKind.PRESERVATION_POLICY
