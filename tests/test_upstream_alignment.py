"""Static acceptance tests for the semantic Hermes compatibility contract."""

import importlib.util
import json
from pathlib import Path

from darkloom.hardening import ControlStatus, load_manifest

ROOT = Path(__file__).resolve().parents[1]


def _checker_module():
    path = ROOT / "scripts" / "check_upstream_alignment.py"
    spec = importlib.util.spec_from_file_location("check_upstream_alignment", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_manifest_is_semantic_and_exact_sha_pinned():
    manifest = load_manifest()
    assert manifest["schema_version"] == 2
    assert manifest["compatibility_model"] == "semantic"
    assert len(manifest["upstream"]["verified_commit"]) == 40
    assert manifest["upstream"]["required_commit"] == manifest["upstream"]["verified_commit"]


def test_preservation_contract_is_non_negotiable():
    manifest = load_manifest()
    policy = manifest["preservation_policy"]
    assert policy == {
        "unsupported_features_remain_enabled": True,
        "fail_closed_scope": "darkloom_owned_operations_only",
        "unknown_upstream_features": "unverified_preserved",
        "runtime_evidence_required_for_routing_claims": True,
    }


def test_discord_voice_is_explicitly_preserved():
    controls = {item["id"]: item for item in load_manifest()["controls"]}
    voice = controls["DL-007"]
    assert voice["status"] == ControlStatus.UNSUPPORTED_PRESERVED.value
    assert voice["preserve_feature"] is True
    assert "discord/adapter.py" in voice["files"][0]


def test_historical_patches_are_not_current_enforcement():
    manifest = load_manifest()
    assert manifest["historical_patches"]
    assert all(item["status"] == "historical" for item in manifest["historical_patches"])
    readme = (ROOT / "patches" / "README.md").read_text(encoding="utf-8")
    assert "DO NOT APPLY" in readme


def test_manifest_and_auto_apply_scans_are_clean():
    checker = _checker_module()
    manifest = json.loads(
        (ROOT / "src" / "darkloom" / "compatibility-manifest.json").read_text(encoding="utf-8")
    )
    assert checker.manifest_errors(manifest, root=ROOT) == []
    assert checker.auto_apply_errors(root=ROOT) == []
