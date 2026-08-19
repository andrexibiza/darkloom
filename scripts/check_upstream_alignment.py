#!/usr/bin/env python3
"""Verify Darkloom against one exact, semantically reviewed Hermes checkout."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from darkloom.hardening import (  # noqa: E402
    CompatibilityError,
    ControlStatus,
    load_manifest,
    verify_compatibility,
)

_ALLOWED_CONTROL_STATES = {
    "upstream_native",
    "darkloom_required",
    "unsupported_preserved",
    "unverified",
    "historical",
}
_AUTO_APPLY = re.compile(
    r"(?:git\s+apply|\bpatch\s+-p\d*|apply_patch).*patches[/\\]000[1-4]",
    re.IGNORECASE,
)


def manifest_errors(manifest: dict, *, root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != 2:
        errors.append("compatibility manifest must use schema_version=2")
    if manifest.get("compatibility_model") != "semantic":
        errors.append("compatibility_model must be semantic")

    upstream = manifest.get("upstream") or {}
    commit = upstream.get("verified_commit")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        errors.append("upstream.verified_commit must be an exact 40-character SHA")

    preservation = manifest.get("preservation_policy") or {}
    if preservation.get("unsupported_features_remain_enabled") is not True:
        errors.append("unsupported_features_remain_enabled must be true")
    if preservation.get("fail_closed_scope") != "darkloom_owned_operations_only":
        errors.append("fail_closed_scope must be darkloom_owned_operations_only")
    if preservation.get("unknown_upstream_features") != "unverified_preserved":
        errors.append("unknown upstream features must be unverified_preserved")
    if preservation.get("runtime_evidence_required_for_routing_claims") is not True:
        errors.append("runtime routing claims must require runtime evidence")

    controls = manifest.get("controls") or []
    ids: set[str] = set()
    for control in controls:
        cid = str(control.get("id") or "")
        if not cid:
            errors.append("control without id")
            continue
        if cid in ids:
            errors.append(f"duplicate control id: {cid}")
        ids.add(cid)
        state = control.get("status")
        if state not in _ALLOWED_CONTROL_STATES:
            errors.append(f"{cid}: unknown status {state!r}")
        if state in {"unsupported_preserved", "unverified"} and control.get("preserve_feature") is not True:
            errors.append(f"{cid}: non-verified upstream control must preserve the feature")

    discord = next((c for c in controls if c.get("id") == "DL-007"), None)
    if not discord:
        errors.append("DL-007 Discord Voice preservation control is required")
    elif discord.get("status") != "unsupported_preserved" or discord.get("preserve_feature") is not True:
        errors.append("DL-007 must preserve Discord Voice as unsupported_preserved")

    for patch in manifest.get("historical_patches") or []:
        path = root / str(patch.get("path") or "")
        if patch.get("status") != "historical":
            errors.append(f"{patch.get('path')}: patch must be historical")
        if not path.is_file():
            errors.append(f"historical patch missing: {path.relative_to(root)}")

    return errors


def auto_apply_errors(*, root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    for base in (root / "scripts", root / "src", root / ".github" / "workflows"):
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path == Path(__file__).resolve():
                continue
            if path.suffix.lower() not in {".py", ".sh", ".ps1", ".yml", ".yaml"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if _AUTO_APPLY.search(text):
                errors.append(f"historical patch auto-application found in {path.relative_to(root)}")
    return errors


def run(hermes_root: Path) -> tuple[list[dict[str, str]], list[str]]:
    manifest = load_manifest()
    errors = manifest_errors(manifest) + auto_apply_errors()
    rows: list[dict[str, str]] = []
    try:
        results = verify_compatibility(hermes_root, strict=True)
    except CompatibilityError as exc:
        errors.append(str(exc))
        results = verify_compatibility(hermes_root, strict=False)

    for result in results:
        rows.append(
            {
                "id": result.control.id,
                "declared": result.control.declared_status.value,
                "observed": result.status.value,
                "evidence": result.evidence.value,
                "detail": result.detail,
            }
        )
        if (
            result.control.declared_status.value in {"upstream_native", "darkloom_required"}
            and result.status in {ControlStatus.INCOMPATIBLE, ControlStatus.STALE, ControlStatus.UNVERIFIED}
        ):
            errors.append(f"{result.control.id}: {result.detail}")
    return rows, list(dict.fromkeys(errors))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("hermes_root", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    rows, errors = run(args.hermes_root.expanduser().resolve())
    payload = {"ok": not errors, "controls": rows, "errors": errors}
    if args.as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for row in rows:
            print(
                f"{row['id']}: {row['observed']} [{row['evidence']}] — {row['detail']}"
            )
        if errors:
            print("\nAlignment failed:", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
        else:
            print("\nDarkloom is aligned with the exact reviewed Hermes revision.")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
