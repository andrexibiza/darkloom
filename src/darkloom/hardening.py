"""Current Hermes compatibility contract and historical Darkloom audit surface.

The historical leak inventory is retained in ``_hardening_audit``. This module
owns current truth: exact upstream revision, semantic source seams, typed
coverage states, preservation of unsupported Hermes features, and runtime-proof
requirements for routing claims.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from enum import Enum
from importlib.resources import files
from pathlib import Path
from typing import Callable

from darkloom import _hardening_audit as _audit

LeakSeverity = _audit.LeakSeverity
LeakStatus = _audit.LeakStatus
Leak = _audit.Leak
LEAKS = _audit.LEAKS
register = _audit.register
run_audit = _audit.run_audit
inject_subprocess_proxy_env = _audit.inject_subprocess_proxy_env
check_tor_health = _audit.check_tor_health

# Correct historical mitigation prose without erasing the historical record.
for _leak in LEAKS:
    if _leak.title.startswith("Discord voice UDP"):
        _leak.after = (
            "Discord Voice remains available as an upstream-native feature. "
            "Darkloom does not claim SOCKS coverage; VPN or another UDP-capable "
            "transport is required for private voice routing."
        )
    elif _leak.title.startswith("Email SMTP/IMAP"):
        _leak.after = (
            "SMTP and IMAP remain available upstream. Darkloom does not claim "
            "routing coverage for these raw-socket transports."
        )
    elif _leak.title.startswith("IRC —"):
        _leak.after = (
            "IRC remains available upstream. Darkloom reports it as "
            "unsupported_preserved rather than disabling it."
        )


class ControlStatus(str, Enum):
    UNVERIFIED = "unverified"
    PATCH_ONLY = "patch_only"
    MITIGATED = "mitigated"
    UPSTREAM_NATIVE = "upstream_native"
    DARKLOOM_REQUIRED = "darkloom_required"
    UNSUPPORTED_PRESERVED = "unsupported_preserved"
    HISTORICAL = "historical"
    VERIFIED = "verified"
    STALE = "stale"
    INCOMPATIBLE = "incompatible"


class EvidenceKind(str, Enum):
    DOCUMENTATION = "documentation"
    PATCH_ARTIFACT = "patch_artifact"
    INSTALLED_PATCH = "installed_patch"
    SEMANTIC_CONTRACT = "semantic_contract"
    PRESERVATION_POLICY = "preservation_policy"
    HISTORICAL_PATCH = "historical_patch"
    RUNTIME_VERIFICATION = "runtime_verification"


@dataclass(frozen=True)
class Control:
    id: str
    title: str
    files: tuple[str, ...]
    hermes_revision: str
    patch_id: str
    documentation_only: bool = False
    declared_status: ControlStatus = ControlStatus.UNVERIFIED
    ownership: str = "upstream"
    checks: tuple[tuple[str, tuple[str, ...]], ...] = ()
    runtime_probe_required: bool = False
    preserve_feature: bool = False


@dataclass(frozen=True)
class ControlResult:
    control: Control
    status: ControlStatus
    evidence: EvidenceKind
    detail: str


class CompatibilityError(RuntimeError):
    """The reviewed Hermes compatibility contract is not satisfied."""


def load_manifest() -> dict:
    path = files("darkloom").joinpath("compatibility-manifest.json")
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest_is_legacy(manifest: dict) -> bool:
    return int(manifest.get("schema_version") or 1) < 2


def _declared_status(item: dict, *, legacy: bool) -> ControlStatus:
    raw = item.get("status")
    if raw:
        return ControlStatus(raw)
    if item.get("documentation_only"):
        return ControlStatus.UNVERIFIED if legacy else ControlStatus.UNSUPPORTED_PRESERVED
    return ControlStatus.DARKLOOM_REQUIRED


def _controls(manifest: dict) -> list[Control]:
    upstream = manifest.get("upstream") or {}
    revision = upstream.get("verified_commit") or upstream.get("required_commit") or ""
    legacy = _manifest_is_legacy(manifest)
    controls: list[Control] = []
    for item in manifest.get("controls") or []:
        declared = _declared_status(item, legacy=legacy)
        checks = tuple(
            (
                str(check.get("file") or ""),
                tuple(str(token) for token in check.get("contains") or ()),
            )
            for check in item.get("checks") or ()
        )
        file_names = dict.fromkeys(
            [
                *(str(name) for name in item.get("files") or ()),
                *(path for path, _ in checks if path),
            ]
        )
        controls.append(
            Control(
                id=str(item["id"]),
                title=str(item["title"]),
                files=tuple(file_names),
                hermes_revision=str(revision),
                patch_id=str(item.get("patch_id") or "none"),
                documentation_only=bool(item.get("documentation_only")),
                declared_status=declared,
                ownership=str(item.get("ownership") or "upstream"),
                checks=checks,
                runtime_probe_required=bool(item.get("runtime_probe_required")),
                preserve_feature=bool(item.get("preserve_feature")),
            )
        )
    return controls


def find_hermes_root(explicit: Path | str | None = None) -> Path | None:
    candidates = [explicit, os.environ.get("HERMES_HOME"), Path.cwd()]
    for candidate in candidates:
        if not candidate:
            continue
        root = Path(candidate).expanduser().resolve()
        if (root / "gateway/platforms/base.py").is_file() and (root / "plugins").is_dir():
            return root
    return None


def _git_revision(root: Path) -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _patch_artifact_ok(manifest: dict) -> bool:
    patch = manifest.get("patch") or {}
    path_value = patch.get("path")
    digest = patch.get("sha256")
    if not path_value:
        return False
    path = Path(__file__).resolve().parents[2] / str(path_value)
    return path.is_file() and (not digest or _sha256(path) == digest)


def _semantic_errors(root: Path, control: Control, manifest: dict) -> list[str]:
    errors: list[str] = []
    expected_hashes = manifest.get("patched_files") or {}
    for name in control.files:
        path = root / name
        if not path.is_file():
            errors.append(f"missing {name}")
            continue
        if not control.checks and name in expected_hashes and _sha256(path) != expected_hashes[name]:
            errors.append(f"hash mismatch {name}")
    for name, tokens in control.checks:
        path = root / name
        if not path.is_file():
            marker = f"missing {name}"
            if marker not in errors:
                errors.append(marker)
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for token in tokens:
            if token not in text:
                errors.append(f"{name} missing semantic token {token!r}")
    return errors


def _probe_result(
    control: Control,
    probe: Callable[[], bool] | None,
    fallback: ControlResult,
) -> ControlResult:
    if probe is None:
        return fallback
    try:
        passed = probe() is True
    except Exception as exc:
        if control.declared_status is ControlStatus.UNSUPPORTED_PRESERVED:
            return ControlResult(
                control,
                ControlStatus.UNSUPPORTED_PRESERVED,
                EvidenceKind.PRESERVATION_POLICY,
                f"runtime probe failed, feature preserved: {exc}",
            )
        return ControlResult(
            control,
            ControlStatus.INCOMPATIBLE,
            EvidenceKind.RUNTIME_VERIFICATION,
            f"runtime probe failed: {exc}",
        )
    if passed:
        return ControlResult(
            control,
            ControlStatus.VERIFIED,
            EvidenceKind.RUNTIME_VERIFICATION,
            "caller-supplied runtime probe passed",
        )
    if control.declared_status is ControlStatus.UNSUPPORTED_PRESERVED:
        return ControlResult(
            control,
            ControlStatus.UNSUPPORTED_PRESERVED,
            EvidenceKind.PRESERVATION_POLICY,
            "runtime probe did not verify routing; feature preserved",
        )
    return ControlResult(
        control,
        ControlStatus.INCOMPATIBLE,
        EvidenceKind.RUNTIME_VERIFICATION,
        "caller-supplied runtime probe reported failure",
    )


def verify_compatibility(
    hermes_root: Path | str | None = None,
    *,
    strict: bool | None = None,
    runtime_probes: dict[str, Callable[[], bool]] | None = None,
) -> list[ControlResult]:
    """Verify an exact revision and semantic source contracts.

    Schema-v2 strict mode blocks only controls declared ``upstream_native`` or
    ``darkloom_required``. Unsupported and unverified upstream capabilities are
    preserved and excluded from Darkloom routing claims. Legacy manifests retain
    their historical strict behavior for compatibility with old audit fixtures.
    """

    manifest = load_manifest()
    controls = _controls(manifest)
    legacy = _manifest_is_legacy(manifest)
    strict = is_strict_mode() if strict is None else strict
    root = find_hermes_root(hermes_root)
    patch_ok = _patch_artifact_ok(manifest)
    revision = _git_revision(root) if root else None
    upstream = manifest.get("upstream") or {}
    required = upstream.get("verified_commit") or upstream.get("required_commit")
    revision_ok = root is not None and revision == required
    results: list[ControlResult] = []

    for control in controls:
        declared = control.declared_status
        if legacy and control.documentation_only:
            result = ControlResult(
                control,
                ControlStatus.UNVERIFIED,
                EvidenceKind.DOCUMENTATION,
                "legacy documentation-only control has no enforcement",
            )
        elif declared is ControlStatus.HISTORICAL:
            result = ControlResult(
                control,
                ControlStatus.HISTORICAL,
                EvidenceKind.HISTORICAL_PATCH,
                "historical artifact retained for provenance only",
            )
        elif declared is ControlStatus.UNSUPPORTED_PRESERVED:
            missing = [
                name
                for name in control.files
                if root is not None and not (root / name).is_file()
            ]
            detail = "native Hermes capability preserved outside Darkloom's verified boundary"
            if missing:
                detail += "; source paths absent: " + ", ".join(missing)
            result = ControlResult(
                control,
                ControlStatus.UNSUPPORTED_PRESERVED,
                EvidenceKind.PRESERVATION_POLICY,
                detail,
            )
        elif root is None:
            result = ControlResult(
                control,
                ControlStatus.PATCH_ONLY if patch_ok else ControlStatus.UNVERIFIED,
                EvidenceKind.PATCH_ARTIFACT if patch_ok else EvidenceKind.DOCUMENTATION,
                "Hermes installation not found; historical patch is not runtime proof",
            )
        else:
            errors = _semantic_errors(root, control, manifest)
            if errors:
                result = ControlResult(
                    control,
                    ControlStatus.INCOMPATIBLE,
                    EvidenceKind.SEMANTIC_CONTRACT,
                    "; ".join(errors),
                )
            elif not revision_ok:
                result = ControlResult(
                    control,
                    ControlStatus.STALE,
                    EvidenceKind.SEMANTIC_CONTRACT,
                    f"Hermes revision {revision or 'unknown'} != reviewed {required}",
                )
            elif legacy:
                result = ControlResult(
                    control,
                    ControlStatus.MITIGATED,
                    EvidenceKind.INSTALLED_PATCH,
                    "legacy revision and installed evidence match",
                )
            elif declared is ControlStatus.UPSTREAM_NATIVE:
                result = ControlResult(
                    control,
                    ControlStatus.UPSTREAM_NATIVE,
                    EvidenceKind.SEMANTIC_CONTRACT,
                    "exact reviewed revision and upstream semantic contract match",
                )
            elif declared is ControlStatus.DARKLOOM_REQUIRED:
                result = ControlResult(
                    control,
                    ControlStatus.DARKLOOM_REQUIRED,
                    EvidenceKind.SEMANTIC_CONTRACT,
                    "exact reviewed revision and Darkloom integration contract match",
                )
            else:
                result = ControlResult(
                    control,
                    ControlStatus.UNVERIFIED,
                    EvidenceKind.SEMANTIC_CONTRACT,
                    "source seam exists; runtime routing remains unverified",
                )

        result = _probe_result(
            control,
            (runtime_probes or {}).get(control.id),
            result,
        )
        results.append(result)

    blocking_observed = {
        ControlStatus.UNVERIFIED,
        ControlStatus.PATCH_ONLY,
        ControlStatus.STALE,
        ControlStatus.INCOMPATIBLE,
    }
    if legacy:
        incompatible = [result for result in results if result.status in blocking_observed]
    else:
        blocking_declared = {
            ControlStatus.UPSTREAM_NATIVE,
            ControlStatus.DARKLOOM_REQUIRED,
        }
        incompatible = [
            result
            for result in results
            if result.control.declared_status in blocking_declared
            and result.status in blocking_observed
        ]
    if strict and incompatible:
        summary = "; ".join(f"{item.control.id}: {item.detail}" for item in incompatible)
        raise CompatibilityError(
            f"strict mode rejected incompatible Hermes integration: {summary}"
        )
    return results


def enable_strict_mode() -> bool:
    """Fail closed inside Darkloom's owned boundary only."""

    os.environ["TOR_STRICT_MODE"] = "1"
    return True


def is_strict_mode() -> bool:
    return os.environ.get("TOR_STRICT_MODE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


__all__ = [
    "CompatibilityError",
    "Control",
    "ControlResult",
    "ControlStatus",
    "EvidenceKind",
    "LEAKS",
    "Leak",
    "LeakSeverity",
    "LeakStatus",
    "check_tor_health",
    "enable_strict_mode",
    "find_hermes_root",
    "inject_subprocess_proxy_env",
    "is_strict_mode",
    "load_manifest",
    "register",
    "run_audit",
    "verify_compatibility",
]


if __name__ == "__main__":
    run_audit()
