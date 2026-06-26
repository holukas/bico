"""Typed view over the settings that live in ``bico.settings``.

The settings file is read as a flat ``dict`` of strings (see
``ops.setup.read_settings_file_to_dict``). That raw dict is convenient to read
and write but means every consumer re-coerces values inline (``== '1'`` for
booleans, ``int(...)`` for numbers) and there is no single place that says what
a setting means or what type it has.

``UserSettings`` is that single place: a frozen, typed snapshot built once from
the raw dict via :meth:`UserSettings.from_raw`. ``RunContext`` is the companion
for the *derived* values a run computes (run id, output folders, the strptime
pattern) — the keys listed in ``ops.file.DERIVED_SETTING_KEYS`` — so user config
and per-run state stop sharing one mutable dict.

This module is introduced alongside the existing ``settings_dict`` flow: nothing
consumes these objects yet. :meth:`from_raw` is intentionally lenient (every
field has a default, missing keys never raise) so constructing it in the run
path cannot break an existing run. Validation is tightened later, as call sites
migrate off the raw dict.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_DATETIME_FMT = '%Y-%m-%d %H:%M'


def _as_bool(value) -> bool:
    """Settings booleans are stored as the strings ``'1'`` / ``'0'``."""
    return str(value).strip() == '1'


def _as_int(value, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _as_path(value) -> Optional[Path]:
    value = '' if value is None else str(value).strip()
    return Path(value) if value else None


def _as_datetime(value) -> Optional[dt.datetime]:
    try:
        return dt.datetime.strptime(str(value).strip(), _DATETIME_FMT)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class UserSettings:
    """A typed snapshot of the user-configurable keys in ``bico.settings``.

    Built once from the raw string dict; downstream code reads typed attributes
    instead of re-coercing strings. Maps 1:1 to the file's user keys (the
    reference-only ``dir_server_*`` entries are intentionally ignored).
    """

    # instruments
    site: str = ''
    header: str = ''
    instrument_1: str = ''
    instrument_2: str = ''
    instrument_3: str = ''

    # raw data
    dir_source: Optional[Path] = None
    start_date: Optional[dt.datetime] = None
    end_date: Optional[dt.datetime] = None
    filename_datetime_format: str = ''
    file_size_min: int = 0
    file_limit: int = 0
    row_limit: int = 0
    select_random_files: bool = False

    # output
    dir_out: Optional[Path] = None
    output_folder_name_prefix: str = ''
    file_compression: str = ''
    num_processes: int = 0
    add_instr_to_varname: bool = False

    # plots
    plot_file_availability: bool = False
    plot_ts_hires: bool = False
    plot_histogram_hires: bool = False
    plot_ts_agg: bool = False

    @classmethod
    def from_raw(cls, raw: dict) -> "UserSettings":
        """Build from the raw string dict read out of ``bico.settings``.

        Lenient by design: every field falls back to a default, so a partial or
        older settings file parses without raising.
        """
        return cls(
            site=raw.get('site', ''),
            header=raw.get('header', ''),
            instrument_1=raw.get('instrument_1', ''),
            instrument_2=raw.get('instrument_2', ''),
            instrument_3=raw.get('instrument_3', ''),
            dir_source=_as_path(raw.get('dir_source')),
            start_date=_as_datetime(raw.get('start_date')),
            end_date=_as_datetime(raw.get('end_date')),
            filename_datetime_format=raw.get('filename_datetime_format', ''),
            file_size_min=_as_int(raw.get('file_size_min')),
            file_limit=_as_int(raw.get('file_limit')),
            row_limit=_as_int(raw.get('row_limit')),
            select_random_files=_as_bool(raw.get('select_random_files')),
            dir_out=_as_path(raw.get('dir_out')),
            output_folder_name_prefix=raw.get('output_folder_name_prefix', ''),
            file_compression=raw.get('file_compression', ''),
            num_processes=_as_int(raw.get('num_processes')),
            add_instr_to_varname=_as_bool(raw.get('add_instr_to_varname')),
            plot_file_availability=_as_bool(raw.get('plot_file_availability')),
            plot_ts_hires=_as_bool(raw.get('plot_ts_hires')),
            plot_histogram_hires=_as_bool(raw.get('plot_histogram_hires')),
            plot_ts_agg=_as_bool(raw.get('plot_ts_agg')),
        )

    @property
    def instruments(self) -> list[str]:
        """The three instrument data-block ids, in order.

        Replaces ``BicoEngine.assemble_datablock_sequence``'s manual key scan.
        """
        return [self.instrument_1, self.instrument_2, self.instrument_3]

    @property
    def header_size(self) -> int:
        """Binary header size in bytes for the configured logger header.

        Centralises the ``29 if header == 'WECOM3' else 38`` rule currently
        inlined in ``BicoEngine.run``. (A fuller fix reads this from the header
        spec, but this already removes the magic number from the engine.)
        """
        return 29 if self.header == 'WECOM3' else 38


@dataclass(frozen=True)
class RunContext:
    """Values a single run derives from :class:`UserSettings`.

    These are the keys in ``ops.file.DERIVED_SETTING_KEYS``: the run id, the
    per-run output folders, and the strptime pattern built from the filename
    datetime format. Kept separate from ``UserSettings`` so per-run state and
    user config no longer share one mutable dict. ``BicoEngine`` builds one of
    these per run as the source of truth for its output paths, then mirrors the
    values back onto the legacy settings dict for consumers that still read it.
    """

    run_id: str
    datetime_parsing_string: str
    dir_out_run: Path
    dir_out_run_log: Path
    dir_out_run_plots: Path
    dir_out_run_plots_hires: Path
    dir_out_run_plots_agg: Path
    dir_out_run_raw_data_ascii: Path

    @classmethod
    def create(cls, settings: UserSettings, run_id: str) -> "RunContext":
        # Imported lazily to avoid any import cycle with ops.file.
        from bico.ops import file as ops_file

        base = settings.dir_out / f"{settings.output_folder_name_prefix}_{run_id}"
        plots = base / 'plots'
        return cls(
            run_id=run_id,
            datetime_parsing_string=ops_file.datetime_parsing_string(
                settings.filename_datetime_format),
            dir_out_run=base,
            dir_out_run_log=base / 'log',
            dir_out_run_plots=plots,
            dir_out_run_plots_hires=plots / 'hires',
            dir_out_run_plots_agg=plots / 'agg',
            dir_out_run_raw_data_ascii=base / 'raw_data_ascii',
        )

    def make_dirs(self) -> None:
        for d in (self.dir_out_run, self.dir_out_run_log, self.dir_out_run_plots,
                  self.dir_out_run_plots_hires, self.dir_out_run_plots_agg,
                  self.dir_out_run_raw_data_ascii):
            d.mkdir(parents=True, exist_ok=True)
