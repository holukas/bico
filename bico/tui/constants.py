"""Shared constants, field specs and small helpers for the bico TUI.

Split out of ``app.py`` so the option lists, form field specs, help text and the
path-parsing helpers can be imported by the widgets, screens and the app without
a circular dependency. ``app.py`` re-exports the names tests rely on.
"""
from pathlib import Path

import bico
from bico.settings import _version as info

# Rows converted for a test run (a quick dry conversion of the first file).
TEST_RUN_ROWS = 20
# Date inputs must look like 2025-12-31 23:59
DATE_PATTERN = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}'

# Package locations, resolved independently of the working directory.
PACKAGE_DIR = Path(bico.__file__).resolve().parent
SETTINGS_DIR = PACKAGE_DIR / 'settings'

# Option lists (kept in step with the data-block specs in settings/data_blocks).
SITES = ['CH-AES', 'CH-AWS', 'CH-CHA', 'CH-DAE', 'CH-DAV', 'CH-DAS', 'CH-FOR',
         'CH-FRU', 'CH-HON', 'CH-INO', 'CH-LAE', 'CH-LAS', 'CH-OE2', 'CH-TAN']
HEADERS = ['WECOM3']
SONIC_ANEMOMETERS = ['HS50-A', 'HS50-B', 'HS100-A', 'R2-A', 'R350-A', 'R350-B', '-None-']
GAS_ANALYZERS = ['IRGA72-A', 'IRGA72-A-GN1', 'IRGA72-B', 'IRGA72-B-GN1', 'IRGA75-A',
                 'IRGA75-A-GN1', 'LGR-A', 'QCL-A', 'QCL-A2', 'QCL-A3', 'QCL-A4', 'QCL-B',
                 'QCL-C', 'QCL-C2', 'QCL-C3', 'QCL-D', 'QCL-ISO', 'QCL-L', 'QCL-L2', '-None-']
COMPRESSION = ['gzip', 'None']

# Field spec: (key, label, kind, options). `kind` is 'select' | 'input' |
# 'int' | 'switch'. Keys match bico.settings keys, except the run-only options
# 'days' and 'avoidduplicates', which are not persisted to the settings file.
INSTRUMENT_FIELDS = [
    ('site', 'Site', 'select', SITES),
    ('header', 'Header', 'select', HEADERS),
    ('instrument_1', 'Instr 1 (sonic)', 'select', SONIC_ANEMOMETERS),
    ('instrument_2', 'Instr 2 (gas)', 'select', GAS_ANALYZERS),
    ('instrument_3', 'Instr 3 (gas)', 'select', GAS_ANALYZERS),
]
RAWDATA_FIELDS = [
    ('dir_source', 'Source folder', 'path', None),
    ('start_date', 'Start date', 'input', None),
    ('end_date', 'End date', 'input', None),
    ('filename_datetime_format', 'Filename dt format', 'input', None),
    ('file_size_min', 'Min size (bytes)', 'int', None),
    ('file_limit', 'File limit (0=all)', 'int', None),
    ('row_limit', 'Row limit (0=all)', 'int', None),
    ('select_random_files', 'Random files (0=no)', 'int', None),
]
OUTPUT_FIELDS = [
    ('dir_out', 'Output folder', 'path', None),
    ('output_folder_name_prefix', 'Folder prefix', 'input', None),
    ('file_compression', 'Compression', 'select', COMPRESSION),
    ('num_processes', 'Processes (0=auto)', 'int', None),
    ('add_instr_to_varname', 'Instr in varname', 'switch', None),
    ('plot_file_availability', 'Plot availability', 'switch', None),
    ('plot_ts_hires', 'Plot hi-res series', 'switch', None),
    ('plot_histogram_hires', 'Plot hi-res histo', 'switch', None),
    ('plot_ts_agg', 'Plot agg series', 'switch', None),
]
RUN_FIELDS = [
    ('days', 'Recent days (0=range)', 'int', None),
    ('avoidduplicates', 'Avoid duplicates', 'switch', None),
]

ALL_FIELDS = INSTRUMENT_FIELDS + RAWDATA_FIELDS + OUTPUT_FIELDS + RUN_FIELDS
FIELD_KIND = {key: kind for key, _, kind, _ in ALL_FIELDS}

# Full explanations shown on hover (labels are abbreviated for the compact layout).
FIELD_HINTS = {
    'dir_source': 'Folder with the binary files. Searched recursively, so files in '
                  'subfolders are found too (not only this folder).',
    'start_date': 'Range start, INCLUSIVE. Format: 2025-12-31 23:59 (YYYY-MM-DD HH:MM)',
    'end_date': 'Range end, INCLUSIVE. Format: 2025-12-31 23:59 (YYYY-MM-DD HH:MM)',
    'filename_datetime_format': 'Datetime pattern in the binary filenames, incl. extension, '
                                'e.g. yyyymmddHH.CMM. Also determines which files are searched.',
    'file_size_min': 'Minimum file size in bytes; smaller files are skipped',
    'file_limit': 'Maximum number of files to convert (0 = no limit)',
    'row_limit': 'Maximum rows read per file (0 = no limit)',
    'select_random_files': 'Convert this many randomly chosen files (0 = no)',
    'output_folder_name_prefix': 'Prefix for the run output folder name',
    'num_processes': 'Worker processes for parallel conversion (0 = auto: cpu_count - 1)',
    'add_instr_to_varname': 'Append the instrument name to each variable name',
    'plot_file_availability': 'Plot the file-availability heatmap',
    'plot_ts_hires': 'Plot high-resolution time series per file',
    'plot_histogram_hires': 'Plot high-resolution histograms per file',
    'plot_ts_agg': 'Plot aggregated time series across files',
    'days': 'Convert only the most recent N days (0 = use the start/end date range)',
    'avoidduplicates': 'Skip files already present in the output folder',
}
# Placeholder text for free-text inputs (shown when the field is empty).
FIELD_PLACEHOLDERS = {
    'start_date': 'YYYY-MM-DD HH:MM',  # HH:MM is required, not optional
    'end_date': 'YYYY-MM-DD HH:MM',
    'filename_datetime_format': 'yyyymmddHH.CMM',
}
# Keys that are persisted to bico.settings (everything but the run-only options).
PERSISTED_KEYS = [key for key, _, _, _ in INSTRUMENT_FIELDS + RAWDATA_FIELDS + OUTPUT_FIELDS]


def _field_id(key: str) -> str:
    return f'field-{key}'


def _parse_dropped_path(text: str):
    """Parse pasted/dropped text into a filesystem Path, or None.

    Terminals deliver a dragged-in file or folder as pasted text: its path,
    often wrapped in quotes or given as a file:// URI. Returns None for empty or
    multi-line text, so ordinary pastes are left untouched.
    """
    candidate = (text or '').strip().strip('"').strip("'").strip()
    if not candidate or '\n' in candidate:
        return None
    if candidate.startswith('file://'):
        from urllib.parse import unquote, urlparse
        candidate = unquote(urlparse(candidate).path)
        # file:///C:/... → strip the leading slash before the drive letter
        if len(candidate) > 2 and candidate[0] == '/' and candidate[2] == ':':
            candidate = candidate[1:]
    return Path(candidate)


def _dropped_folder(text: str):
    """Resolve dropped text to a folder path string (a dropped file yields its
    parent folder), or None if the text is not an existing path."""
    path = _parse_dropped_path(text)
    if path is None:
        return None
    if path.is_dir():
        return str(path)
    if path.is_file():
        return str(path.parent)
    return None


HELP_MD = """\
# bico help

bico converts ETH eddy-covariance raw binary files to ASCII CSV for EddyPro.
Set up the run in the settings panel on the left. The console on the right shows
validation results and the live run log.

## Workflow
1. Set the options (Instruments, Raw data, Output, Run options).
2. Press **Validate** (`v`). It checks every field, shows the settings the run
   will use, and counts the matching files in the source folder.
3. Press **Run** (`r`). Run stays off until Validate passes, and editing any
   field switches it off again, so you always run exactly what you validated.
   The live plot (top-right) fills in automatically as files convert.

## Settings files
The TUI opens with the settings you last saved (`s`) to the source `bico.settings`.
Each run also drops a `bico.settings` snapshot into its output folder. Three
buttons manage settings files (none of them changes the source file until you
Save):
- **Save** (`s`): write the current form back to the source `bico.settings`.
- **Load…** (`l`): read a `bico.settings` you pick — e.g. a previous run's
  snapshot — into the form. (To *reuse* an earlier run's settings, Load its
  snapshot; dragging a file onto the TUI only fills folder fields, see below.)
- **Export…** (`e`): write the current form as a `bico.settings` into a folder
  you choose, e.g. to seed a headless run folder.

## Drag and drop folders
Instead of browsing, click the **Source folder** or **Output folder** field to
focus it, then **drag and drop a file or folder onto the TUI** — the field is
filled with the folder path (dropping a file uses the folder that contains it).
Each folder field has a **…** button to browse and a **✕** button to empty it.

## Progress
While a run is going, the bar shows files done / total. Below it, each file being
converted right now gets its own line with a per-file progress bar, a percentage,
and the current step (Reading, Converting, Saving, …) — so with several worker
processes you see every in-flight file at once. A file's line drops off when it
finishes, and its detailed log appears in the console at that point.

## Stopping a run
Press **Stop** to end a running conversion early. The file being converted
finishes (so its output is complete), then no further files are started and the
run winds down normally. Files already converted are kept.

## Live plot
Top-right, beside the progress bars, bico plots the **first 100 values of the
first three variables** (for a sonic that is U, V, W) as each file finishes
converting. The three are overlaid on a shared min/max y-axis, each in its own
colour, matching the variable names shown in the plot title (the legend). It
starts automatically on Run — nothing to pick — and redraws for every file in
completion order. Missing values (-9999) are skipped. Press **`p`** to show or
hide the plot pane.

## Copy from the log
Drag with the mouse to select text in the console, then press **Ctrl+C** to copy
it. Double-click selects a line.

## Keys
- `v`: validate the settings (turns on Run once everything is OK)
- `d`: detect the time range from the source files (fills Start/End date)
- `t`: test run, converting the first rows of the first file and writing nothing
- `r`: run the conversion
- `s`: save settings to the source `bico.settings`
- `l`: load settings from a `bico.settings` file you pick into the form
- `e`: export the current settings as a `bico.settings` into a folder you choose
  (e.g. a headless run folder); the source `bico.settings` is left unchanged
- `f`: show or hide the settings panel
- `p`: show or hide the live plot pane
- `ctrl+l`: clear the console
- `h`: this help
- `q`: quit

## Settings

**Instruments.** Site, logger header, and up to three instrument data blocks
(sonic and gas analyzers), in order.

**Raw data**
- *Source folder*: where binary files are read from (Browse… or type a path).
  Searched **recursively** — files in subfolders are found too, not only the
  folder you pick.
- *Start / End date*: `YYYY-MM-DD HH:MM`. Both ends are inclusive. Use
  **Detect dates from source files** (`d`) to fill these from the earliest and
  latest file in the source folder (parsed with the filename datetime format);
  this also resets *Recent days* to 0 so the range is used. Adjust afterwards.
- *Filename dt format*: the datetime pattern in the filenames, including the
  extension (e.g. `yyyymmddHH.CMM`). It also sets which files are searched, so
  there is no separate file-extension setting.
- *Min size*: files smaller than this many bytes are skipped.
- *File limit* and *Row limit*: `0` means no limit.
- *Random files*: `0` means no random selection.

**Output**
- *Output folder*: where converted files are written.
- *Folder prefix*: goes in front of the run output folder name.
- *Compression*: `gzip` writes `.csv.gz`, `None` writes `.csv`.
- *Processes*: number of parallel workers. `0` picks it automatically
  (cpu_count minus 1).
- *Instr in varname*: adds the instrument name to each variable.
- *Plots*: which figures to generate.

**Run options**
- *Recent days*: convert only the last N days. `0` uses the start/end range.
- *Avoid duplicates*: skip files already present in the output folder.

## Folder picker
Browse the tree, use **Up** for the parent folder, or type or paste a path into
the field and press Enter to jump there. **Select folder** confirms.

## How bico works

bico turns ETH eddy-covariance raw binary files into uncompressed ASCII CSV that
EddyPro and other tools can read.

**Data blocks.** Each instrument writes its measurements as a data block, a fixed
binary layout of variables. A sonic anemometer writes wind components and sonic
temperature. A gas analyzer writes CO₂/H₂O concentrations, diagnostics, and cell
temperature and pressure, among others. A logger *file* starts with a header.
Each *record* (one timestamp) then holds only the data blocks of the configured
instruments, one after another. The layout of every block is described by a spec
file (`bico/settings/data_blocks/*.dblock`), so supporting a new instrument means
adding a spec rather than changing code. The **Instruments** settings (header
plus Instrument 1 to 3) tell bico which blocks to expect and in what order.

## The run pipeline
1. *Find files.* Search the source folder, **including all subfolders**, for
   names that match the filename datetime format. The same format gives both the
   search pattern and each file's timestamp.
2. *Filter.* Keep files inside the start/end date range, above the minimum size,
   and within the file limit. Optionally take a random subset.
3. *Convert.* For each file, read the binary with the data-block specs and decode
   every record into rows of named variables. Files convert in parallel, one
   process per file, up to the number of workers set by *Processes*. A bad file
   is skipped instead of stopping the run.
4. *Write.* Save each file as ASCII CSV, either gzipped (`.csv.gz`) or plain
   (`.csv`), and optionally add the instrument name to each variable.
5. *Summarise.* Compute per-file and aggregated statistics, and render the
   availability heatmap, the high-resolution time series and histograms, and the
   aggregated time series when those plots are enabled.

**Output.** Each run makes a timestamped folder under the output folder, named
from the *Folder prefix* and the run id. It holds `raw_data_ascii/` with the
converted files, `plots/`, a `log/` with the full run log, and a snapshot of the
exact settings used. A run never changes the source `bico.settings`.

**Same engine everywhere.** The TUI (`bico -t`) and the headless CLI
(`bico -f <folder> -d <days> -a`, used for scheduled jobs) run the same
conversion engine, so the output is the same however you start a run.
"""

# Appended so the URLs stay in one place (bico.settings._version). Links are
# clickable in the help overlay (HelpScreen opens them in the browser).
HELP_MD += f"""
## Links
- [Source code (GitHub repo)]({info.__link_source_code__})
- [README]({info.__link_readme__})
- [Changelog]({info.__link_changelog__})
"""
