# QCL-A3

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
- CH4_DRY ... CH4 dry mole fraction, mixing ratio, ppb    
- H2O_DRY ... H2O dry mole fraction, mixing ratio, ppb  
  (!) This H2O_DRY is a special case, because it does not provide the full 
  measurement resolution, more info below.  
- N2O_DRY ... N2O dry mole fraction, mixing ratio, ppb    
- DUMMY ... (!) Do not use
- T_CELL ... Temperature of the measurement cell

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
- Old ID in FCT: qcl_v1v6b_ch-cha_2018_2
- Old data block in FCT: data_block_qcl_ver1_var6_b_ch_cha_2018_2
- FCT Source code: --> https://gitlab.ethz.ch/holukas/fct-flux-calculation-tool

# Details
- This format was not intended.
- Note the different gains in comparison to other QCL-A formats.
- Note the different colum order in comparison to other QCL-A formats. 
- H2O does not have the full resolution and looks rather static in the raw data files. 
  However, it gives the correct order of magnitude and generally its values are realistic.
  Note that in this format H2O_DRY has a very different 'gain_on_signal' than in other
  QCL-A formats. In this format, the recorded H2O signal is too low, therefore the
  'gain_on_signal' was set to 0.001, which means that the raw signal is multiplied by 1000
  to yield ppb in the converted ASCII files. 

## Binary info
- B...unsigned char, integer, 1 Byte
- h...short integer, 2 Bytes
- ">"...big-endian, MSB most-significant Byte at lowest address
     Big-endian systems store the most significant byte of a word in the smallest address
- --> https://docs.python.org/3/library/struct.html
- --> https://docs.python.org/3.1/library/struct.html#format-characters