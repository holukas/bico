"""Shared pytest setup for the bico test suite.

`bico` runs as a script (the `src/` directory is put on `sys.path` at runtime
rather than installed as a package), so the tests reproduce that by adding
`src/` to `sys.path`. This lets tests import the conversion modules directly
(`from ops import bin`) without importing the PyQt5 GUI in `bico.py`.
"""
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
DATA_DIR = Path(__file__).resolve().parent / "data"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
