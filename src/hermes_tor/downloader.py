"""Authenticated downloader for Tor Expert Bundles."""
import hashlib
import json
import logging
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

import httpx
from hermes_tor.policy import NetworkChannel, authorize

from hermes_tor.constants import (
    TOR_BINARY_DIR, TOR_RELEASE_SIGNING_FINGERPRINTS, TOR_RELEASE_SIGNING_KEY,
    TOR_VERSION, get_download_url, get_signature_url, get_tor_binary_path,
    is_tor_installed,
)

logger = logging.getLogger(__name__)
INSTALL_METADATA = "install-metadata.json"


class DownloadError(Exception):
    """Raised when an artifact cannot be downloaded or authenticated."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_signature(artifact: Path, signature: Path) -> str:
    """Verify a detached signature in an isolated keyring and return its signer."""
    if not TOR_RELEASE_SIGNING_KEY.is_file():
        raise DownloadError("Bundled Tor release signing key is missing")
    with tempfile.TemporaryDirectory(prefix="hermes-tor-gpg-") as home:
        home_path = Path(home)
        home_path.chmod(0o700)
        base = ["gpg", "--batch", "--no-tty", "--homedir", home]
        try:
            imported = subprocess.run(
                base + ["--status-fd", "1", "--import", str(TOR_RELEASE_SIGNING_KEY)],
                capture_output=True, text=True, check=False,
            )
            if imported.returncode:
                raise DownloadError(f"Could not import bundled Tor signing key: {imported.stderr.strip()}")
            checked = subprocess.run(
                base + ["--status-fd", "1", "--verify", str(signature), str(artifact)],
                capture_output=True, text=True, check=False,
            )
        except FileNotFoundError as exc:
            raise DownloadError("GnuPG is required to authenticate Tor downloads") from exc

    statuses = [line.removeprefix("[GNUPG:] ").split() for line in checked.stdout.splitlines()
                if line.startswith("[GNUPG:] ")]
    fatal = {"BADSIG", "ERRSIG", "EXPSIG", "EXPKEYSIG", "REVKEYSIG", "NO_PUBKEY"}
    failures = [parts[0] for parts in statuses if parts and parts[0] in fatal]
    valid = next((parts for parts in statuses if parts and parts[0] == "VALIDSIG"), None)
    if checked.returncode or failures or valid is None:
        reason = ", ".join(failures) or checked.stderr.strip() or "no valid signature"
        raise DownloadError(f"Tor bundle signature verification failed: {reason}")
    signer = valid[1].upper()
    primary = valid[-1].upper()
    if signer not in TOR_RELEASE_SIGNING_FINGERPRINTS and primary not in TOR_RELEASE_SIGNING_FINGERPRINTS:
        raise DownloadError(f"Tor bundle was signed by unknown key {signer}")
    return primary if primary in TOR_RELEASE_SIGNING_FINGERPRINTS else signer


def _metadata_path() -> Path:
    return TOR_BINARY_DIR / INSTALL_METADATA


def validate_installed_binary(*, strict: bool = True) -> bool:
    """Re-hash the executable against authenticated installation metadata."""
    binary = get_tor_binary_path()
    metadata_path = _metadata_path()
    if not binary.is_file():
        return False
    if not metadata_path.is_file():
        if strict:
            raise DownloadError("Tor installation has no signature-verification metadata")
        return False
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        signer = metadata["signer_fingerprint"].upper()
        expected = metadata["executable_sha256"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise DownloadError("Tor installation verification metadata is invalid") from exc
    if signer not in TOR_RELEASE_SIGNING_FINGERPRINTS:
        raise DownloadError(f"Tor installation records unknown signer {signer}")
    if not isinstance(expected, str) or _sha256(binary) != expected:
        raise DownloadError("Installed Tor executable does not match its verified digest")
    return True


def _download(url: str, destination: Path, progress_callback=None) -> None:
    with httpx.stream("GET", url, follow_redirects=True, timeout=300) as response:
        if response.status_code >= 400:
            raise DownloadError(f"HTTP {response.status_code} downloading {url}")
        total = int(response.headers.get("content-length", 0))
        downloaded = 0
        with destination.open("wb") as stream:
            for chunk in response.iter_bytes(chunk_size=65536):
                stream.write(chunk)
                downloaded += len(chunk)
                if progress_callback:
                    progress_callback(downloaded, total)


def download_tor_binary(progress_callback=None, force: bool = False) -> Path:
    """Download, authenticate, extract, and record a Tor Expert Bundle."""
    if is_tor_installed() and not force:
        validate_installed_binary(strict=True)
        return get_tor_binary_path()

    url = get_download_url()
    authorize(NetworkChannel.TOR_BOOTSTRAP)
    TOR_BINARY_DIR.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="hermes-tor-download-") as directory:
        artifact = Path(directory) / "bundle.tar.gz"
        signature = Path(directory) / "bundle.tar.gz.asc"
        try:
            _download(url, artifact, progress_callback)
            _download(get_signature_url(), signature)
            signer = _verify_signature(artifact, signature)
            archive_digest = _sha256(artifact)
            staging = Path(directory) / "extracted"
            staging.mkdir()
            with tarfile.open(artifact, "r:gz") as archive:
                archive.extractall(staging, filter="data")
            relative_binary = get_tor_binary_path().relative_to(TOR_BINARY_DIR)
            staged_binary = staging / relative_binary
            if not staged_binary.is_file():
                raise DownloadError(f"Tor binary not found in authenticated archive at {relative_binary}")
            if TOR_BINARY_DIR.exists():
                shutil.rmtree(TOR_BINARY_DIR)
            shutil.move(str(staging), TOR_BINARY_DIR)
            binary = get_tor_binary_path()
            if os.name != "nt":
                binary.chmod(0o755)
            metadata = {
                "schema_version": 1, "tor_version": TOR_VERSION, "artifact_url": url,
                "artifact_sha256": archive_digest, "executable_sha256": _sha256(binary),
                "signer_fingerprint": signer,
            }
            _metadata_path().write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            validate_installed_binary(strict=True)
            return binary
        except httpx.HTTPError as exc:
            raise DownloadError(f"Failed to download Tor artifact: {exc}") from exc
        except (tarfile.TarError, OSError) as exc:
            raise DownloadError(f"Failed to install Tor artifact: {exc}") from exc
