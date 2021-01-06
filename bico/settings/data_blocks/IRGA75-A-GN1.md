# IRGA75-A-GN1
Based on IRGA75-A but with a different gain on CO2_CONC.

## Variables
- DATA_SIZE ...  Data size of current data block, number of bytes in Licor 7500 record
  (2 = missing, 16 = available) 
- STATUS_CODE ... Status of IRGA data aquisition, see Table 7 in WE's sonicread.pdf
    - octal value converted to integer yields:
    - 0 .. Status OK, no problems (octal 0000)
    - 20 .. IRGA did not respond (0020)
    - 40 .. Status OK, old data used (0040)
    - 200 .. not OK, IRGA data are missing (0200)
- GA_DIAG_CODE ... IRGA diagnostic value
    - The cell diagnostic value is a 1 byte unsigned integer (value between 0 and 255) with the following bit map (in order of how the code reads it, orig bit position in brackets):
        - (7) CHOPPER: 1 = OK
        - (6) DETECTOR: 1 = OK
        - (5) PLL: 1 = OK
        - (4) SYNC: 1 = OK
        - (3,2,1,0) AGC: 100% = bad (generally true, but check data files for exceptions), automatic gain control, window dirtiness, signal strength
    - 'output': 1 means that the var is written to the output stream of this data block, i.e. included in the
        output file.    
- H2O_CONC ... H2O concentration density, molar density
- CO2_CONC ... CO2 concentration density, molar density  
  **A GAIN of 0.974 is applied to this signal to correct for the usage of a wrong calibration gas.  
  For more info, see here: https://www.swissfluxnet.ethz.ch/index.php/knowledge-base/wrong-calibration-gas-2017/**
- T_BOX ... Ambient temperature measured in the control box
- P_BOX ... Atmospheric pressure measured in the control box
- COOLER_V ... Cooler voltage

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
- Old ID in FCT: li-7500_co2_gain0974
- Old data block in FCT: data_block_irga_li7500_co2_gain0974
- FCT Source code: --> https://gitlab.ethz.ch/holukas/fct-flux-calculation-tool

## Details
Please see IRGA75-A.md for more info on the LI-7500.

## Binary info
- B...unsigned char, integer, 1 Byte
- h...short integer, 2 Bytes
- ">"...big-endian, MSB most-significant Byte at lowest address
     Big-endian systems store the most significant byte of a word in the smallest address
- --> https://docs.python.org/3/library/struct.html
- --> https://docs.python.org/3.1/library/struct.html#format-characters