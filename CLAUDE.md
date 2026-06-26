# CLAUDE.md

Guidance for working in the `bico` repository.

## Git / commit conventions

- **Never commit unless explicitly asked.** Make and stage changes freely, then stop and let the user request the commit.
- **Never add `Co-Authored-By:` trailers** (or any co-author/attribution) to commit messages or PR bodies. Write plain commit messages.
- The default branch is `master`. Prefer creating a new branch rather than committing directly to `master`.

## Project overview

`bico` (Binary Converter) converts ETH eddy covariance raw data from a compressed binary format to uncompressed ASCII CSV files for use in EddyPro. It is an installed package (`bico/`) exposing a `bico` console command, with both a PyQt5 GUI and a CLI.

## Environment & tooling

- Dependency management uses [`uv`](https://docs.astral.sh/uv/) (migrated from poetry). Source of truth: `pyproject.toml` (PEP 621), locked in `uv.lock`.
- Requires Python 3.12.
- Set up the environment: `uv sync`
- Run the GUI: `uv run bico -g`
- Run headless: `uv run bico -f <folder> -d <days> -a` (also available as `uv run python -m bico ...`)
- Run the tests: `uv run pytest`

## Testing

- Tests live in `tests/` and use `pytest` (a dev dependency, in the `dev` group of `pyproject.toml`).
- `tests/conftest.py` exposes the installed package location; tests import the conversion modules directly
  (`from bico.ops import bin`). Importing the `bico` package is light and does not pull in the PyQt5 GUI.
- The main test is a golden-file test: it converts a small truncated real binary
  (`tests/data/*.X00`) and asserts the output matches a committed expected CSV (`tests/data/*.golden.csv`).
  The conversion output must stay byte-for-byte stable, so this guards against regressions in converted values.

## Architecture notes

- `bico/bico.py` — entry point (`main_cli`); `BicoEngine` (conversion), `BicoGUI`, `BicoFolder` (CLI). `bico/__main__.py` enables `python -m bico`.
- `bico/ops/` — `bin.py` (binary->ASCII core, struct/mmap), `file.py` (search/IO), `stats.py`, `vis.py`, `setup.py`, `cli.py`.
- `bico/settings/data_blocks/*.dblock` — data-driven format specs (one per instrument/logging variant), each parsed as Python dict literals. Adding instrument support means adding a `.dblock` file, not changing code. Companion `.md` files document each block.
- Internal imports are package-qualified (`from bico.ops import ...`); the package is installed editable via `uv sync` and `[project.scripts] bico` points to `bico.bico:main_cli`.
- Version is set in `bico/settings/_version.py` and `pyproject.toml` (kept in sync by a test).
