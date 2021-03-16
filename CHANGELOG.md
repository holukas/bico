# BICO Changelog

## v0.5.2 - 17 Mar 2021
- added: datablock `IRGA72-A-GN1.dblock`

## v0.5.1 - 4 Mar 2021
- added: datablock `IRGA72-B-GN1.dblock`
- added: link to datablock descriptions
- the BICO run id is now shown in the "BICO finished." text message
- some minor text adjustments, clarifications in datablock descriptions

## v0.5.0 - 23 Feb 2021
- bug: wrong number of bits for SIGNAL_STRENGTH in `IRGA72-B.dblock`
- bug: reading order for extracted variables was wrong in `IRGA72-B.dblock`
- bug: wrong number of bits for AGC in `IRGA75-A.dblock` and `IRGA75-A-GN1.dblock` 
- bug: reading order for extracted variables was wrong in `IRGA75-A.dblock` and `IRGA75-A-GN1.dblock` 
- changed: the `'apply_gain'` option for `SIGNAL_STRENGTH` in IRGA72 datablocks was changed
  from `6.6666666666666666` to `6.67` to be more in line with their manual. This means that
  the max signal strength that can be reached is `100.05`:
  - `IRGA72-A.dblock`
  - `IRGA72-B.dblock`
- added: median is now also shown in hires plots
- added: link for CHANGELOG

## v0.4.0 - 15 Feb 2021
- changed: For QCL and LGR instruments, PRESS_CELL in Torr is now converted to hPa.  
  For the conversion, the parameter  
  `'apply_gain': 1.33322368` was used (was previously set to `1`).   
  **The following .dblock files are affected:**
    - LGR-A.dblock
    - QCL-A.dblock
    - QCL-A2.dblock
    - QCL-A4.dblock
    - QCL-C.dblock
    - not changed: QCL-A3.dblock because it does not record pressure
- changed: CHANGELOG is now a markup file (.md)

## v0.3.2 - 12 Feb 2021
- fixed: GUI now shows correct date for version

## v0.3.1 - 12 Feb 2021
- small bug: `IRGA75-A-GN1.dblock`: `datablock` was incorrectly named `IRGA75-A`
- added: CHANGELOG.txt

