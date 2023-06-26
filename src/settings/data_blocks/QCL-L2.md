# QCL-L2

!!! THIS FORMAT IS UNCERTAIN, SEE DETAILS BELOW

## Variables

- DATA_SIZE ... Data size of current data block, number of bytes in QCL record
  (2 = missing, 16 = available)
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
- (???) _MAYBE_N2O_DRY ... CH4 dry mole fraction, mixing ratio, ppb --> uncertain format
- (???) _MAYBE_CO2_DRY ... CO2 dry mole fraction, mixing ratio, ppb --> uncertain format
- (???) _MAYBE_H2O_DRY ... H2O dry mole fraction, mixing ratio, ppb --> uncertain format
- (???) _MAYBE_DUMMY ... 2 extra bytes --> uncertain format

--> Assuming all are in dry mole fraction, as this was also the case for other QCL data.

## BICO Settings

- For an explanation of the different variable property settings, please see ```_help_bico_settings.md```.

*Before BICO, the binary conversion was done in FCT FluxCalcTool:*

- Old data block in FCT: data_block_qcl_ver1_var0
- FCT Source code: --> https://gitlab.ethz.ch/holukas/fct-flux-calculation-tool

# Details

- **It is possible that QCL measurements did not work during this time period, conversion to
  proper units did not yield realistic values**.
- Similar to `QCL-L`, but according to notes `QCL-L2` contains 2 extra Bytes.
- Conversion for `QCL-L` did work, but did not work for `QCL-L2`.
- This is the QCL version 1 variant 0 according to Werner Eugster's Table 3 in sonicread.pdf (see folder `/docs`)
- `QCL-L` and `QCL-L2` were used at site CH-LAE from `2005-09-30 11:00` until `2005-11-12 11:00`
- Raw binary data contains an extra 2 Bytes between `2005-09-30 11:00` and `2005-10-11 11:00` (format `QCL-L2`):
  during this time the status byte says data is 16 bytes (which is correct), but data are only stored
  in 12 Bytes + 2 Bytes header = 14 Bytes. Therefore, in that case we read 16 Bytes, but use only
  the first 12 Bytes after the 2-Byte header for the data output.
  Either way, the structure in both cases (16 or 14 Bytes length) seems to be the same.
- However, it seems that the CO2 measurements from the QCL are wrong according to this note in qcldoc_20200515.pdf, p5
  (see folder `/docs`): "It turned out that the CO2 concentration data were erroneous since a wrong absorption
  line had been chosen (the one for 13CO2)."

## Binary info

- B...unsigned char, integer, 1 Byte
- h...short integer, 2 Bytes
- ">"...big-endian, MSB most-significant Byte at lowest address
  Big-endian systems store the most significant byte of a word in the smallest address
- --> https://docs.python.org/3/library/struct.html
- --> https://docs.python.org/3.1/library/struct.html#format-characters