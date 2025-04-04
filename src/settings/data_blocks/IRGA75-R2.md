# IRGA75-R2

## Variables

- CO2_CONC ... CO2 concentration density, molar density (mmol m-3)
- H2O_CONC ... H2O concentration density, molar density (mmol m-3)
- TEMP_BOX ... Ambient temperature measured in the control box (degC)
- PRESS_BOX ... Atmospheric pressure measured in the control box (kPa)
- COOLER_V ... Cooler voltage (V)
- GA_DIAG_CODE ... IRGA diagnostic value
  - same as GA_DIAG_VALUE found in other datablocks
  - Originally, the cell diagnostic value is a 1 byte unsigned integer (value between 0 and 255, or in binary
    notation e.g. `00111001`) with the following bit map (in order of how the code reads it,
    orig bit position in brackets):
      - (7; first digit) CHOPPER: 1 = OK
      - (6; second digit) DETECTOR: 1 = OK
      - (5; third digit) PLL: 1 = OK
      - (4; fourth digit) SYNC: 1 = OK
      - (3,2,1,0; last four digits) AGC: 100% = bad (generally true, but check data files for exceptions),
        automatic gain control, window dirtiness, signal strength. However, this value can never reach 100%
        according to the binary notation, because AGC corresponds to the 4 right-most digits of the byte,
        and if these are e.g. `1111` than that corresponds to decimal `15`, which is multiplied
        by `6.25` to yield AGC = `93.75%`.
- AGC ... Automatic gain control from the LI-7500 (%)
  - low values close to 50 mean good signal
  - extracted from GA_DIAG_CODE
- STATUS_CODE ... Status of IRGA data aquisition, see Table 7 in WE's sonicread.pdf
    - same as STATUS_CODE found in other datablocks
    - octal value converted to integer yields:
    - 0 .. Status OK, no problems (octal 0000)
    - 20 .. IRGA did not respond (0020)
    - 40 .. Status OK, old data used (0040)
    - 200 .. not OK, IRGA data are missing (0200)

## BICO Settings

- This datablock does not need conversion because it is already logged in ASCII format.

## Details

- Datablock originates from the logging script `rECord`, which replaces the old logging script `sonicread`.
- More info about `sonicread` can be found in `docs/sonicread_20190503.pdf`.
