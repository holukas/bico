# QCL-A2

## Variables
- DATA_SIZE ... Data size of current data block, number of bytes in QCL record
  (2 = missing, 22 = available)
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
- CH4_DRY ... CH4 dry mole fraction (in **dry** air), mixing ratio, ppb (parts per billion)
- N2O_DRY ... N2O dry mole fraction (in **dry** air), mixing ratio, ppb
- CH4 ... CH4 molar fraction (in **humid** air), wet mole fraction
- T_CELL ... Temperature of the measurement cell
- PRESS_CELL ... Pressure in the measurement cell

## BICO Settings
- For an explanation of the different variable property settings, please see ```_help_bico_settings.md```.

*Before BICO, the binary conversion was done in FCT FluxCalcTool:*
- 
- Old ID in FCT: qcl_v1v6b
- Old data block in FCT: data_block_qcl_ver1_var6_b
- FCT Source code: --> https://gitlab.ethz.ch/holukas/fct-flux-calculation-tool

# Details
- Note that there is no H2O (was unintended at the time)!
- in WE's sonicread.pdf Table 2: QCL Version 1 Variant 6, QC-TILDAS ETHZ, 
  Columns: "CH4, N2O, H2O, TEMP, PRESS since V. 7.06 (2015-05-18)", but instead
  of H2O the ambient CH4 was logged by mistake, due to an undocumented? change 
  in the order of incoming data from the QCL
- Modified data acquisition to also record QCL temperature and pressure.
- Now there are 5 QCL variables that are detected (there were 3 in previous versions).

## Binary info
- B...unsigned char, integer, 1 Byte
- h...short integer, 2 Bytes
- ">"...big-endian, MSB most-significant Byte at lowest address
     Big-endian systems store the most significant byte of a word in the smallest address
- --> https://docs.python.org/3/library/struct.html
- --> https://docs.python.org/3.1/library/struct.html#format-characters