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

The data blocks implemented in `bico` are listed in the folder `src/settings/datablocks`.
The data block information that is used in code to convert binary to ASCII is given
in `.dblock` files. Accompanying information can be found in the respective `.md` files
in the same folder.

## Installation

- Latest release: https://github.com/holukas/bico/releases/latest
- `bico` can be installed directly from source by specifying the desired version number
  via `pip install https://github.com/holukas/bico/archive/refs/tags/v1.6.0.tar.gz`
- Using `poetry`, the file `pyproject.toml` can be used to install the environment that contains
  all required dependencies to run the script.

## Usage

### GUI

- `bico` can be run via GUI, e.g. in the `poetry` environment under Windows run
    - `python.exe .\bico.py -g` (for this you need to be in the folder `bico/src` where
      the file `bico.py` is located)

### CLI

- `bico` can also be run from the command-line interface (CLI). This can be used to  
  execute the script automatically at certain intervals. For example, `bico` is used to
  convert binary files to ASCII csv files for the site CH-OE2 once a day:
    - `python P:\Flux\RDS_calculations\_scripts\BICO\bico-v1.2.3\src\bico.py -f Z:\CH-OE2_Oensingen\20_ec_fluxes\2022\raw_data_ascii -d 8 -a`
    - `python` calls python
    - `P:\Flux\RDS_calculations\_scripts\BICO\bico-v1.2.3\src\bico.py` is the location of the script `bico.py`
    - `-f Z:\CH-OE2_Oensingen\20_ec_fluxes\2022\raw_data_ascii` specifies the folder where the `BICO.settings` file
      and the raw binary files for this site (CH-OE2) are located. The settings file can be created via the GUI, or
      edited directly with a text editor.
    - `-d 8` converts binary files from the last 8 days to ASCII
    - `-a` means "avoid duplicates", converts only binary files that were not converted before. The folder specified
      with `-f` is checked if a specific files was already converted. If the file already exists in the folder, then it
      is not converted again.
  