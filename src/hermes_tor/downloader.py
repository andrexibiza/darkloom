"""Tor binary downloader.

Downloads and verifies a pinned Tor Expert Bundle for the current platform.
"""
import hashlib
import logging
import os
import shutil
import tarfile
import tempfile
from pathlib import Path

import httpx

from hermes_tor.constants import (
    get_download_url,
    get_tor_binary_path,
    TOR_BINARY_DIR,
    is_tor_installed,
)

logger = logging.getLogger(__name__)


class DownloadError(Exception):
    """Raised when Tor binary download fails."""


def download_tor_binary(
    progress_callback=None,
    force: bool = False,
    expected_sha256: str | None = None,
) -> Path:
    """Download and extract Tor Expert Bundle. Returns path to tor binary.

    Args:
        progress_callback: Optional callable(downloaded_bytes, total_bytes)
        force: If True, re-download even if already installed.
        expected_sha256: SHA-256 digest obtained from a trusted source. If not
            provided, ``HERMES_TOR_BUNDLE_SHA256`` must be set. The downloader
            deliberately does not fetch a checksum beside the archive, since a
            compromised download source could replace both.

    Returns:
        Path to the tor binary.

    Raises:
        DownloadError: If download or extraction fails.
    """
    if is_tor_installed() and not force:
        binpath = get_tor_binary_path()
        logger.info("Tor binary already installed at %s", binpath)
        return binpath

    url = get_download_url()
    logger.info("Downloading Tor Expert Bundle %s", url)

    expected_sha256 = expected_sha256 or os.environ.get("HERMES_TOR_BUNDLE_SHA256")
    if not expected_sha256 or len(expected_sha256) != 64:
        raise DownloadError(
            "A trusted SHA-256 checksum is required. Pass expected_sha256 or set "
            "HERMES_TOR_BUNDLE_SHA256."
        )
    try:
        bytes.fromhex(expected_sha256)
    except ValueError as e:
        raise DownloadError("The expected SHA-256 checksum is not hexadecimal") from e

    TOR_BINARY_DIR.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        tmppath = Path(tmp.name)

    try:
        # Stream download
        with httpx.stream("GET", url, follow_redirects=True, timeout=300) as resp:
            if resp.status_code >= 400:
                raise DownloadError(
                    f"HTTP {resp.status_code} downloading Tor bundle from {url}"
                )
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            with open(tmppath, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total)

        size_mb = downloaded / (1024 * 1024)
        logger.info("Downloaded %.1f MB", size_mb)

        actual_sha256 = hashlib.sha256(tmppath.read_bytes()).hexdigest()
        if actual_sha256.lower() != expected_sha256.lower():
            raise DownloadError(
                "Tor bundle SHA-256 mismatch: "
                f"expected {expected_sha256.lower()}, got {actual_sha256}"
            )

        # Extract into a new directory. Only ordinary files and directories are
        # accepted: links and special files can escape an otherwise safe path.
        logger.info("Extracting verified bundle to %s", TOR_BINARY_DIR)
        staging = Path(tempfile.mkdtemp(prefix="tor-bin-", dir=TOR_BINARY_DIR.parent))
        try:
            with tarfile.open(tmppath, "r:gz") as tar:
                root = staging.resolve()
                for member in tar.getmembers():
                    destination = (staging / member.name).resolve()
                    if root not in destination.parents and destination != root:
                        raise DownloadError(
                            f"Unsafe path in Tor bundle: {member.name!r}"
                        )
                    if not (member.isdir() or member.isreg()):
                        raise DownloadError(
                            f"Unsupported archive entry in Tor bundle: {member.name!r}"
                        )
                tar.extractall(path=staging)

            if TOR_BINARY_DIR.exists():
                shutil.rmtree(TOR_BINARY_DIR)
            staging.replace(TOR_BINARY_DIR)
        finally:
            if staging.exists():
                shutil.rmtree(staging)

        binpath = get_tor_binary_path()
        if not binpath.exists():
            raise DownloadError(
                f"Tor binary not found after extraction at {binpath}. "
                f"Contents of {TOR_BINARY_DIR}: {list(TOR_BINARY_DIR.iterdir())}"
            )

        # Make executable on Linux
        if os.name != "nt":
            binpath.chmod(0o755)

        logger.info("Tor binary ready at %s", binpath)
        return binpath

    except httpx.HTTPError as e:
        raise DownloadError(f"Failed to download Tor bundle: {e}") from e
    except tarfile.TarError as e:
        raise DownloadError(f"Failed to extract Tor bundle: {e}") from e
    finally:
        tmppath.unlink(missing_ok=True)
