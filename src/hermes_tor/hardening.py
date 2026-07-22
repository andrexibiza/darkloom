"""Evidence-based audit of the Hermes integrations required by hermes-tor.

An environment variable or a patch in this repository is not proof that traffic
is protected.  Controls progress through four deliberately narrow states:
UNVERIFIED, PATCH_ONLY, MITIGATED (the expected files are installed), and
VERIFIED (an explicit runtime probe supplied by the caller passed).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import socket
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from importlib.resources import files
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


class ControlStatus(Enum):
    UNVERIFIED = "unverified"
    PATCH_ONLY = "patch_only"
    MITIGATED = "mitigated"
    VERIFIED = "verified"


class EvidenceKind(Enum):
    DOCUMENTATION = "documentation"
    PATCH_ARTIFACT = "patch_artifact"
    INSTALLED_PATCH = "installed_patch"
    RUNTIME_VERIFICATION = "runtime_verification"


@dataclass(frozen=True)
class Control:
    id: str
    title: str
    files: tuple[str, ...]
    hermes_revision: str
    patch_id: str
    documentation_only: bool = False


@dataclass(frozen=True)
class ControlResult:
    control: Control
    status: ControlStatus
    evidence: EvidenceKind
    detail: str


class CompatibilityError(RuntimeError):
    """The installed Hermes tree is not the versioned, patched integration."""


def load_manifest() -> dict:
    path = files("hermes_tor").joinpath("compatibility-manifest.json")
    return json.loads(path.read_text(encoding="utf-8"))


def _controls(manifest: dict) -> list[Control]:
    revision = manifest["upstream"]["required_commit"]
    return [
        Control(item["id"], item["title"], tuple(item.get("files", ())),
                revision, item["patch_id"], item.get("documentation_only", False))
        for item in manifest["controls"]
    ]


def find_hermes_root(explicit: Path | str | None = None) -> Path | None:
    """Find Hermes without treating the hermes-tor repository as Hermes."""
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
            ["git", "rev-parse", "HEAD"], cwd=root, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_compatibility(
    hermes_root: Path | str | None = None,
    *,
    strict: bool | None = None,
    runtime_probes: dict[str, Callable[[], bool]] | None = None,
) -> list[ControlResult]:
    """Compare the installed Hermes revision and files to the signed-off manifest.

    A matching file set is MITIGATED, not VERIFIED.  VERIFIED requires a named
    runtime probe from the embedding application; hermes-tor never infers network
    behaviour from configuration alone.
    """
    manifest = load_manifest()
    controls = _controls(manifest)
    strict = is_strict_mode() if strict is None else strict
    root = find_hermes_root(hermes_root)
    patch_path = Path(__file__).resolve().parents[2] / manifest["patch"]["path"]
    patch_ok = patch_path.is_file() and _sha256(patch_path) == manifest["patch"]["sha256"]
    revision = _git_revision(root) if root else None
    revision_ok = revision == manifest["upstream"]["required_commit"]
    expected = manifest["patched_files"]
    results: list[ControlResult] = []

    for control in controls:
        if control.documentation_only:
            result = ControlResult(control, ControlStatus.UNVERIFIED,
                                   EvidenceKind.DOCUMENTATION,
                                   "limitation documented; no enforcement is claimed")
        elif root is None or not revision_ok:
            detail = "Hermes installation not found" if root is None else (
                f"Hermes revision {revision or 'unknown'} != required {control.hermes_revision}")
            result = ControlResult(
                control, ControlStatus.PATCH_ONLY if patch_ok else ControlStatus.UNVERIFIED,
                EvidenceKind.PATCH_ARTIFACT if patch_ok else EvidenceKind.DOCUMENTATION, detail)
        else:
            bad = [name for name in control.files
                   if not (root / name).is_file() or _sha256(root / name) != expected[name]]
            if bad:
                result = ControlResult(control, ControlStatus.PATCH_ONLY,
                                       EvidenceKind.PATCH_ARTIFACT,
                                       "missing or incompatible installed files: " + ", ".join(bad))
            else:
                result = ControlResult(control, ControlStatus.MITIGATED,
                                       EvidenceKind.INSTALLED_PATCH,
                                       "required revision and patched file hashes match")
                probe = (runtime_probes or {}).get(control.id)
                if probe is not None:
                    try:
                        passed = probe() is True
                    except Exception as exc:  # a failed probe is evidence of no verification
                        result = ControlResult(control, ControlStatus.MITIGATED,
                                               EvidenceKind.INSTALLED_PATCH,
                                               f"runtime probe failed: {exc}")
                    else:
                        if passed:
                            result = ControlResult(control, ControlStatus.VERIFIED,
                                                   EvidenceKind.RUNTIME_VERIFICATION,
                                                   "caller-supplied runtime probe passed")

        results.append(result)

    incompatible = [r for r in results if not r.control.documentation_only and
                    r.status in (ControlStatus.UNVERIFIED, ControlStatus.PATCH_ONLY)]
    if strict and incompatible:
        summary = "; ".join(f"{r.control.id}: {r.detail}" for r in incompatible)
        raise CompatibilityError(f"strict mode rejected incompatible Hermes integration: {summary}")
    return results


def run_audit(hermes_root: Path | str | None = None) -> list[ControlResult]:
    results = verify_compatibility(hermes_root, strict=False)
    print("HERMES-TOR CONTROL AUDIT")
    print("Documentation is not a patch; a patch artifact is not installed; an installed patch is not runtime proof.")
    for result in results:
        c = result.control
        print(f"{c.id} {result.status.value.upper():<11} evidence={result.evidence.value}")
        print(f"  {c.title}")
        print(f"  required Hermes revision: {c.hermes_revision}")
        print(f"  patch identifier: {c.patch_id}")
        print(f"  detail: {result.detail}")
    return results


def inject_subprocess_proxy_env(env_dict: dict[str, str]) -> dict[str, str]:
    """Copy configured proxy variables; this does not prove child compatibility."""
    for key in ("ALL_PROXY", "HTTPS_PROXY", "HTTP_PROXY", "TOR_PROXY"):
        if os.environ.get(key):
            env_dict[key] = os.environ[key]
    return env_dict


def enable_strict_mode() -> bool:
    os.environ["TOR_STRICT_MODE"] = "1"
    logger.warning("TOR_STRICT_MODE enabled; compatibility will be checked before gateway startup")
    return True


def is_strict_mode() -> bool:
    return os.environ.get("TOR_STRICT_MODE", "").lower() in ("1", "true", "yes")


def check_tor_health(socks_port: int = 9050, timeout: float = 2.0) -> bool:
    """Only check that a local TCP listener exists; do not claim Tor routing."""
    try:
        with socket.create_connection(("127.0.0.1", socks_port), timeout=timeout):
            return True
    except OSError:
        return False


if __name__ == "__main__":
    run_audit(sys.argv[2] if len(sys.argv) > 2 else None)
