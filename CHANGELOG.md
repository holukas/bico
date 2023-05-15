# BICO Changelog

## v1.4.0 - 15 May 2023

- Now using `poetry` for dependency management (instead of `conda`)
    - The package versions for `pandas`, `numpy`, `matplotlib` and others remain the same as before
- Removed: `start_bico.py` (is no longer used)
- Removed: `environment.yml` (is no longer used)

## v1.3.0 - 11 Aug 2022

- Added: new datablock `QCL-C3`
- Added: More descriptions in GUI about what numbers mean, e.g. using `0` for `Row Limit Per File`
- Improved: Better (clearer) plotting of high-res data
- Changed: Hi-res and aggregated plots do not use scientific notation (e.g., `1e9`) or an offset (e.g., `+1e9`)
- Updated links in sidebar
- CRITICAL FIX: In `bin.py`, the return of line `self.check_if_dblock_size_zero(dblock_true_size=dblock_true_size)`
  was not stored in any variable, therefore this check seems to not have worked. Line was changed to
  `end_of_data_reached = self.check_if_dblock_size_zero(dblock_true_size=dblock_true_size)`. Then indentation was
  removed for the following break command `if end_of_data_reached: break # Stop for loop` to really stop the
  for-loop. I assume this does not have major implications on the conversion but only acts as an additional
  check if data are still available.

## v1.2.3 - 7 Dec 2021

- Fixed: Script folder was wrong when running from CLI

## v1.2.2 - 7 Dec 2021

- Added: CLI flag `-a` to avoid duplicates when converting files.
  Is only considered if script is started via CLI.
- Added: CLI flag `-d` to convert only the most recent number of days, e.g. `-d 3` to convert files from
  the last 3 days. Is only considered if script is started via CLI.
- Changed: Settings file is now called `BICO.settings`

## v1.2.1 - 5 Dec 2021

- Added automatic detection of working directory

## v1.2 - 5 Dec 2021

- Included CLI support for automatic script execution without GUI
- Code refactoring: separated the conversion functions (`BicoEngine`) from GUI (`BicoGUI`)
- Added: new datablock `QCL-C2` (used at CH-DAV)
- Changed: switching back to `conda` for dependency management

## v1.1 - 14 Nov 2021

- `BICO` is now using `poetry` for dependency management and packaging
- The virtual env created by `poetry` is specific to `BICO` and stored alongside the source code in folder `.venv`
- Updated Python version to 3.9.7, packages were updated to their newest versions
- Removed `conda` env
- Renamed source code folder to `src`
- Adjusted folder structure
- Added support for CLI execution
- Solved some minor warnings

## v1.0 - 20 Sep 2021

- Updated version number to 1.
- bug: removed small naming bug in `HS100-A.md` (`SA_DIAG_TYPE`, `SA_DIAG_VAL`)
- bug: `QCL-A3` was incorrectly labelled `QCL-A` in converted raw data files

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

## Ideas

- TODO LATER parallelize, multiprocessing?
  `
  import multiprocessing as mp
  print("Number of processors: ", mp.cpu_count())
  `
