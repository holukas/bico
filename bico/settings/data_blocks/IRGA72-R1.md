# IRGA72-R1

## Variables
- LI72_Ndx ... currently unknown
- LI72_CO2_DRY ... CO2 dry mole fraction (in dry air), mixing ratio, ppm (parts per million)
- LI72_H2O_DRY ... H2O dry mole fraction (in dry air), mixing ratio, ppt (parts per THOUSAND)
- LI72_T_CELL ... Temperature of the measurement cell, degC
- LI72_PRESS_CELL ... Pressure in the measurement cell, kPa
- LI72_COOLER_V ... Cooler voltage, V
- LI72_FLOW_VOLRATE ... Volume flow rate in the sampling line, slpm
- LI72_DIAG_CODE ... IRGA diagnostic value
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
          100% means very good signal. However, this value cannot be *exactly* reached if the conversion
          of `6.67` according to the manual is used. Instead, the maximum value is `100.05%`.
- LI72_AGC ... 
- LI72_STATUS_CODE ... Status of IRGA data aquisition
    - For the original description for files logged with `sonicread`, see Table 7 in WE's sonicread.pdf
    - Description for the original `sonicread` files:
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
