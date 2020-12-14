# IRGA72-A

## Variables
- DATA_SIZE ... Data size of current data block, number of bytes in Licor 7200 record
  (2 = missing, 26 = available)
- STATUS_CODE ... Status of IRGA data aquisition, see Table 7 in WE's sonicread.pdf
    - octal value converted to integer yields:
    - 0 .. Status OK, no problems (octal 0000)
    - 20 .. IRGA did not respond (0020)
    - 40 .. Status OK, old data used (0040)
    - 200 .. not OK, IRGA data are missing (0200)
- GA_DIAG_CODE ... IRGA diagnostic value
    - MSB, most significant bit; high-order bit
    - The cell diagnostic value is a 2 byte unsigned integer (value between 0 and 8191)
      with the following bit map (in order of how the code reads it, orig bit position in brackets):
        - (15,14,13) UNUSED
        - (12) HEAD_DETECT: sensor head attached to LI-7550; 1 = LI-7200
        - (11) T_OUTLET: 1 = thermocouple OK; 0 = thermocouple open circuit
        - (10) T_INLET: 1 = thermocouple OK; 0 = thermocouple open circuit
        - (9) AUX_INPUT: 1 = internal reference voltages OK;
          0 = internal reference voltages not OK, analyzer interface unit needs service
        - (8) DIFF_PRESS: 1 = good, 0.1 to 4.9V; 0 = out of range; d=delta
        - (7) CHOPPER: 1 = chopper wheel temp is near setpoint; 0 = not near setpoint
        - (6) DETECTOR: 1 = detector temp is near setpoint; 0 = not near setpoint
        - (5) PLL: 1 = OK; lock bit, indicates that optical wheel is rotating at the correct rate
        - (4) SYNC: always set to 1 (OK)
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
- Old ID in FCT: li-7200_extended
- Old data block in FCT: data_block_irga_li7200_extended
- FCT Source code: --> https://gitlab.ethz.ch/holukas/fct-flux-calculation-tool

## Details
- Extended data logging to comply w/ ICOS requirements.
- Installed in CH-DAV in 2017-07.
- Returns 13 columns.
- from WE's email 2017-07-10:
- The length of the LI7200 records have increased from 25 to 26 bytes;
- the extra byte for the 2-byte status is inserted before the former status byte
  was found in the beginning of the structure;
- thus, the 1-byte status is now a short int 2-byte variable
- (MSB format like all other data except those in the 29-byte header)

## Binary info
- B...unsigned char, integer, 1 Byte
- h...short integer, 2 Bytes
- ">"...big-endian, MSB most-significant Byte at lowest address
     Big-endian systems store the most significant byte of a word in the smallest address
- --> https://docs.python.org/3/library/struct.html
- --> https://docs.python.org/3.1/library/struct.html#format-characters
