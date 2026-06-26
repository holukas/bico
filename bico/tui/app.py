"""Textual TUI for bico.

Left column: every setting from bico.settings plus the run-time options that the
CLI exposes (recent-days window, avoid-duplicates). Right column: a live Rich
console showing the run log. The same conversion engine (``BicoEngine``) used by
the headless CLI does the work, driven here from a worker thread so the UI stays
responsive.
"""
import datetime as dt
import logging
import threading
from pathlib import Path

from rich.style import Style
from rich.text import Text
from textual import events, on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.strip import Strip
from textual.validation import Integer, Regex
from textual.widgets import (Button, DirectoryTree, Footer, Header, Input, Label,
                             Markdown, ProgressBar, RichLog, Select, Static, Switch)

import bico
from bico.bico import BicoEngine
from bico.ops import bin as bbin, file as bfile, setup as ops_setup
from bico.settings import _version as info
from bico.tui.log_handler import make_tui_handler

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


class PathDropInput(Input):
    """A path field that fills itself from a dragged-in file or folder.

    Most terminals paste a dropped file/folder as its path; when the pasted text
    is a real path this sets the field to the folder (a dropped file yields its
    parent folder), so source/output folders can be set by dropping instead of
    browsing. Any other paste behaves like a normal Input paste.

    A terminal routes a dropped path to the *focused* widget, so click (focus) the
    field before dropping onto it.
    """

    def _on_paste(self, event: events.Paste) -> None:
        folder = _dropped_folder(event.text)
        if folder is not None:
            self.value = folder
            self.cursor_position = len(folder)
            # Textual dispatches `_on_paste` for every class in the MRO; only
            # prevent_default() stops Input's own handler from then inserting the
            # raw path. stop() keeps it from bubbling to the app paste handler.
            event.prevent_default()
            event.stop()
        # Otherwise do nothing: Textual still calls Input._on_paste (normal paste).


class SelectableRichLog(RichLog):
    """A ``RichLog`` whose text can be selected with the mouse and copied.

    Plain ``RichLog`` (Textual 8.2) renders pre-styled strips and never attaches
    the per-cell content offsets the screen uses to map a mouse drag to text, nor
    does it draw the selection or expose the selected text — so dragging over it
    selects nothing. This subclass adds the three missing pieces: it stamps each
    rendered line with its content offset (so a drag forms a selection), paints
    the selection highlight, and returns the selected text for copy (Ctrl+C).
    """

    def _selection_style(self) -> Style:
        """Selection highlight: only a background colour, so the text keeps its own
        colour and stays readable. (The theme's ``screen--selection`` foreground is
        ``transparent`` = "keep existing", which, applied as a base style, would turn
        plain text invisible — so we take just its background.)"""
        comp = self.screen.get_component_rich_style('screen--selection')
        return Style(bgcolor=comp.bgcolor) if comp.bgcolor else Style(reverse=True)

    @staticmethod
    def _highlight_span(line: Strip, start: int, end: int, style: Style) -> Strip:
        """Return `line` with the background of cells [start, end) set to `style`."""
        start = max(0, start)
        end = min(end, line.cell_length)
        if end <= start:
            return line
        before, selected, after = line.divide([start, end, line.cell_length])
        return Strip.join([before, selected.apply_style(style), after])

    def render_line(self, y: int) -> Strip:
        scroll_x, scroll_y = self.scroll_offset
        content_y = scroll_y + y
        selection = self.text_selection
        if selection is None:
            # No selection: keep the base (cached) rendering, but stamp offsets so
            # a future drag can resolve the cell under the mouse to content text.
            return super().render_line(y).apply_offsets(scroll_x, content_y)
        width = self.scrollable_content_region.width
        if content_y >= len(self.lines):
            return Strip.blank(width, self.rich_style).apply_offsets(scroll_x, content_y)
        line = self.lines[content_y]
        span = selection.get_span(content_y)
        if span is not None:
            start, end = span
            if end == -1:
                end = line.cell_length
            line = self._highlight_span(line, start, end, self._selection_style())
        line = line.crop_extend(scroll_x, scroll_x + width, self.rich_style)
        line = line.apply_style(self.rich_style)
        return line.apply_offsets(scroll_x, content_y)

    def get_selection(self, selection):
        text = '\n'.join(strip.text for strip in self.lines)
        return selection.extract(text), '\n'

    def selection_updated(self, selection) -> None:
        self.refresh()


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

## Settings files
The TUI opens with the settings you last saved (`s`) to `bico.settings`. Each run
also drops a `bico.settings` snapshot into its output folder. To reuse a previous
run's settings, **drag and drop its `bico.settings` file anywhere onto the TUI**
and the form is filled from it.

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

## Copy from the log
Drag with the mouse to select text in the console, then press **Ctrl+C** to copy
it. Double-click selects a line.

## Keys
- `v`: validate the settings (turns on Run once everything is OK)
- `d`: detect the time range from the source files (fills Start/End date)
- `t`: test run, converting the first rows of the first file and writing nothing
- `r`: run the conversion
- `s`: save settings to the source `bico.settings`
- `e`: export the current settings as a `bico.settings` into a folder you choose
  (e.g. a headless run folder); the source `bico.settings` is left unchanged
- `f`: show or hide the settings panel
- `ctrl+l`: clear the console
- `h`: this help
- `q`: quit

## Settings

**Instruments.** Site, logger header, and up to three instrument data blocks
(sonic and gas analyzers), in order.

**Raw data**
- *Source folder*: where binary files are read from (Browse… or type a path).
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
1. *Find files.* Search the source folder for names that match the filename
   datetime format. The same format gives both the search pattern and each
   file's timestamp.
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


class HelpScreen(ModalScreen):
    """Scrollable help overlay explaining the TUI."""

    BINDINGS = [('escape', 'close', 'Close'), ('q', 'close', 'Close'), ('h', 'close', 'Close')]

    def compose(self) -> ComposeResult:
        with Vertical(id='help'):
            yield Static('bico — help   (esc to close)', classes='help-title')
            with VerticalScroll(id='help-body'):
                yield Markdown(HELP_MD)
            with Horizontal(id='help-actions'):
                yield Button('Close', id='help-close', variant='primary')

    @on(Button.Pressed, '#help-close')
    def _close(self) -> None:
        self.dismiss()

    def action_close(self) -> None:
        self.dismiss()


class _PickerScreen(ModalScreen[str]):
    """Shared modal browser: an editable path field over a ``DirectoryTree``.

    Subclasses supply the title/labels (``compose``) and decide what counts as a
    valid pick (the tree-selection, path-submit and OK handlers). Dismisses with
    the chosen path string, or None if cancelled.

    Only the handlers common to every picker live here. Textual dispatches every
    ``@on`` handler found across the MRO (deduped by function, not by name), so an
    override in a subclass would *also* run the base version — the differing
    handlers must therefore stay in the subclasses, not here.
    """

    BINDINGS = [('escape', 'cancel', 'Cancel')]

    def __init__(self, start_path: str):
        super().__init__()
        path = Path(start_path) if start_path else Path.home()
        # Fall back gracefully if the configured path no longer exists.
        while not path.is_dir() and path != path.parent:
            path = path.parent
        if not path.is_dir():
            path = Path.home()
        self._root = path
        self._selected = str(path)

    def _set_selected(self, path) -> None:
        """Update the selected path and reflect it in the editable path field."""
        self._selected = str(path)
        self.query_one('#picker-path', Input).value = self._selected

    def _goto(self, path) -> None:
        """Re-root the tree at path (if it is a directory) and select it."""
        path = Path(path)
        if path.is_dir():
            self.query_one('#picker-tree', DirectoryTree).path = str(path)
            self._set_selected(path)
            return True
        return False

    @on(Button.Pressed, '#picker-up')
    def _on_up(self) -> None:
        tree = self.query_one('#picker-tree', DirectoryTree)
        self._goto(Path(tree.path).parent)

    @on(Button.Pressed, '#picker-cancel')
    def _on_cancel(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class DirectoryPickerScreen(_PickerScreen):
    """Modal folder browser. Dismisses with the chosen folder, or None if cancelled."""

    def compose(self) -> ComposeResult:
        with Vertical(id='picker'):
            yield Static('Select a folder (type or paste a path, then Enter)',
                         classes='picker-title')
            yield Input(self._selected, id='picker-path',
                        placeholder='Paste a folder path and press Enter')
            yield DirectoryTree(str(self._root), id='picker-tree')
            with Horizontal(id='picker-actions'):
                yield Button('Up', id='picker-up')
                yield Button('Select folder', id='picker-ok', variant='success')
                yield Button('Cancel', id='picker-cancel')

    @on(DirectoryTree.DirectorySelected)
    def _on_dir_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        self._set_selected(event.path)

    @on(Input.Submitted, '#picker-path')
    def _on_path_submitted(self, event: Input.Submitted) -> None:
        # Jump the tree to a typed/pasted path.
        if not self._goto(event.value.strip()):
            self.notify(f'Not a folder: {event.value}', severity='warning')

    @on(Button.Pressed, '#picker-ok')
    def _on_ok(self) -> None:
        # The editable path field is the source of truth.
        self.dismiss(self.query_one('#picker-path', Input).value.strip())


class FilePickerScreen(_PickerScreen):
    """Modal file browser. Dismisses with the chosen file path, or None if cancelled.

    Clicking a folder expands it; clicking a file selects it; OK is gated on the
    path field naming an existing file. When the start path is a file, the tree
    opens at its folder with that file pre-selected.
    """

    def __init__(self, start_path: str, title: str = 'Select a file'):
        self._title = title
        start = Path(start_path) if start_path else None
        self._initial_file = str(start) if start and start.is_file() else ''
        # Root the tree at the file's folder when a file path is given.
        super().__init__(str(start.parent) if self._initial_file else start_path)
        if self._initial_file:
            self._selected = self._initial_file

    def compose(self) -> ComposeResult:
        with Vertical(id='picker'):
            yield Static(f'{self._title} (type or paste a path, then Enter)',
                         classes='picker-title')
            yield Input(self._selected, id='picker-path',
                        placeholder='Paste a file path and press Enter')
            yield DirectoryTree(str(self._root), id='picker-tree')
            with Horizontal(id='picker-actions'):
                yield Button('Up', id='picker-up')
                yield Button('Select file', id='picker-ok', variant='success')
                yield Button('Cancel', id='picker-cancel')

    @on(DirectoryTree.FileSelected)
    def _on_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        self._set_selected(event.path)

    @on(Input.Submitted, '#picker-path')
    def _on_path_submitted(self, event: Input.Submitted) -> None:
        # A typed file path selects it (opening the tree at its folder); a folder
        # path re-roots the tree there.
        value = event.value.strip()
        path = Path(value)
        if path.is_file():
            self._goto(path.parent)
            self._set_selected(path)
        elif not self._goto(value):
            self.notify(f'Not a file or folder: {value}', severity='warning')

    @on(Button.Pressed, '#picker-ok')
    def _on_ok(self) -> None:
        value = self.query_one('#picker-path', Input).value.strip()
        if not Path(value).is_file():
            self.notify(f'Not a file: {value}', severity='warning')
            return
        self.dismiss(value)


class BicoApp(App):
    """bico — binary converter, as a terminal UI."""

    CSS_PATH = 'app.tcss'
    TITLE = 'bico'
    SUB_TITLE = f'binary converter  ·  v{info.__version__}'

    BINDINGS = [
        ('r', 'run_conversion', 'Run'),
        ('t', 'test_run', 'Test run'),
        ('v', 'validate', 'Validate'),
        ('d', 'detect_dates', 'Detect dates'),
        ('s', 'save_settings', 'Save'),
        ('l', 'load_settings', 'Load'),
        ('e', 'export_settings', 'Export'),
        ('f', 'toggle_settings', 'Show/hide settings'),
        ('ctrl+l', 'clear_console', 'Clear log'),
        # Override the App's default ctrl+c (which only shows a "press q to quit"
        # hint for non-Input widgets) so it copies the console selection instead.
        Binding('ctrl+c', 'copy_selection', 'Copy', show=False),
        ('h', 'help', 'Help'),
        ('q', 'quit', 'Quit'),
    ]

    def __init__(self):
        super().__init__()
        # Base settings read from file; non-form keys (e.g. dir_server_*) are
        # preserved here and merged back in when collecting form values.
        # On startup this is the last-saved bico.settings, so the TUI always
        # opens with the settings last persisted via Save.
        self._base_settings = ops_setup.read_settings_file_to_dict(
            dir_settings=SETTINGS_DIR, file=bfile.SETTINGS_FILENAME, reset_paths=False)
        self._busy = False
        # Run is only allowed after Validate confirms the settings are OK; any
        # change to a setting clears this so the user must re-validate.
        self._validated = False
        # Set from the UI when the user presses Stop; the engine polls it between
        # files and winds the run down (see _run_engine / action_stop_conversion).
        self._stop_event = threading.Event()
        # Live per-file progress: task index -> (total, filename, step, fraction).
        # One line is shown per entry, so parallel files each get their own line.
        self._file_status: dict[int, tuple] = {}

    # -- layout --------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id='body'):
            with Vertical(id='settings'):
                # Single wide column so paths stay as readable as possible.
                with VerticalScroll(id='settings-fields'):
                    yield from self._section('Instruments', INSTRUMENT_FIELDS)
                    yield from self._section('Raw data', RAWDATA_FIELDS)
                    detect = Button('Detect dates from source files', id='btn-detect',
                                    classes='detect-row-btn')
                    detect.tooltip = ('Scan the source folder, parse every file date with the '
                                      'filename datetime format, and set Start/End date to the '
                                      'earliest/latest file. You can adjust them afterwards.')
                    yield detect
                    yield from self._section('Output', OUTPUT_FIELDS)
                    yield from self._section('Run options', RUN_FIELDS)
                with Horizontal(id='actions'):
                    yield Button('Save', id='btn-save', variant='primary')
                    load = Button('Load…', id='btn-load')
                    load.tooltip = ('Load a bico.settings from a folder you choose into the '
                                    'form. The source bico.settings is not changed until you Save.')
                    yield load
                    export = Button('Export…', id='btn-export')
                    export.tooltip = ('Write a bico.settings with the current form values into a '
                                      'folder you choose — e.g. a headless run folder. The source '
                                      'bico.settings is not changed.')
                    yield export
                    yield Button('Validate', id='btn-validate')
                    yield Button('Test', id='btn-test')
                    # Run stays disabled until Validate confirms the settings are OK.
                    yield Button('Run', id='btn-run', variant='success', disabled=True)
                    # Stop is enabled only while a conversion is running.
                    yield Button('Stop', id='btn-stop', variant='error', disabled=True)
            with Vertical(id='console-pane'):
                yield Static('Console', classes='pane-title')
                progress = ProgressBar(id='progress', show_eta=True)
                progress.display = False  # shown only while a conversion runs
                yield progress
                status = Static('', id='run-status')
                status.display = False  # shows the current file / step / % live
                yield status
                yield SelectableRichLog(id='console', highlight=False, markup=False, wrap=True)
        yield Footer()

    def _section(self, title: str, fields):
        yield Static(title, classes='section')
        for key, label, kind, options in fields:
            hint = FIELD_HINTS.get(key)
            # One row per field: label on the left, control on the right.
            with Horizontal(classes=f'field field-{kind}'):
                lbl = Label(label, classes='field-label')
                lbl.tooltip = hint
                yield lbl
                if kind == 'switch':
                    control = Switch(id=_field_id(key))
                elif kind == 'select':
                    control = Select([(o, o) for o in options], id=_field_id(key),
                                     allow_blank=False)
                elif kind == 'path':
                    control = PathDropInput(id=_field_id(key), type='text')
                else:
                    validators = None
                    if key in ('start_date', 'end_date'):
                        validators = [Regex(DATE_PATTERN,
                                            failure_description='Use 2025-12-31 23:59')]
                    elif kind == 'int':
                        # Validate (instead of blocking input) so a disallowed
                        # character turns the field red rather than being silently
                        # dropped.
                        validators = [Integer(failure_description='Whole number only')]
                    control = Input(id=_field_id(key), type='text',
                                    placeholder=FIELD_PLACEHOLDERS.get(key, ''),
                                    validators=validators)
                control.tooltip = hint
                yield control
                if kind == 'path':
                    browse = Button('…', id=f'browse-{key}', classes='browse-btn')
                    browse.tooltip = 'Browse for a folder'
                    yield browse
                    clear = Button('✕', id=f'clear-{key}', classes='clear-btn')
                    clear.tooltip = 'Clear this field'
                    yield clear

    # -- wiring --------------------------------------------------------------

    def on_mount(self) -> None:
        self._load_settings_into_form(self._base_settings)
        console = self.query_one('#console', RichLog)
        console.write(Text('Ready. Adjust settings and press Run (r).', style='dim'))

    def _load_settings_into_form(self, settings: dict) -> None:
        for key, kind in FIELD_KIND.items():
            value = settings.get(key, '')
            # Recent-days defaults to 0 so a run uses the start/end date range
            # unless the user explicitly sets a positive number of days.
            if key == 'days' and not value:
                value = '0'
            widget = self.query_one(f'#{_field_id(key)}')
            if kind == 'switch':
                widget.value = str(value) == '1'
            elif kind == 'select':
                widget.value = value if value else Select.BLANK
            else:
                widget.value = '' if value is None else str(value)

    def _load_settings_from_path(self, path: Path) -> None:
        """Load a bico.settings file into the form (e.g. via the Load… button)."""
        try:
            settings = ops_setup.read_settings_file_to_dict(
                dir_settings=path.parent, file=path.name, reset_paths=False)
        except Exception as exc:
            self.notify(f'Could not read {path.name}: {exc}', severity='error')
            return
        # Replace the base settings (preserving non-form keys from the loaded file)
        # and refresh the form. Loading invalidates any prior validation.
        self._base_settings = settings
        self._load_settings_into_form(settings)
        self._set_validated(False)
        console = self.query_one('#console', RichLog)
        console.write(Text(f'Loaded settings from {path}', style='bold cyan'))
        self.notify(f'Loaded settings from {path.name}', severity='information')

    def _collect_form(self) -> dict:
        """Read widget values, merged onto the base (file) settings."""
        settings = dict(self._base_settings)
        for key, kind in FIELD_KIND.items():
            if key in ('days', 'avoidduplicates'):
                continue  # run-only options, handled separately
            widget = self.query_one(f'#{_field_id(key)}')
            if kind == 'switch':
                settings[key] = '1' if widget.value else '0'
            elif kind == 'select':
                settings[key] = '' if widget.value is Select.BLANK else str(widget.value)
            else:
                settings[key] = str(widget.value)
        return settings

    def _run_options(self):
        days_raw = self.query_one(f'#{_field_id("days")}', Input).value.strip()
        days = int(days_raw) if days_raw and int(days_raw) > 0 else None
        avoid = self.query_one(f'#{_field_id("avoidduplicates")}', Switch).value
        return days, avoid

    # -- actions -------------------------------------------------------------

    def action_clear_console(self) -> None:
        self.query_one('#console', RichLog).clear()

    def action_copy_selection(self) -> None:
        """Copy the current text selection (e.g. from the console) to the clipboard."""
        text = self.screen.get_selected_text()
        if not text:
            self.notify('Select text first — drag across the console, then Ctrl+C.',
                        severity='information')
            return
        self.copy_to_clipboard(text)
        n = len(text)
        self.notify(f'Copied {n} character{"" if n == 1 else "s"} to the clipboard.')

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_toggle_settings(self) -> None:
        """Hide/show the left settings pane; the console fills the freed width."""
        settings = self.query_one('#settings')
        settings.display = not settings.display

    def action_save_settings(self) -> None:
        settings = self._collect_form()
        settings['dir_settings'] = SETTINGS_DIR
        bfile.save_settings_to_file(settings)
        # Keep the in-memory base in step so a later collect/save round-trips cleanly.
        self._base_settings = dict(settings)
        self.notify(f'Settings saved to {bfile.SETTINGS_FILENAME}', severity='information')

    @on(Button.Pressed, '#btn-save')
    def _on_save(self) -> None:
        self.action_save_settings()

    def action_load_settings(self) -> None:
        """Load a settings file the user picks into the form.

        The counterpart to Export…: choose a settings file (any name read by the
        same parser) and it is read into the form. The source bico.settings is not
        touched until Save.
        """
        if self._busy:
            self.notify('Busy — finish the current run first.', severity='warning')
            return

        def apply(path: str | None) -> None:
            if not path:
                return
            settings_file = Path(path)
            if not settings_file.is_file():
                self.notify(f'Not a file: {path}', severity='error')
                return
            self._load_settings_from_path(settings_file)

        # Start the picker at the source folder's bico.settings, a likely target.
        settings = self._collect_form()
        folder = settings.get('dir_source') or settings.get('dir_out') or ''
        start = str(Path(folder) / bfile.SETTINGS_FILENAME) if folder else ''
        self.push_screen(FilePickerScreen(start, title='Select a settings file'), apply)

    @on(Button.Pressed, '#btn-load')
    def _on_load(self) -> None:
        self.action_load_settings()

    def action_export_settings(self) -> None:
        """Export the current form settings as a bico.settings into a chosen folder.

        Lets the user edit settings on screen and drop them into a headless run
        folder. The source bico.settings (loaded on startup) is left untouched.
        """
        if self._busy:
            self.notify('Busy — finish the current run first.', severity='warning')
            return
        settings = self._collect_form()

        def apply(path: str | None) -> None:
            if not path:
                return
            dest = Path(path)
            if not dest.is_dir():
                self.notify(f'Not a folder: {path}', severity='error')
                return
            # Prefer an existing bico.settings in the target as the template (keeps
            # any local comments); otherwise use the canonical source file.
            template = dest / bfile.SETTINGS_FILENAME
            if not template.is_file():
                template = SETTINGS_DIR / bfile.SETTINGS_FILENAME
            try:
                out = bfile.export_settings_to_folder(settings, dest, template)
            except Exception as exc:
                self.notify(f'Export failed: {exc}', severity='error')
                return
            self.notify(f'Settings exported to {out}', severity='information')

        # Start the picker at the output folder, the most likely export target.
        start = settings.get('dir_out') or settings.get('dir_source') or ''
        self.push_screen(DirectoryPickerScreen(start), apply)

    @on(Button.Pressed, '#btn-export')
    def _on_export(self) -> None:
        self.action_export_settings()

    @on(Button.Pressed, '#btn-validate')
    def _on_validate(self) -> None:
        self.action_validate()

    @on(Button.Pressed, '#btn-detect')
    def _on_detect(self) -> None:
        self.action_detect_dates()

    @on(Button.Pressed, '#btn-test')
    def _on_test(self) -> None:
        self.action_test_run()

    @on(Button.Pressed, '#btn-run')
    def _on_run(self) -> None:
        self.action_run_conversion()

    @on(Button.Pressed, '#btn-stop')
    def _on_stop(self) -> None:
        self.action_stop_conversion()

    @on(Input.Changed)
    @on(Select.Changed)
    @on(Switch.Changed)
    def _on_setting_changed(self, event) -> None:
        # Any settings edit invalidates a prior validation, so Run is disabled
        # again until the user re-validates. (Ignore the folder-picker's input.)
        if getattr(event.control, 'id', '') == 'picker-path':
            return
        self._set_validated(False)

    def _set_validated(self, ok: bool) -> None:
        self._validated = ok
        self._refresh_run_enabled()

    def _refresh_run_enabled(self) -> None:
        self.query_one('#btn-run', Button).disabled = self._busy or not self._validated

    @on(Button.Pressed, '#browse-dir_source')
    def _browse_source(self) -> None:
        self._open_picker('dir_source')

    @on(Button.Pressed, '#browse-dir_out')
    def _browse_out(self) -> None:
        self._open_picker('dir_out')

    @on(Button.Pressed, '.clear-btn')
    def _on_clear_field(self, event: Button.Pressed) -> None:
        # Empty the associated path field (and re-focus it for typing/dropping).
        key = event.button.id.removeprefix('clear-')
        field = self.query_one(f'#{_field_id(key)}', Input)
        field.value = ''
        field.focus()

    def _open_picker(self, key: str) -> None:
        field = self.query_one(f'#{_field_id(key)}', Input)

        def apply(path: str | None) -> None:
            if path:
                field.value = path

        self.push_screen(DirectoryPickerScreen(field.value), apply)

    def _effective_settings(self):
        """Build exactly what a run would use: form values + run dirs + the
        effective date range. Returns (settings, days, avoid)."""
        settings = self._collect_form()
        self._add_run_dirs(settings)
        days, avoid = self._run_options()
        if days:
            self._apply_recent_days(settings, days)
        return settings, days, avoid

    @staticmethod
    def _quiet_logger():
        """A logger that swallows output (for counting/test conversions)."""
        lg = logging.getLogger('bico_tui_quiet')
        lg.handlers.clear()
        lg.addHandler(logging.NullHandler())
        lg.setLevel(logging.CRITICAL)
        lg.propagate = False
        return lg

    def action_validate(self) -> None:
        """Show the settings a run would use, validate the fields, and count
        the matching files. Enables the Run button only if there are no errors."""
        settings, days, avoid = self._effective_settings()
        problems = self._validate(settings, days)
        self._write_preview(settings, days, avoid, problems)
        ok = not any(level == 'error' for level, _ in problems)
        self._set_validated(ok)
        if ok:
            self._count_files(settings)

    @work(thread=True, group='bico-count')
    def _count_files(self, settings: dict) -> None:
        """Count files matching the settings in the source folder (off the UI thread)."""
        console = self.query_one('#console', RichLog)
        write = lambda renderable: self.call_from_thread(console.write, renderable)
        write(Text('  Checking source folder…', style='dim'))
        try:
            fmt = settings['filename_datetime_format']
            file_glob = bfile.search_glob_from_datetime_format(fmt)
            qlog = self._quiet_logger()
            matched = bfile.SearchAll.search_all(dir=settings['dir_source'],
                                                 file_id=file_glob, logger=qlog)
            # How many pass the glob + time range + min size (ignoring file limit / random).
            probe = dict(settings)
            probe['filename_datetime_parsing_string'] = bfile.datetime_parsing_string(fmt)
            probe['file_limit'] = '0'
            probe['select_random_files'] = '0'
            valid = bfile.SearchAll(probe, qlog).keep_valid_files()
            write(Text(f'  Folder: {len(matched)} file(s) match "{file_glob}", '
                       f'{len(valid)} within the time range and ≥ min size.',
                       style='bold green' if valid else 'yellow'))
            limit = int(settings.get('file_limit') or 0)
            if limit and len(valid) > limit:
                write(Text(f'  File limit {limit} will cap this run to {limit} file(s).',
                           style='yellow'))
        except Exception as exc:
            write(Text(f'  (!) Folder check failed: {exc}', style='yellow'))

    def action_detect_dates(self) -> None:
        """Fill Start/End date from the earliest/latest file in the source folder.

        Uses the filename datetime format (the parsing pattern) to read each
        file's date, so only the source folder and that format are required."""
        if self._busy:
            self.notify('A conversion is already running.', severity='warning')
            return
        src = self.query_one(f'#{_field_id("dir_source")}', Input).value.strip()
        fmt = self.query_one(f'#{_field_id("filename_datetime_format")}', Input).value.strip()
        console = self.query_one('#console', RichLog)
        issues = []
        if not src:
            issues.append('Source folder is empty.')
        elif not Path(src).is_dir():
            issues.append(f'Source folder does not exist: {src}')
        if not fmt:
            issues.append('Filename datetime format is empty.')
        if issues:
            console.write(Text('✗ Cannot detect dates:', style='bold red'))
            for m in issues:
                console.write(Text(f'    • {m}', style='red'))
            self.notify('Fix the errors before detecting dates.', severity='warning')
            return
        self._detect_dates(src, fmt)

    @work(thread=True, exclusive=True, group='bico-detect')
    def _detect_dates(self, src: str, fmt: str) -> None:
        """Scan the source folder and set the date range to the file date span."""
        console = self.query_one('#console', RichLog)
        write = lambda renderable: self.call_from_thread(console.write, renderable)
        write(Text('─' * 40, style='dim'))
        write(Text('Detecting time range from source files…', style='bold cyan'))
        try:
            file_glob = bfile.search_glob_from_datetime_format(fmt)
            parsing = bfile.datetime_parsing_string(fmt)
            qlog = self._quiet_logger()
            matched = bfile.SearchAll.search_all(dir=src, file_id=file_glob, logger=qlog)
            if not matched:
                write(Text(f'  No files match "{file_glob}" in {src}.', style='yellow'))
                self.call_from_thread(self.notify, 'No matching files found.', severity='warning')
                return
            dates = []
            unparsed = 0
            for name in matched:
                try:
                    dates.append(dt.datetime.strptime(name, parsing))
                except ValueError:
                    unparsed += 1  # matched the glob but not the datetime format
            if not dates:
                write(Text(f'  None of the {len(matched)} matched file(s) could be parsed with "{fmt}".',
                           style='yellow'))
                self.call_from_thread(self.notify, 'No file dates could be parsed.', severity='warning')
                return
            start_s = min(dates).strftime('%Y-%m-%d %H:%M')
            end_s = max(dates).strftime('%Y-%m-%d %H:%M')
            self.call_from_thread(self._apply_detected_range, start_s, end_s)
            note = f' ({unparsed} unparseable, skipped)' if unparsed else ''
            write(Text(f'  Parsed {len(dates)} file date(s){note}.', style='dim'))
            write(Text(f'✓ Time range set to {start_s} → {end_s}. Adjust the dates if needed.',
                       style='bold green'))
        except Exception as exc:
            write(Text(f'(!) Date detection failed: {exc}', style='yellow'))

    def _apply_detected_range(self, start_s: str, end_s: str) -> None:
        """Write the detected range into the form (on the UI thread)."""
        self.query_one(f'#{_field_id("start_date")}', Input).value = start_s
        self.query_one(f'#{_field_id("end_date")}', Input).value = end_s
        # Recent-days overrides the explicit range, so reset it to 0 to make the
        # detected range take effect; the user can still change any of these.
        self.query_one(f'#{_field_id("days")}', Input).value = '0'

    def _validate(self, settings: dict, days):
        """Return a list of (level, message); level is 'error' or 'warning'."""
        problems = []
        err = lambda m: problems.append(('error', m))
        warn = lambda m: problems.append(('warning', m))

        if not settings.get('site'):
            err('No site selected.')
        if not settings.get('header'):
            err('No header selected.')
        instrs = [settings.get(f'instrument_{i}') for i in (1, 2, 3)]
        if all(i in ('', '-None-', None) for i in instrs):
            err('No instrument selected (all set to -None-).')

        src = str(settings.get('dir_source') or '')
        if not src:
            err('Source folder is empty.')
        elif not Path(src).is_dir():
            err(f'Source folder does not exist: {src}')

        out = str(settings.get('dir_out') or '')
        if not out:
            err('Output folder is empty — choose where converted files go.')
        elif not Path(out).is_dir():
            warn(f'Output folder does not exist yet (will be created): {out}')

        if not days:  # date range is only used when not converting recent days
            parsed = {}
            for key in ('start_date', 'end_date'):
                try:
                    parsed[key] = dt.datetime.strptime(settings.get(key, ''), '%Y-%m-%d %H:%M')
                except ValueError:
                    err(f'{key} is not in YYYY-MM-DD hh:mm format: {settings.get(key)!r}')
            if len(parsed) == 2 and parsed['start_date'] > parsed['end_date']:
                err('Start date is after end date.')

        if not settings.get('filename_datetime_format'):
            err('Filename datetime format is empty.')

        numeric = [('file_size_min', 'Min file size'), ('file_limit', 'File limit'),
                   ('row_limit', 'Row limit'), ('select_random_files', 'Random files'),
                   ('num_processes', 'Processes')]
        for key, label in numeric:
            value = str(settings.get(key, '')).strip()
            if value == '':
                err(f'{label} is empty.')
            else:
                try:
                    if int(value) < 0:
                        err(f'{label} must be 0 or greater.')
                except ValueError:
                    err(f'{label} must be a whole number (got {value!r}).')

        days_raw = self.query_one(f'#{_field_id("days")}', Input).value.strip()
        if days_raw == '':
            err('Recent days is empty (use 0 for the start/end date range).')
        else:
            try:
                if int(days_raw) < 0:
                    err('Recent days must be 0 or greater.')
            except ValueError:
                err(f'Recent days must be a whole number (got {days_raw!r}).')

        return problems

    def _write_preview(self, settings: dict, days, avoid: bool, problems) -> None:
        log = self.query_one('#console', RichLog)
        log.write(Text('─' * 40, style='dim'))
        log.write(Text('Preview — settings this run will use', style='bold cyan'))

        def row(label, value, note=None):
            line = Text()
            line.append(f'  {label:20}', style='dim')
            line.append('' if value in (None, '') else str(value))
            if note:
                line.append(f'   — {note}', style='dim italic')
            log.write(line)

        instrs = ', '.join(i for i in (settings.get('instrument_1'), settings.get('instrument_2'),
                                       settings.get('instrument_3')) if i and i != '-None-')
        if days:
            time_range = f"recent {days} day(s): {settings['start_date']} → {settings['end_date']}"
            time_note = 'computed from recent days; both ends inclusive'
        else:
            time_range = f"{settings.get('start_date')} → {settings.get('end_date')}"
            time_note = 'both ends inclusive'
        plots = [name for name, key in (('availability', 'plot_file_availability'),
                                        ('hi-res series', 'plot_ts_hires'),
                                        ('hi-res histograms', 'plot_histogram_hires'),
                                        ('agg series', 'plot_ts_agg')) if settings.get(key) == '1']

        row('Site', settings.get('site'), 'EC site code')
        row('Header', settings.get('header'), 'logger header type')
        row('Instruments', instrs or '(none)', 'data blocks, in order')
        row('Source folder', settings.get('dir_source') or '(not set)', 'raw binary files are read from here')
        row('Output folder', settings.get('dir_out') or '(not set)', 'converted files are written here')
        row('Time range', time_range, time_note)
        row('Filename dt format', settings.get('filename_datetime_format'),
            'incl. extension; also selects which files are searched')
        row('Min size (bytes)', settings.get('file_size_min'), 'smaller files are skipped')
        row('File limit', settings.get('file_limit'), '0 = no limit')
        row('Row limit', settings.get('row_limit'), '0 = no limit (all rows per file)')
        row('Random files', settings.get('select_random_files'), '0 = no random selection')
        row('Output prefix', settings.get('output_folder_name_prefix'), 'prefixes the run output folder name')
        row('Compression', settings.get('file_compression'), 'gzip → .csv.gz, None → .csv')
        row('Processes', settings.get('num_processes'), '0 = auto (cpu_count − 1)')
        row('Instr in varname', 'yes' if settings.get('add_instr_to_varname') == '1' else 'no',
            'append instrument name to each variable')
        row('Plots', ', '.join(plots) or '(none)', 'figures generated per run')
        row('Avoid duplicates', 'yes' if avoid else 'no', 'skip files already in the output folder')

        errors = [m for level, m in problems if level == 'error']
        warnings = [m for level, m in problems if level == 'warning']
        if not problems:
            log.write(Text('✓ All fields look OK — Run is now enabled.', style='bold green'))
        if errors:
            log.write(Text(f'✗ {len(errors)} problem(s) to fix before running:', style='bold red'))
            for m in errors:
                log.write(Text(f'    • {m}', style='red'))
        if warnings:
            log.write(Text(f'! {len(warnings)} warning(s):', style='yellow'))
            for m in warnings:
                log.write(Text(f'    • {m}', style='yellow'))

    def action_test_run(self) -> None:
        """Dry-run: convert the first rows of the first matching file, no output written."""
        if self._busy:
            self.notify('A conversion is already running.', severity='warning')
            return
        settings, _, _ = self._effective_settings()
        # A test run only needs to find and convert one file: it writes nothing
        # and ignores the date range, so only the essentials are required here.
        issues = []
        src = str(settings.get('dir_source') or '')
        if not src:
            issues.append('Source folder is empty.')
        elif not Path(src).is_dir():
            issues.append(f'Source folder does not exist: {src}')
        if all(settings.get(f'instrument_{i}') in ('', '-None-', None) for i in (1, 2, 3)):
            issues.append('No instrument selected (all set to -None-).')
        if not settings.get('filename_datetime_format'):
            issues.append('Filename datetime format is empty.')
        if issues:
            console = self.query_one('#console', RichLog)
            console.write(Text('✗ Cannot test run:', style='bold red'))
            for m in issues:
                console.write(Text(f'    • {m}', style='red'))
            self.notify('Fix the errors before a test run.', severity='warning')
            return
        self._begin_busy('test run…')
        self._test_run(settings)

    @work(thread=True, exclusive=True, group='bico-run')
    def _test_run(self, settings: dict) -> None:
        console = self.query_one('#console', RichLog)
        write = lambda renderable: self.call_from_thread(console.write, renderable)
        try:
            write(Text('─' * 40, style='dim'))
            write(Text(f'Test run — converting the first {TEST_RUN_ROWS} rows of the first file',
                       style='bold cyan'))
            fmt = settings['filename_datetime_format']
            file_glob = bfile.search_glob_from_datetime_format(fmt)
            qlog = self._quiet_logger()
            matched = bfile.SearchAll.search_all(dir=settings['dir_source'],
                                                 file_id=file_glob, logger=qlog)
            if not matched:
                write(Text(f'(!) No files match "{file_glob}" in {settings["dir_source"]}.',
                           style='bold red'))
                return
            name = sorted(matched)[0]
            path = matched[name]
            write(Text(f'File: {name}'))

            dblocks_seq = [settings.get(f'instrument_{i}') for i in (1, 2, 3)]
            dblocks_props = bfile.load_dblocks_props(dblocks_seq, {'dir_script': str(PACKAGE_DIR)})
            size_header = 29 if settings.get('header') == 'WECOM3' else 38

            obj = bbin.ConvertData(binary_filename=path, size_header=size_header,
                                   dblocks=dblocks_props, limit_read_lines=TEST_RUN_ROWS,
                                   logger=qlog, cur_file_number=1)
            obj.run()
            headers, _ = obj.get_data()
            if settings.get('add_instr_to_varname') == '1':
                headers = [(f"{h[0]}_{h[2]}", h[1], h[2]) for h in headers]
            df = obj.get_dataframe(headers)

            write(Text(f'✓ Converted OK: {df.shape[0]} row(s) × {df.shape[1]} column(s)',
                       style='bold green'))
            names = [h[0] for h in headers]
            shown = ', '.join(names[:12]) + (' …' if len(names) > 12 else '')
            write(Text(f'Variables ({len(names)}): {shown}', style='dim'))
            for line in df.head(3).to_string(max_cols=8).splitlines():
                write(Text('  ' + line))
            write(Text('Test run only — no files were written. Press Run (r) to convert for real.',
                       style='dim'))
        except Exception as exc:
            import traceback
            write(Text(f'✗ Test run failed: {exc}', style='bold red'))
            write(Text(traceback.format_exc(), style='red'))
        finally:
            self.call_from_thread(self._run_finished)

    def _begin_busy(self, subtitle: str) -> None:
        """Mark a run/test as in progress and disable the action buttons."""
        self._busy = True
        for bid in ('#btn-run', '#btn-save', '#btn-load', '#btn-export', '#btn-test', '#btn-validate', '#btn-detect'):
            self.query_one(bid, Button).disabled = True
        self.sub_title = subtitle

    def action_run_conversion(self) -> None:
        if self._busy:
            self.notify('A conversion is already running.', severity='warning')
            return
        settings, days, avoid = self._effective_settings()
        problems = self._validate(settings, days)
        if any(level == 'error' for level, _ in problems):
            self._write_preview(settings, days, avoid, problems)
            self.notify('Cannot run — fix the errors first.', severity='error')
            return

        self._stop_event.clear()
        self._file_status.clear()
        self._begin_busy('running…')
        # Stop is available only during a real conversion run.
        stop_btn = self.query_one('#btn-stop', Button)
        stop_btn.disabled = False
        bar = self.query_one('#progress', ProgressBar)
        bar.display = True
        bar.update(total=None, progress=0)  # total is set on the first progress report
        console = self.query_one('#console', RichLog)
        console.write(Text('─' * 40, style='dim'))
        console.write(Text('Starting conversion…', style='bold cyan'))
        self._run_engine(settings, avoid)

    def action_stop_conversion(self) -> None:
        """Ask the running conversion to stop after the current file."""
        if not self._busy or self._stop_event.is_set():
            return
        self._stop_event.set()
        self.query_one('#btn-stop', Button).disabled = True
        self.sub_title = 'stopping…'
        self.notify('Stopping — the current file will finish first.', severity='warning')
        console = self.query_one('#console', RichLog)
        console.write(Text('Stop requested — finishing the current file…', style='bold yellow'))

    # -- run plumbing --------------------------------------------------------

    @staticmethod
    def _add_run_dirs(settings: dict) -> None:
        """Set the package directory keys the engine needs (for data blocks,
        settings snapshot, etc.). Source/output folders are NOT defaulted: if the
        user didn't choose them, validation flags it instead of silently using
        the package folder."""
        settings['dir_script'] = str(PACKAGE_DIR)
        settings['dir_settings'] = SETTINGS_DIR
        settings['dir_bico'] = PACKAGE_DIR.parent
        settings['dir_root'] = PACKAGE_DIR.parent.parent

    @staticmethod
    def _apply_recent_days(settings: dict, days: int) -> None:
        """Replace the date range with the most recent `days` (mirrors CLI -d)."""
        start = dt.datetime.now().date() - dt.timedelta(days=days)
        settings['start_date'] = dt.datetime(start.year, start.month, start.day, 0, 0) \
            .strftime('%Y-%m-%d %H:%M')
        settings['end_date'] = dt.datetime.now().strftime('%Y-%m-%d %H:%M')

    @work(thread=True, exclusive=True, group='bico-run')
    def _run_engine(self, settings: dict, avoidduplicates: bool) -> None:
        console = self.query_one('#console', RichLog)
        try:
            engine = BicoEngine(settings_dict=settings, usedgui=False,
                                avoidduplicates=avoidduplicates,
                                progress_callback=self._on_progress,
                                file_progress_callback=self._on_file_progress,
                                should_stop=self._stop_event.is_set)
            # Route the engine's logger into the console; drop the stdout stream
            # handler the engine added (it would otherwise fight the TUI).
            for handler in list(engine.logger.handlers):
                if isinstance(handler, logging.StreamHandler) \
                        and not isinstance(handler, logging.FileHandler):
                    engine.logger.removeHandler(handler)
            engine.logger.addHandler(make_tui_handler(self, console))
            engine.run()
        except Exception as exc:  # surface failures in the console rather than crash
            import traceback
            self.call_from_thread(console.write, Text(f'(!) RUN FAILED: {exc}', style='bold red'))
            self.call_from_thread(console.write, Text(traceback.format_exc(), style='red'))
        finally:
            self.call_from_thread(self._run_finished)

    def _on_progress(self, done: int, total: int) -> None:
        """Engine progress callback (worker thread) → update the progress bar."""
        self.call_from_thread(self._update_progress, done, total)

    def _update_progress(self, done: int, total: int) -> None:
        bar = self.query_one('#progress', ProgressBar)
        bar.display = True
        bar.update(total=total, progress=done)

    def _on_file_progress(self, idx: int, total: int, filename: str, step: str, frac: float) -> None:
        """Engine per-file progress (worker thread) → update the live status lines."""
        self.call_from_thread(self._update_file_status, idx, total, filename, step, frac)

    @staticmethod
    def _status_line(idx: int, total: int, filename: str, step: str, frac: float) -> Text:
        pct = int(frac * 100)
        bar_width = 16
        filled = round(frac * bar_width)
        return Text.assemble(
            ('▶ ', 'bold green'),
            (f'[{idx}/{total}] ', 'cyan'),
            (filename, 'bold magenta'),
            ('  ', ''),
            ('━' * filled, 'bright_cyan'),
            ('━' * (bar_width - filled), 'grey30'),
            (f' {pct:3d}%  ', 'bright_cyan'),
            (step, 'bold cyan'),
        )

    def _update_file_status(self, idx: int, total: int, filename: str, step: str, frac: float) -> None:
        # One line per in-progress file (several convert at once in parallel).
        # A finished file drops off; the count bar and the log show completion.
        if step == 'Done' and frac >= 1.0:
            self._file_status.pop(idx, None)
        else:
            self._file_status[idx] = (total, filename, step, frac)
        self._render_file_status()

    def _render_file_status(self) -> None:
        status = self.query_one('#run-status', Static)
        if not self._file_status:
            status.update('')
            return
        status.display = True
        text = Text()
        for i, idx in enumerate(sorted(self._file_status)):
            if i:
                text.append('\n')
            text.append_text(self._status_line(idx, *self._file_status[idx]))
        status.update(text)

    def _run_finished(self) -> None:
        self._busy = False
        self._stop_event.clear()
        self._file_status.clear()
        self.query_one('#btn-stop', Button).disabled = True
        for bid in ('#btn-save', '#btn-load', '#btn-export', '#btn-test', '#btn-validate', '#btn-detect'):
            self.query_one(bid, Button).disabled = False
        self._refresh_run_enabled()  # Run stays gated by validation state
        self.query_one('#progress', ProgressBar).display = False
        self.query_one('#run-status', Static).display = False
        self.sub_title = f'binary converter  ·  v{info.__version__}'


def run_tui() -> None:
    BicoApp().run()
