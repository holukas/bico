# CLAUDE.md

Guidance for working in the `bico` repository.

## Git / commit conventions

- **Never commit unless explicitly asked.** Make and stage changes freely, then stop and let the user request the commit.
- **Never add `Co-Authored-By:` trailers** (or any co-author/attribution) to commit messages or PR bodies. Write plain commit messages.
- The default branch is `master`. Prefer creating a new branch rather than committing directly to `master`.

## Project overview

`bico` (Binary Converter) converts ETH eddy covariance raw data from a compressed binary format to uncompressed ASCII CSV files for use in EddyPro. It runs as an application (not an installed package) via `src/bico.py`, with both a PyQt5 GUI and a CLI.

## Environment & tooling

- Dependency management uses [`uv`](https://docs.astral.sh/uv/) (migrated from poetry). Source of truth: `pyproject.toml` (PEP 621), locked in `uv.lock`.
- Requires Python 3.12.
- Set up the environment: `uv sync`
- Run the GUI: `uv run python src\bico.py -g`
- Run headless: `uv run python src\bico.py -f <folder> -d <days> -a`
- Run the tests: `uv run pytest`

## Testing

- Tests live in `tests/` and use `pytest` (a dev dependency, in the `dev` group of `pyproject.toml`).
- `tests/conftest.py` puts `src/` on `sys.path` so tests import the conversion modules directly
  (`from ops import bin`) without importing the PyQt5 GUI.
- The main test is a golden-file test: it converts a small truncated real binary
  (`tests/data/*.X00`) and asserts the output matches a committed expected CSV (`tests/data/*.golden.csv`).
  The conversion output must stay byte-for-byte stable, so this guards against regressions in converted values.

## Architecture notes

- `src/bico.py` — entry point; `BicoEngine` (conversion), `BicoGUI`, `BicoFolder` (CLI).
- `src/ops/` — `bin.py` (binary->ASCII core, struct/mmap), `file.py` (search/IO), `stats.py`, `vis.py`, `setup.py`, `cli.py`.
- `src/settings/data_blocks/*.dblock` — data-driven format specs (one per instrument/logging variant), each parsed as Python dict literals. Adding instrument support means adding a `.dblock` file, not changing code. Companion `.md` files document each block.
- Version is set in `src/settings/_version.py` and `pyproject.toml`.
