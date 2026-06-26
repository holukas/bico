# bico

**Binary Converter for converting ETH eddy covariance binary raw data to ASCII CSV files**

`bico` converts eddy covariance raw data files from a compressed binary format
to uncompressed ASCII (human-readable). Converted files can then be used for
flux calculations in EddyPro.

Instruments send their data in data blocks. One data block contains all data
from the respective instrument at the time of measurement. For example, the
data blocks sent by sonic anemometers comprises the wind variables, sonic temperature
and other variables. Data blocks from gas analyzers comprise concentrations (e.g., CO2,
H2O), instrument metrics (e.g., signal strength), among others.

The data blocks implemented in `bico` are listed in the folder `bico/settings/data_blocks`.
The data block information that is used in code to convert binary to ASCII is given
in `.dblock` files. Accompanying information can be found in the respective `.md` files
in the same folder.

## Installation

`bico` requires Python 3.12 and uses [`uv`](https://docs.astral.sh/uv/) for dependency management.

- Latest release: https://github.com/holukas/bico/releases/latest
- From a clone (recommended): run `uv sync` in the repository root to create the virtual environment (`.venv`)
  with all pinned dependencies from `pyproject.toml` / `uv.lock`, then run the app with `uv run bico` (see Usage).
- As a package: `bico` can also be installed directly from a release tag, e.g.
  `pip install https://github.com/holukas/bico/archive/refs/tags/v2.0.tar.gz`, which provides the `bico` command.

## Usage

`bico` is installed as a package and exposes a `bico` command (run `uv sync` once to set up the environment).
The same command is available as `uv run python -m bico`.

### GUI

- Start the GUI with:
    - `uv run bico -g`

### CLI

- `bico` can also be run from the command-line interface (CLI). This can be used to  
  execute the script automatically at certain intervals. For example, `bico` is used to
  convert binary files to ASCII csv files for the site CH-OE2 once a day:
    - `uv run bico -f Z:\CH-OE2_Oensingen\20_ec_fluxes\2022\raw_data_ascii -d 8 -a`
    - `uv run bico` runs the installed `bico` command (use `uv run --project <bico-dir> bico ...` from another directory,
      or activate the project's virtual environment)
    - `-f Z:\CH-OE2_Oensingen\20_ec_fluxes\2022\raw_data_ascii` specifies the folder where the `BICO.settings` file
      and the raw binary files for this site (CH-OE2) are located. The settings file can be created via the GUI, or
      edited directly with a text editor.
    - `-d 8` converts binary files from the last 8 days to ASCII
    - `-a` means "avoid duplicates", converts only binary files that were not converted before. The folder specified
      with `-f` is checked if a specific files was already converted. If the file already exists in the folder, then it
      is not converted again.
  