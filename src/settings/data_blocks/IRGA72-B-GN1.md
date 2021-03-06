# IRGA72-B-GN1
Based on IRGA72-B but with a different gain on CO2_DRY and CO2_CONC to correct for the 
usage of a wrong calibration gas.

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
          100% means very good signal. However, this value cannot be *exactly* reached if the conversion
          of `6.67` according to the manual is used. Instead, the maximum value is `100.05%`.
    - 'output': 1 means that the var is written to the output stream of this data block,
      i.e. included in the output file.
- H2O_DRY ... H2O dry mole fraction (in dry air), mixing ratio, ppt (parts per THOUSAND)
- CO2_DRY ... CO2 dry mole fraction (in dry air), mixing ratio, ppm (parts per million)
  **A GAIN of 0.974 is applied to this signal to correct for the usage of a wrong calibration gas.  
  For more info, see here: https://www.swissfluxnet.ethz.ch/index.php/knowledge-base/wrong-calibration-gas-2017/**
- H2O_CONC ... H2O concentration density, molar density
- CO2_CONC ... CO2 concentration density, molar density
  **A GAIN of 0.974 is applied to this signal to correct for the usage of a wrong calibration gas.  
  For more info, see here: https://www.swissfluxnet.ethz.ch/index.php/knowledge-base/wrong-calibration-gas-2017/**
- T_CELL ... Temperature of the measurement cell
- PRESS_CELL ... Pressure in the measurement cell
- PRESS_BOX ... Pressure of the box containing the logger and the electronics of the GA
- COOLER_V ... Cooler voltage
- FLOW_VOLRATE ... Volume flow rate in the sampling line

## BICO Settings
- For an explanation of the different variable property settings, please see ```_help_bico_settings.md```.

*Before BICO, the binary conversion was done in FCT FluxCalcTool:*
- Old ID in FCT: li-7200_co2_gain0974
- Old data block in FCT: data_block_irga_li7200_co2_gain0974
- FCT Source code: --> https://gitlab.ethz.ch/holukas/fct-flux-calculation-tool

## Details
Generally the same as IRGA72-A, with the difference that
- GA_DIAG_CODE is only 1 Byte in size and contains less information.
- CO2 measurements are corrected for the usage of a wrong calibration gas by applying a gain of 0.974.
  For more information about the calibration gas issue see here:
  https://www.swissfluxnet.ethz.ch/index.php/knowledge-base/wrong-calibration-gas-2017/

## Binary info
- B...unsigned char, integer, 1 Byte
- h...short integer, 2 Bytes
- ">"...big-endian, MSB most-significant Byte at lowest address
     Big-endian systems store the most significant byte of a word in the smallest address
- --> https://docs.python.org/3/library/struct.html
- --> https://docs.python.org/3.1/library/struct.html#format-characters
