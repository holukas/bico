# LGR-A

## Variables
- DATA_SIZE ... Data size of current data block, number of bytes in LGR record
  (2 = missing, 33 = available)
- STATUS_CODE ... Status of LGR data aquisition, see Table 11 and 13 in WE's sonicread.pdf
    - status code converted to integer yields:
    - 0 .. Status OK, no problems (corresponds to binary 0000)
    - 1 .. Old LGR record replicated (0001)
    - ? .. LGR did not respond (this is never used)
    - 8 .. not OK, LGR data are missing (1000)  
- CH4_DRY ... CH4 dry mole fraction (in **dry** air), mixing ratio, ppm (parts per million)
- N2O_DRY ... N2O dry mole fraction (in **dry** air), mixing ratio, ppm
- H2O ... H2O molar fraction (in **humid** air), wet mole fraction
- CH4 ... CH4 molar fraction (in **humid** air), wet mole fraction
- N2O ... N2O molar fraction (in **humid** air), wet mole fraction
- PRESS_CELL ... Pressure in cell, originally output in Torr, but is converted to hPa.
  This conversion is done because EddyPro cannot handle Torr as input units for cell pressure
  during flux calculations. 
- T_CELL ... Temperature in cell
- T_UNKNOWN ... Unknown temperature (similar to T_CELL, maybe around cell somewhere?)
- MIRROR_RINGDOWNTIME ... Mirror ring-down time
- FIT_FLAG ... *TODO*

## BICO Settings
- For an explanation of the different variable property settings, please see ```_help_bico_settings.md```.

*Before BICO, the binary conversion was done in FCT FluxCalcTool:*
- Old ID in FCT: lgr_ino2018
- Old data block in FCT: data_block_lgr_ino2018
- FCT Source code: --> https://gitlab.ethz.ch/holukas/fct-flux-calculation-tool

## Details
- none

## Binary info
- B...unsigned char, integer, 1 Byte
- h...short integer, 2 Bytes
- ">"...big-endian, MSB most-significant Byte at lowest address
     Big-endian systems store the most significant byte of a word in the smallest address
- --> https://docs.python.org/3/library/struct.html
- --> https://docs.python.org/3.1/library/struct.html#format-characters

