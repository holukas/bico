# IRGA72-B

## Variables
- DATA_SIZE ... Data size of current data block, number of bytes in Licor 7200 record
  (2 = missing, 25 = available)
- STATUS_CODE ... Status of IRGA data aquisition, see Table 7 in WE's sonicread.pdf
    - octal value converted to integer yields:
    - 0 .. Status OK, no problems (octal 0000)
    - 20 .. IRGA did not respond (0020)
    - 40 .. Status OK, old data used (0040)
    - 200 .. not OK, IRGA data are missing (0200)
- GA_DIAG_CODE ... IRGA diagnostic value
    - MSB, most significant bit; high-order bit
    - The cell diagnostic value in **IRGA72-B** is a **1 byte** unsigned integer
      with the following bit map (in order of how the code reads it, orig bit position in brackets):
        - (8,7,6,5,4) currently unknown info, but most likely a part of the 2-byte GA_DIAG_CODE from the
          IRGA72-A can be found in these bits
        - (3,2,1,0) SIGNAL_STRENGTH
          The gain 6.6666666666666666 has that many digits after the comma so that the calculated
          max signal strength is 100%. For example, if there is one digit after the comma less,
          then the max signal strength yields 99.99999999999999% instead of 100%.
    - 'output': 1 means that the var is written to the output stream of this data block,
      i.e. included in the output file.
- H2O_DRY ... H2O dry mole fraction (in dry air), mixing ratio, ppt (parts per THOUSAND)
- CO2_DRY ... CO2 dry mole fraction (in dry air), mixing ratio, ppm (parts per million)
- H2O_CONC ... H2O concentration density, molar density
- CO2_CONC ... CO2 concentration density, molar density
- T_CELL ... Temperature of the measurement cell
- PRESS_CELL ... Pressure in the measurement cell
- PRESS_BOX ... Pressure of the box containing the logger and the electronics of the GA
- COOLER_V ... Cooler voltage
- FLOW_VOLRATE ... Volume flow rate in the sampling line

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
- Old ID in FCT: li-7200
- Old data block in FCT: data_block_irga_li7200
- FCT Source code: --> https://gitlab.ethz.ch/holukas/fct-flux-calculation-tool

## Details
- Generally the same as IRGA72-A, but GA_DIAG_CODE is only 1 Byte in size and contains less information.

## Binary info
- B...unsigned char, integer, 1 Byte
- h...short integer, 2 Bytes
- ">"...big-endian, MSB most-significant Byte at lowest address
     Big-endian systems store the most significant byte of a word in the smallest address
- --> https://docs.python.org/3/library/struct.html
- --> https://docs.python.org/3.1/library/struct.html#format-characters
