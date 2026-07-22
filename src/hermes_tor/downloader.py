"""Tor binary downloader.

Downloads the verified Tor Expert Bundle for the current platform.
No signature verification — the bundle is served over HTTPS from
archive.torproject.org and we pin a specific version.
"""
import logging
import os
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
) -> Path:
    """Download and extract Tor Expert Bundle. Returns path to tor binary.

    Args:
        progress_callback: Optional callable(downloaded_bytes, total_bytes)
        force: If True, re-download even if already installed.

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

    TOR_BINARY_DIR.mkdir(parents=True, exist_ok=True)

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

        # Extract
        logger.info("Extracting to %s", TOR_BINARY_DIR)
        with tarfile.open(tmppath, "r:gz") as tar:
            tar.extractall(path=TOR_BINARY_DIR)

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
