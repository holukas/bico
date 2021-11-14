# IRGA75-A

## Variables
- DATA_SIZE ...  Data size of current data block, number of bytes in Licor 7500 record
  (2 = missing, 16 = available) 
- STATUS_CODE ... Status of IRGA data aquisition, see Table 7 in WE's sonicread.pdf
    - octal value converted to integer yields:
    - 0 .. Status OK, no problems (octal 0000)
    - 20 .. IRGA did not respond (0020)
    - 40 .. Status OK, old data used (0040)
    - 200 .. not OK, IRGA data are missing (0200)
- GA_DIAG_CODE ... IRGA diagnostic value
    - The cell diagnostic value is a 1 byte unsigned integer (value between 0 and 255, or in binary
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
    - 'output': 1 means that the var is written to the output stream of this data block, i.e. included in the
        output file.    
- H2O_CONC ... H2O concentration density, molar density
- CO2_CONC ... CO2 concentration density, molar density
- T_BOX ... Ambient temperature measured in the control box
- PRESS_BOX ... Atmospheric pressure measured in the control box
- COOLER_V ... Cooler voltage

## BICO Settings
- For an explanation of the different variable property settings, please see ```_help_bico_settings.md```.

*Before BICO, the binary conversion was done in FCT FluxCalcTool:*
- Old ID in FCT: li-7500
- Old data block in FCT: data_block_irga_li7500
- FCT Source code: --> https://gitlab.ethz.ch/holukas/fct-flux-calculation-tool

## Details

### Note about temperature and pressure measurements
#### From the LI-7500 manual ```LI-7500_Manual_V4_06360.pdf```
```
Notes about on-board temperature and pressure sensors
The LI-7500 internal temperature sensor has an accuracy of ±0.2 °C over a range from 0-70
°C. However, since it is positioned inside the control box the sensor will experience artificial
heating from various active electronic components on the circuit board. Since the box is
sealed it will also experience natural radiation loading from sunlight which will also heat up
the internal temperature of the box during daylight hours. The net result is that the internal
thermistor is perpetually exposed to a temperature that is higher than the actual ambient air.

The LI-7500 internal absolute pressure sensor has a range of 15-115 kPa. Its accuracy
(between temperatures of 0-85 °C) is ±1.5% full scale span. The enclosure includes a
pressure port so the internal pressure will be representative of ambient conditions.
As emphasized before the temperature and pressure sensors do not need to be very accurate
for output of density data.
```
This means that pressure is representative of ambient pressure, but temperature is higher than
true ambient temperature and should be substituted by an external measurement during flux
calculations.

#### Old Notes
I labelled the temperature and pressure coming from the IRGA75 as Ambient Temperature and Ambient Pressure
(not cell temp or cell press) b/c in the EddyPro help it says:
- ambient temperature	Ta	Temperature of ambient air as measured, for example, by an open-path analyzer (e.g., LI‑7500x)
- ambient pressure	Pa	Pressure of ambient air as measured, for example, by an open-path analyzer (e.g., LI‑7500x)
From <https://www.licor.com/env/support/EddyPro/topics/sensitive-and-nonsensitive-variables.html>

and

I think the IRGA75 measures the AMBIENT TEMPERATURE (not the average cell temperature), I checked the manual:
"An external temperature thermistor is included for measuring ambient temperature outside of the LI-7550 Analyzer
Interface Unit." and
"Temperature measured at LI-7550", "Pressure measured in LI-7550", p4-19

BUT: I made a short comparison and defined the column in the settings one time as CELL TEMPERATURE
and one time as AMBIENT TEMPERATURE and calculated the fluxes --> there were no differences in the calculated
fluxes! The only difference was that at the very end of the full_output file, the temperature column was one
time labelled as cell temp, and the other time as ambient temp.

AND: I also calculated fluxes with column set as Ambient Pressure, and the results were veeery slightly
different (99.9% the same)
2020-05-27

## Binary info
- B...unsigned char, integer, 1 Byte
- h...short integer, 2 Bytes
- ">"...big-endian, MSB most-significant Byte at lowest address
     Big-endian systems store the most significant byte of a word in the smallest address
- --> https://docs.python.org/3/library/struct.html
- --> https://docs.python.org/3.1/library/struct.html#format-characters