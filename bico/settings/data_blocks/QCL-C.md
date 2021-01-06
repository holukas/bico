# QCL-C

## Variables
- DATA_SIZE ... Data size of current data block, number of bytes in QCL record
  (2 = missing, 34 = available)
- STATUS_CODE ... Status information and extension variant information
  - Most significant bits of this byte (bits 4–7) contain the VARIANT information
    - On Windows systems (LSB): bits 0-3
    - Gives variant information according to Table 2 in WE's sonicread.pdf
    - Example: "6" means variant 6 as listed in Table 2
  - Least significant bits (bits 0–3) contain STATUS information
    - On Windows systems (LSB): bits 4-7    
    - converted to integers yields:
      - 0 ... Status OK (binary 0000), no bits set
      - 1 ... Old data used (0001), bit 1 set
      - 2 ... QCL did not respond (0010), bit 2 set
      - 8 ... QCL data missing (1000), bit 4 set
    - Original information found in ```extdata.h```:
      - define	QCL_STATUS_OK		0000	/* no bits set	*/
      - define	QCL_OLD_DATA_USED	0001	/* bit 1 set	*/
      - define	QCL_DID_NOT_RESPOND	0002    /* bit 2 set	*/
      - define QCL_DATA_MISSING	0010	    /* bit 4 set	*/
- CH4_DRY ... CH4 dry mole fraction, mixing ratio, ppb    
- N2O_DRY ... N2O dry mole fraction, mixing ratio, ppb    
- CO2_DRY ... CO2 dry mole fraction, mixing ratio, ppb    
- H2O_DRY ... H2O dry mole fraction, mixing ratio, ppb    
- T_CELL ... Temperature of the measurement cell
- PRESS_CELL ... Pressure in the measurement cell
- STATUS_WORD ... 
- VICI ... 

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
- Old ID in FCT: qcl_dav2015
- Old data block in FCT: data_block_qcl_dav2015
- FCT Source code: --> https://gitlab.ethz.ch/holukas/fct-flux-calculation-tool

# Details
- ICOS setup at CH-DAV, used starting in 2015-11-14
- in WE's sonicread.pdf Table 2: Version 1 Variant 6, QC-TILDAS ETHZ ICOS Davos, CH4,
  N2O, H2O, CO2, TEMP, PRESS, StatusW, VICI valves
- since sonicread V. 7.07 (2015-11-13)

## Binary info
- B...unsigned char, integer, 1 Byte
- h...short integer, 2 Bytes
- ">"...big-endian, MSB most-significant Byte at lowest address
     Big-endian systems store the most significant byte of a word in the smallest address
- --> https://docs.python.org/3/library/struct.html
- --> https://docs.python.org/3.1/library/struct.html#format-characters