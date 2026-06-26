"""Keep the version in sync across the two places it is declared.

The version lives in `src/settings/_version.py` (the runtime source of truth,
shown in the GUI/log and bundled into the frozen build) and in `pyproject.toml`
(used by uv / the lockfile). They have to be edited together; this test fails
if they drift apart, so a forgotten update is caught instead of shipping a
wrong version number.
"""
import tomllib
from pathlib import Path

from conftest import PACKAGE_DIR

from bico.settings import _version

PYPROJECT = PACKAGE_DIR.parent / "pyproject.toml"


def test_pyproject_version_matches_version_module():
    with open(PYPROJECT, "rb") as f:
        pyproject_version = tomllib.load(f)["project"]["version"]
    assert pyproject_version == _version.__version__, (
        f"version mismatch: pyproject.toml has {pyproject_version!r}, "
        f"src/settings/_version.py has {_version.__version__!r}"
    )
