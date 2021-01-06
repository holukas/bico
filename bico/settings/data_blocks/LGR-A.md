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
- P_CELL ... Pressure in cell
- T_CELL ... Temperature in cell
- T_AMBIENT ... Ambient temperature (in box?)
- MIRROR_RINGDOWNTIME ... Mirror ring-down time
- FIT_FLAG ... *TODO*

## BICO Settings
- 'order' ... Order in the data block variable sequence
- 'bytes' ... Number of bytes in the binary data
- 'format' ... Format to convert from binary to integers, floats, etc.
- 'gain_on_signal' ... Gain that was applied to the raw data signal, to get to units *divide* by this gain
- 'offset_on_signal' ... Offset that was added to the raw data signal, to get to units *subtract* this offset
- 'apply_gain' ... Gain that is applied during conversion, e.g. to convert to different units if needed
- 'add_offset' ... Offset that is added during conversion, e.g. to convert to different units if needed
- 'units' ... Units
- 'datablock' ... Data block ID

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

