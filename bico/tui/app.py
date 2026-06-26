"""Textual TUI for bico.

Left column: every setting from BICO.settings plus the run-time options that the
CLI exposes (recent-days window, avoid-duplicates). Right column: a live Rich
console showing the run log. The same conversion engine (``BicoEngine``) used by
the headless CLI does the work, driven here from a worker thread so the UI stays
responsive.
"""
import datetime as dt
import logging
from pathlib import Path

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (Button, DirectoryTree, Footer, Header, Input, Label,
                             RichLog, Select, Static, Switch)

import bico
from bico.bico import BicoEngine
from bico.ops import file as bfile, setup as ops_setup
from bico.settings import _version as info
from bico.tui.log_handler import make_tui_handler

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
# 'int' | 'switch'. Keys match BICO.settings keys, except the run-only options
# 'days' and 'avoidduplicates', which are not persisted to the settings file.
INSTRUMENT_FIELDS = [
    ('site', 'Site', 'select', SITES),
    ('header', 'Header', 'select', HEADERS),
    ('instrument_1', 'Instrument 1 (sonic)', 'select', SONIC_ANEMOMETERS),
    ('instrument_2', 'Instrument 2 (gas analyzer)', 'select', GAS_ANALYZERS),
    ('instrument_3', 'Instrument 3 (gas analyzer)', 'select', GAS_ANALYZERS),
]
RAWDATA_FIELDS = [
    ('dir_source', 'Source folder', 'path', None),
    ('start_date', 'Start date (YYYY-MM-DD hh:mm)', 'input', None),
    ('end_date', 'End date (YYYY-MM-DD hh:mm)', 'input', None),
    ('filename_datetime_format', 'Datetime format in filename', 'input', None),
    ('file_ext', 'File extension', 'input', None),
    ('file_size_min', 'Minimum file size (bytes)', 'int', None),
    ('file_limit', 'File limit (0 = no limit)', 'int', None),
    ('row_limit', 'Row limit per file (0 = no limit)', 'int', None),
    ('select_random_files', 'Select random files (0 = no)', 'int', None),
]
OUTPUT_FIELDS = [
    ('dir_out', 'Output folder', 'path', None),
    ('output_folder_name_prefix', 'Output folder name prefix', 'input', None),
    ('file_compression', 'File compression', 'select', COMPRESSION),
    ('num_processes', 'Worker processes (0 = auto)', 'int', None),
    ('add_instr_to_varname', 'Add instrument to variable name', 'switch', None),
    ('plot_file_availability', 'Plot: file availability heatmap', 'switch', None),
    ('plot_ts_hires', 'Plot: high-res time series', 'switch', None),
    ('plot_histogram_hires', 'Plot: high-res histograms', 'switch', None),
    ('plot_ts_agg', 'Plot: aggregated time series', 'switch', None),
]
RUN_FIELDS = [
    ('days', 'Recent days (0 = use date range above)', 'int', None),
    ('avoidduplicates', 'Avoid duplicates already in output folder', 'switch', None),
]

ALL_FIELDS = INSTRUMENT_FIELDS + RAWDATA_FIELDS + OUTPUT_FIELDS + RUN_FIELDS
FIELD_KIND = {key: kind for key, _, kind, _ in ALL_FIELDS}
# Keys that are persisted to BICO.settings (everything but the run-only options).
PERSISTED_KEYS = [key for key, _, _, _ in INSTRUMENT_FIELDS + RAWDATA_FIELDS + OUTPUT_FIELDS]


def _field_id(key: str) -> str:
    return f'field-{key}'


class DirectoryPickerScreen(ModalScreen[str]):
    """Modal folder browser. Dismisses with the chosen path, or None if cancelled."""

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

    def compose(self) -> ComposeResult:
        with Vertical(id='picker'):
            yield Static('Select a folder', classes='picker-title')
            yield Label(self._selected, id='picker-current')
            yield DirectoryTree(str(self._root), id='picker-tree')
            with Horizontal(id='picker-actions'):
                yield Button('Up', id='picker-up')
                yield Button('Select folder', id='picker-ok', variant='success')
                yield Button('Cancel', id='picker-cancel')

    def _set_selected(self, path) -> None:
        self._selected = str(path)
        self.query_one('#picker-current', Label).update(self._selected)

    @on(DirectoryTree.DirectorySelected)
    def _on_dir_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        self._set_selected(event.path)

    @on(Button.Pressed, '#picker-up')
    def _on_up(self) -> None:
        tree = self.query_one('#picker-tree', DirectoryTree)
        parent = Path(tree.path).parent
        tree.path = str(parent)        # re-root the tree one level up
        self._set_selected(parent)

    @on(Button.Pressed, '#picker-ok')
    def _on_ok(self) -> None:
        self.dismiss(self._selected)

    @on(Button.Pressed, '#picker-cancel')
    def _on_cancel(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class BicoApp(App):
    """bico — binary converter, as a terminal UI."""

    CSS_PATH = 'app.tcss'
    TITLE = 'bico'
    SUB_TITLE = f'binary converter  ·  v{info.__version__}'

    BINDINGS = [
        ('r', 'run_conversion', 'Run'),
        ('s', 'save_settings', 'Save'),
        ('ctrl+l', 'clear_console', 'Clear log'),
        ('q', 'quit', 'Quit'),
    ]

    def __init__(self):
        super().__init__()
        # Base settings read from file; non-form keys (e.g. dir_server_*) are
        # preserved here and merged back in when collecting form values.
        self._base_settings = ops_setup.read_settings_file_to_dict(
            dir_settings=SETTINGS_DIR, file='BICO.settings', reset_paths=False)
        self._running = False

    # -- layout --------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id='body'):
            with VerticalScroll(id='settings'):
                yield from self._section('Instruments', INSTRUMENT_FIELDS)
                yield from self._section('Raw data', RAWDATA_FIELDS)
                yield from self._section('Output', OUTPUT_FIELDS)
                yield from self._section('Run options', RUN_FIELDS)
                with Horizontal(id='actions'):
                    yield Button('Save settings', id='btn-save', variant='primary')
                    yield Button('Run conversion', id='btn-run', variant='success')
            with Vertical(id='console-pane'):
                yield Static('Console', classes='pane-title')
                yield RichLog(id='console', highlight=False, markup=False, wrap=True)
        yield Footer()

    def _section(self, title: str, fields):
        yield Static(title, classes='section')
        for key, label, kind, options in fields:
            if kind == 'switch':
                with Horizontal(classes='field field-switch'):
                    yield Label(label, classes='field-label')
                    yield Switch(id=_field_id(key))
            elif kind == 'path':
                with Vertical(classes='field'):
                    yield Label(label, classes='field-label')
                    with Horizontal(classes='path-row'):
                        yield Input(id=_field_id(key), type='text')
                        yield Button('Browse…', id=f'browse-{key}', classes='browse-btn')
            else:
                with Vertical(classes='field'):
                    yield Label(label, classes='field-label')
                    if kind == 'select':
                        yield Select([(o, o) for o in options], id=_field_id(key),
                                     allow_blank=False)
                    else:
                        yield Input(id=_field_id(key),
                                    type='integer' if kind == 'int' else 'text')

    # -- wiring --------------------------------------------------------------

    def on_mount(self) -> None:
        self._load_settings_into_form(self._base_settings)
        console = self.query_one('#console', RichLog)
        console.write(Text('Ready. Adjust settings and press Run (r).', style='dim'))

    def _load_settings_into_form(self, settings: dict) -> None:
        for key, kind in FIELD_KIND.items():
            value = settings.get(key, '')
            widget = self.query_one(f'#{_field_id(key)}')
            if kind == 'switch':
                widget.value = str(value) == '1'
            elif kind == 'select':
                widget.value = value if value else Select.BLANK
            else:
                widget.value = '' if value is None else str(value)

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

    def action_save_settings(self) -> None:
        settings = self._collect_form()
        settings['dir_settings'] = SETTINGS_DIR
        bfile.save_settings_to_file(settings)
        self.notify('Settings saved to BICO.settings', severity='information')

    @on(Button.Pressed, '#btn-save')
    def _on_save(self) -> None:
        self.action_save_settings()

    @on(Button.Pressed, '#btn-run')
    def _on_run(self) -> None:
        self.action_run_conversion()

    @on(Button.Pressed, '#browse-dir_source')
    def _browse_source(self) -> None:
        self._open_picker('dir_source')

    @on(Button.Pressed, '#browse-dir_out')
    def _browse_out(self) -> None:
        self._open_picker('dir_out')

    def _open_picker(self, key: str) -> None:
        field = self.query_one(f'#{_field_id(key)}', Input)

        def apply(path: str | None) -> None:
            if path:
                field.value = path

        self.push_screen(DirectoryPickerScreen(field.value), apply)

    def action_run_conversion(self) -> None:
        if self._running:
            self.notify('A conversion is already running.', severity='warning')
            return
        settings = self._collect_form()
        self._add_run_dirs(settings)
        days, avoid = self._run_options()
        if days:
            self._apply_recent_days(settings, days)

        self._running = True
        self.query_one('#btn-run', Button).disabled = True
        self.query_one('#btn-save', Button).disabled = True
        self.sub_title = 'running…'
        console = self.query_one('#console', RichLog)
        console.write(Text('─' * 40, style='dim'))
        console.write(Text('Starting conversion…', style='bold cyan'))
        self._run_engine(settings, avoid)

    # -- run plumbing --------------------------------------------------------

    @staticmethod
    def _add_run_dirs(settings: dict) -> None:
        """Set the directory keys the engine expects (mirrors the old GUI)."""
        settings['dir_script'] = str(PACKAGE_DIR)
        settings['dir_settings'] = SETTINGS_DIR
        settings['dir_bico'] = PACKAGE_DIR.parent
        settings['dir_root'] = PACKAGE_DIR.parent.parent
        # Empty source/output paths default to the package dir, as the GUI did.
        if not settings.get('dir_source'):
            settings['dir_source'] = settings['dir_bico']
        if not settings.get('dir_out'):
            settings['dir_out'] = settings['dir_bico']

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
                                avoidduplicates=avoidduplicates)
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

    def _run_finished(self) -> None:
        self._running = False
        self.query_one('#btn-run', Button).disabled = False
        self.query_one('#btn-save', Button).disabled = False
        self.sub_title = f'binary converter  ·  v{info.__version__}'
        self.query_one('#console', RichLog).write(Text('Done.', style='bold green'))


def run_tui() -> None:
    BicoApp().run()
