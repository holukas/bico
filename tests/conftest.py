"""Shared pytest setup for the bico test suite.

`bico` is an installed package (editable, via `uv sync`), so tests import the
conversion modules directly as `from bico.ops import bin`. Importing the `bico`
package itself is intentionally light and does not pull in PyQt5.
"""
from pathlib import Path

import bico

# Location of the installed `bico` package (holds settings/data_blocks).
PACKAGE_DIR = Path(bico.__file__).resolve().parent
DATA_DIR = Path(__file__).resolve().parent / "data"
