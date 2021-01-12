# HS50-B

## Variables
- U ... First horizontal wind component (x)
- V ... Second horizontal wind component (y)
- W ... Vertical wind component (z)
- T_SONIC ... Sonic temperature
- INC_X ... Inclinometer x
- INC_Y ... Inclinometer y

## BICO Settings
- For an explanation of the different variable property settings, please see ```_help_bico_settings.md```.

*Before BICO, the binary conversion was done in FCT FluxCalcTool:*
- Old ID in FCT: hs-50
- Old data block in FCT: data_block_sonic_hs_50
- FCT Source code: --> https://gitlab.ethz.ch/holukas/fct-flux-calculation-tool

## Details
- Original format with which HS-50 data were logged

## Binary info
- B...unsigned char, integer, 1 Byte
- h...short integer, 2 Bytes
- ">"...big-endian, MSB most-significant Byte at lowest address
     Big-endian systems store the most significant byte of a word in the smallest address
- --> https://docs.python.org/3/library/struct.html
- --> https://docs.python.org/3.1/library/struct.html#format-characters
