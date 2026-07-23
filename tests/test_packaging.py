"""Installed-package smoke tests for the declared runtime dependency set."""

import os
from pathlib import Path
import subprocess
import venv


def test_declared_dependencies_provide_socks_transport(tmp_path):
    """A clean install (without dev extras) must pass the local SOCKS check."""
    root = Path(__file__).resolve().parents[1]
    env_dir = tmp_path / "installed"
    venv.EnvBuilder(with_pip=True).create(env_dir)
    python = env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

    subprocess.run(
        [str(python), "-m", "pip", "install", "--disable-pip-version-check", str(root)],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            str(python),
            "-c",
            "from hermes_tor.socks_support import require_socks_support; "
            "require_socks_support('socks5://127.0.0.1:1')",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
