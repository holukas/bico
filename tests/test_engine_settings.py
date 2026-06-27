"""Engine-level tests that the typed UserSettings drives BicoEngine correctly.

These cover the orchestration call sites migrated off the raw settings_dict:
header size, instrument sequence, worker count, and the per-file task dict's
now-typed values (real bool/int instead of '1'/'0' strings). The conversion
golden tests exercise ops.bin directly and do not construct BicoEngine, so this
is the only coverage of that wiring.
"""
from pathlib import Path

from bico.bico import BicoEngine
from bico.settings.model import UserSettings


def _base_settings(tmp_path) -> dict:
    """A minimal settings dict with the keys BicoEngine.__init__ needs."""
    return {
        'site': 'CH-DAV',
        'header': 'WECOM3',
        'instrument_1': 'HS50-A',
        'instrument_2': 'IRGA72-A',
        'instrument_3': 'QCL-C3',
        'dir_out': str(tmp_path),
        'output_folder_name_prefix': 'test',
        'file_compression': 'gzip',
        'num_processes': '2',
        'file_limit': '0',
        'row_limit': '0',
        'add_instr_to_varname': '1',
        'plot_ts_hires': '1',
        'plot_histogram_hires': '0',
        'plot_file_availability': '0',
        'plot_ts_agg': '0',
    }


def _make_engine(tmp_path) -> BicoEngine:
    # console=... default True would stream to stdout; the engine builds the
    # logger with console on, which is harmless under pytest's capture.
    return BicoEngine(settings_dict=_base_settings(tmp_path), usedgui=False)


def test_engine_builds_typed_settings(tmp_path):
    engine = _make_engine(tmp_path)
    assert isinstance(engine.settings, UserSettings)
    assert engine.settings.header_size == 29  # WECOM3
    assert engine.settings.instruments == ['HS50-A', 'IRGA72-A', 'QCL-C3']


def test_run_context_built_and_mirrored(tmp_path):
    engine = _make_engine(tmp_path)
    ctx = engine.run_context

    # the run output folders actually exist on disk
    assert ctx.dir_out_run_raw_data_ascii.is_dir()
    assert ctx.dir_out_run_plots_hires.is_dir()
    assert ctx.dir_out_run_log.is_dir()

    # the derived values are mirrored onto the legacy dict for un-migrated readers
    # (file.SearchAll, the logger, the run snapshot)
    sd = engine.settings_dict
    assert sd['dir_out_run'] == ctx.dir_out_run
    assert sd['dir_out_run_raw_data_ascii'] == ctx.dir_out_run_raw_data_ascii
    assert sd['filename_datetime_parsing_string'] == ctx.datetime_parsing_string
    assert sd['run_id'] == engine.run_id


def test_n_workers_uses_num_processes(tmp_path):
    engine = _make_engine(tmp_path)
    # num_processes=2, capped by the number of tasks
    assert engine._n_workers(5) == 2
    assert engine._n_workers(1) == 1


def test_build_tasks_emits_typed_values(tmp_path):
    engine = _make_engine(tmp_path)
    # _build_tasks reads the strptime pattern from run_context; override it so the
    # synthetic filename below parses. The dir_out_run_* paths come from the
    # RunContext built in __init__.
    object.__setattr__(engine.run_context, 'datetime_parsing_string', '%Y%m%d%H%M')
    engine.bin_size_header = engine.settings.header_size
    engine.dblocks_props = []  # normally loaded in run(); passed straight into the task

    bin_found = {'sample': Path('202111101300')}  # .name parses with the format above
    tasks = engine._build_tasks(bin_found, availablefiles=False, logger=engine.logger)

    assert len(tasks) == 1
    task = tasks[0]
    # values are now real types, not '1'/'0'/str-int
    assert task['row_limit'] == 0 and isinstance(task['row_limit'], int)
    assert task['add_instr_to_varname'] is True
    assert task['plot_ts_hires'] is True
    assert task['plot_histogram_hires'] is False
    assert task['compression'] == 'gzip'
    assert task['size_header'] == 29
    assert task['ascii_filename'] == 'CH-DAV_202111101300'
