# bico
Binary Converter for ETH eddy covariance binary raw data to ASCII

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
