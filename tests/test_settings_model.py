"""Tests for the typed settings model (``bico.settings.model``).

These lock in that ``UserSettings.from_raw`` matches the real packaged
``bico.settings`` file and coerces the string values to the right types, and
that it stays lenient (a partial/empty dict must not raise) so wiring it into
the live run path cannot break a run.
"""
import datetime as dt
from pathlib import Path

from bico.ops import setup as ops_setup
from bico.settings.model import UserSettings, RunContext

from conftest import PACKAGE_DIR


def _real_raw() -> dict:
    """The actual packaged settings file, read the same way the app reads it."""
    return ops_setup.read_settings_file_to_dict(
        dir_settings=PACKAGE_DIR / "settings",
        file="bico.settings",
        reset_paths=False,
    )


def test_from_raw_parses_packaged_settings():
    s = UserSettings.from_raw(_real_raw())

    # strings pass through
    assert s.site == "CH-DAV"
    assert s.header == "WECOM3"
    assert s.file_compression == "gzip"

    # ints are coerced from strings
    assert isinstance(s.file_limit, int) and s.file_limit == 0
    assert isinstance(s.row_limit, int)
    assert isinstance(s.num_processes, int) and s.num_processes == 1

    # '1'/'0' become real bools
    assert s.add_instr_to_varname is True
    assert s.plot_histogram_hires is False
    assert isinstance(s.select_random_files, bool)

    # paths and dates are parsed
    assert isinstance(s.dir_source, Path)
    assert isinstance(s.start_date, dt.datetime)
    assert isinstance(s.end_date, dt.datetime)


def test_derived_properties():
    s = UserSettings.from_raw(_real_raw())
    assert s.instruments == ["HS50-A", "IRGA72-A", "QCL-C2"]
    assert s.header_size == 29  # WECOM3
    assert UserSettings.from_raw({"header": "OTHER"}).header_size == 38


def test_from_raw_is_lenient_on_empty_and_garbage():
    # missing keys: defaults, no exception
    empty = UserSettings.from_raw({})
    assert empty.site == ""
    assert empty.file_limit == 0
    assert empty.dir_source is None
    assert empty.start_date is None
    assert empty.add_instr_to_varname is False

    # unparseable numbers/dates fall back instead of raising
    garbage = UserSettings.from_raw({"row_limit": "abc", "start_date": "not-a-date"})
    assert garbage.row_limit == 0
    assert garbage.start_date is None


def test_run_context_derives_paths(tmp_path):
    s = UserSettings.from_raw({
        "dir_out": str(tmp_path),
        "output_folder_name_prefix": "test",
        "filename_datetime_format": "yyyymmddHH.XMM",
    })
    ctx = RunContext.create(s, run_id="BICO-20260101-000000")

    assert ctx.dir_out_run == tmp_path / "test_BICO-20260101-000000"
    assert ctx.dir_out_run_plots_hires == ctx.dir_out_run / "plots" / "hires"
    assert ctx.dir_out_run_raw_data_ascii == ctx.dir_out_run / "raw_data_ascii"
    assert ctx.datetime_parsing_string  # non-empty strptime pattern was built
