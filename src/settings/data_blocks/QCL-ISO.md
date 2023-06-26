# QCL-ISO

!!! THIS FORMAT IS UNCERTAIN, SEE DETAILS BELOW

## Variables

- DATA_SIZE ... Data size of current data block, number of bytes in QCL record
  (2 = missing, 26 = available)
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
            - define QCL_STATUS_OK 0000 /* no bits set    */
            - define QCL_OLD_DATA_USED 0001 /* bit 1 set    */
            - define QCL_DID_NOT_RESPOND 0002 /* bit 2 set    */
            - define QCL_DATA_MISSING 0010 /* bit 4 set    */
- 12C16O18O ... --> uncertain format
- 12C16O2 ... --> uncertain format
- 13C16O2 ... --> uncertain format
- CO2_CALIBRATED ... --> uncertain format
- d13C ... --> uncertain format
- d18O ... --> uncertain format

--> Assuming all are in dry mole fraction, as this was also the case for other QCL data.

## BICO Settings

- For an explanation of the different variable property settings, please see ```_help_bico_settings.md```.

*Before BICO, the binary conversion was done in FCT FluxCalcTool:*

- Old data block in FCT: data_block_qcl_ver1_var2
- FCT Source code: --> https://gitlab.ethz.ch/holukas/fct-flux-calculation-tool

# Details

- Isotope measurements
- Columns were documented in the script `qcl.c` of the QCL eddy covariance data acquisition program `qclread`:
  > V 1.04, 16.05.2008: new mode to add three more numbers to the
    QCL with 12C16O18O, 12C16O2, and 13C16O2: 12CO2 calib, d13C, d18O  
  > V 1.03, 23.08.2007: modification to be ready for the newest QCL
   campaign with EMPA to measure 12C16O18O, 12C16O2, and 13C16O2
- This is the QCL version 1 variant 2 according to Werner Eugster's Table 3 in sonicread.pdf (see folder `/docs`)
- `QCL-ISO` and `QCL-L2` was used at site CH-LAE in 2008.

## Binary info

- B...unsigned char, integer, 1 Byte
- h...short integer, 2 Bytes
- ">"...big-endian, MSB most-significant Byte at lowest address
  Big-endian systems store the most significant byte of a word in the smallest address
- --> https://docs.python.org/3/library/struct.html
- --> https://docs.python.org/3.1/library/struct.html#format-characters