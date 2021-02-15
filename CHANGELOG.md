# BICO Changelog

## v0.4.0 - 15 Feb 2021
- changed: For QCL and LGR instruments, PRESS_CELL in Torr is now converted to hPa.  
  This conversion is done because EddyPro cannot handle Torr as input units for cell pressure during flux calculations. For the conversion, the parameter  
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

