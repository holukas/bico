# HS50-A

## Variables
- U ... First horizontal wind component (x)
- V ... Second horizontal wind component (y)
- W ... Vertical wind component (z)
- T_SONIC ... Sonic temperature
- SA_DIAG_TYPE ... Status type indicator (error, inclinometer, configuration) (StaA in manual)
- SA_DIAG_VAL ... Status value and information (StaD in manual)
- INC_XY ... Inclinometer, alternatively x (odd record numbers) and y (even record numbers)

*2017-07-25: EddyPro can currently not handle StaA and StaD, but it will be implemented soon for ICOS requirements*

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
- Old ID in FCT: hs-50_extended
- Old data block in FCT: data_block_sonic_hs_50_extended
- FCT Source code: --> https://gitlab.ethz.ch/holukas/fct-flux-calculation-tool

## Details
- Extended data logging to comply w/ ICOS requirements.
- Installed first in CH-DAV in 2017-07.
- from WE's email 2017-07-10:
    - the former 4 data bytes containing the two inclinometer angles are now used differently
    - first byte is the StaA byte from the sonic
    - second byte is the StaD byte from the sonic 
    - third and fourth byte are still a short integer as before, but now
     it contains the inclinometer X angle if the record number is an odd number,
     or the inclinometer Y angle if the record number is an even number

## Binary info
- B...unsigned char, integer, 1 Byte
- h...short integer, 2 Bytes
- ">"...big-endian, MSB most-significant Byte at lowest address
     Big-endian systems store the most significant byte of a word in the smallest address
- --> https://docs.python.org/3/library/struct.html
- --> https://docs.python.org/3.1/library/struct.html#format-characters
