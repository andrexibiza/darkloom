"""Security regression tests for Tor bundle installation."""

import hashlib
import io
import os
import stat
import tarfile
from pathlib import Path

import pytest

import hermes_tor.downloader as downloader
from hermes_tor.downloader import (
    BundleManifest,
    DownloadError,
    _atomic_install,
    _extract_verified_archive,
    _secure_install_parent,
)


def _archive(path: Path, members: list[tuple[str, bytes, str, str | None]]) -> Path:
    """Create members as (name, contents, kind, link target)."""
    with tarfile.open(path, "w:gz") as tar:
        for name, contents, kind, target in members:
            info = tarfile.TarInfo(name)
            if kind == "file":
                info.size = len(contents)
                info.mode = 0o644
                tar.addfile(info, io.BytesIO(contents))
            elif kind == "executable":
                info.size = len(contents)
                info.mode = 0o755
                tar.addfile(info, io.BytesIO(contents))
            elif kind == "symlink":
                info.type = tarfile.SYMTYPE
                info.linkname = target or ""
                tar.addfile(info)
            elif kind == "hardlink":
                info.type = tarfile.LNKTYPE
                info.linkname = target or ""
                tar.addfile(info)
            elif kind == "fifo":
                info.type = tarfile.FIFOTYPE
                tar.addfile(info)
    return path


def _manifest(files=("tor/tor",), executables=("tor/tor",)) -> BundleManifest:
    digests = {
        name: hashlib.sha256(b"safe executable").hexdigest() for name in executables
    }
    return BundleManifest(frozenset(files), digests)


@pytest.mark.parametrize("name", ["../escaped", "tor/../../escaped"])
def test_rejects_path_traversal(tmp_path, name):
    archive = _archive(tmp_path / "bad.tar.gz", [(name, b"bad", "executable", None)])
    with pytest.raises(DownloadError, match="traversal"):
        _extract_verified_archive(archive, tmp_path / "stage", _manifest())
    assert not (tmp_path / "escaped").exists()


@pytest.mark.parametrize("name", ["/tmp/absolute", r"C:\absolute"])
def test_rejects_absolute_paths(tmp_path, name):
    archive = _archive(tmp_path / "bad.tar.gz", [(name, b"bad", "executable", None)])
    with pytest.raises(DownloadError, match="absolute|traversal"):
        _extract_verified_archive(archive, tmp_path / "stage", _manifest())


def test_rejects_escaping_symlink(tmp_path):
    archive = _archive(
        tmp_path / "bad.tar.gz", [("tor/link", b"", "symlink", "../../outside")]
    )
    with pytest.raises(DownloadError, match="leaves staging"):
        _extract_verified_archive(
            archive, tmp_path / "stage", _manifest(("tor/link",), ())
        )


def test_rejects_duplicate_members(tmp_path):
    archive = _archive(
        tmp_path / "bad.tar.gz",
        [("tor/tor", b"safe executable", "executable", None)] * 2,
    )
    with pytest.raises(DownloadError, match="duplicate"):
        _extract_verified_archive(archive, tmp_path / "stage", _manifest())


def test_rejects_oversized_expansion(tmp_path):
    archive = _archive(
        tmp_path / "bad.tar.gz", [("tor/tor", b"safe executable", "executable", None)]
    )
    with pytest.raises(DownloadError, match="maximum expanded size"):
        _extract_verified_archive(
            archive, tmp_path / "stage", _manifest(), max_expanded_size=4
        )


def test_rejects_unexpected_executable(tmp_path):
    archive = _archive(
        tmp_path / "bad.tar.gz",
        [
            ("tor/tor", b"safe executable", "file", None),
            ("tor/surprise", b"malware", "executable", None),
        ],
    )
    with pytest.raises(DownloadError, match="unexpected executable"):
        _extract_verified_archive(
            archive,
            tmp_path / "stage",
            _manifest(("tor/tor", "tor/surprise")),
        )


@pytest.mark.parametrize("kind", ["hardlink", "fifo"])
def test_rejects_dangerous_member_types(tmp_path, kind):
    archive = _archive(
        tmp_path / "bad.tar.gz", [("tor/danger", b"", kind, "tor/tor")]
    )
    with pytest.raises(DownloadError, match="hard link|device or FIFO"):
        _extract_verified_archive(
            archive, tmp_path / "stage", _manifest(("tor/danger",), ())
        )


def test_verified_install_replaces_live_tree_only_after_validation(tmp_path):
    live = tmp_path / "tor-bin"
    live.mkdir()
    (live / "old").write_text("last verified")
    staging = tmp_path / ".staging"
    staging.mkdir()
    (staging / "new").write_text("replacement")

    _atomic_install(staging, live)

    assert not (live / "old").exists()
    assert (live / "new").read_text() == "replacement"
    assert not list(tmp_path.glob(".tor-bin.previous-*"))


def test_valid_bundle_verifies_digest_and_permissions(tmp_path):
    archive = _archive(
        tmp_path / "good.tar.gz",
        [
            ("tor/tor", b"safe executable", "executable", None),
            ("data/geoip", b"data", "file", None),
        ],
    )
    staging = tmp_path / "stage"
    staging.mkdir()
    _extract_verified_archive(
        archive, staging, _manifest(("tor/tor", "data/geoip"))
    )
    assert (staging / "tor/tor").read_bytes() == b"safe executable"
    assert (staging / "data/geoip").read_bytes() == b"data"


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission regression test")
def test_install_parent_is_private_with_permissive_umask(tmp_path):
    parent = tmp_path / "shared" / "tor"
    previous = os.umask(0)
    try:
        _secure_install_parent(parent)
    finally:
        os.umask(previous)

    assert stat.S_IMODE(parent.stat().st_mode) == 0o700


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission regression test")
def test_validator_rejects_locally_replaceable_install_tree(tmp_path, monkeypatch):
    install = tmp_path / "shared" / "tor-bin"
    install.mkdir(parents=True)
    install.parent.chmod(0o777)
    install.chmod(0o700)
    monkeypatch.setattr(downloader, "TOR_BINARY_DIR", install)

    with pytest.raises(DownloadError, match="not private"):
        downloader._validate_install_permissions()
