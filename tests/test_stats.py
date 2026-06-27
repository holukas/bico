"""Tests for per-file stats, including the all-missing-variable diagnostic.

A variable defined in the settings but absent from the binary converts to all
-9999 (missing). That used to surface only as numpy's raw "Mean of empty slice"
RuntimeWarning on stderr, which corrupts the live TUI display. stats.calc now
reports it as a readable logger warning instead, and silences the raw numpy
warning so nothing leaks to stderr.
"""
import logging
import warnings

import numpy as np
import pandas as pd

from bico.ops import stats as bstats


def _frame(cols, rows):
    """Build a stats frame with MultiIndex (name, units, instr) columns."""
    return pd.DataFrame(rows, columns=pd.MultiIndex.from_tuples(cols))


def test_all_missing_variable_is_logged(caplog):
    cols = [('co2', '[ppm]', '[IRGA]'), ('ghost', '[ppm]', '[IRGA2]')]
    # 'co2' has valid data; 'ghost' is entirely -9999 (instrument not present).
    df = _frame(cols, [[1.0, -9999], [2.0, -9999]])
    logger = logging.getLogger('test_stats_missing')

    with caplog.at_level(logging.WARNING, logger=logger.name):
        bstats.calc(stats_df=df, stats_coll_df=pd.DataFrame(),
                    bin_filedate=pd.Timestamp('2026-01-01'),
                    counter_bin_files=1, logger=logger)

    msgs = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any('ghost' in m for m in msgs), msgs
    # The variable that has data must not be reported as missing.
    assert not any('co2' in m for m in msgs), msgs


def test_no_warning_when_all_variables_have_data(caplog):
    cols = [('co2', '[ppm]', '[IRGA]'), ('h2o', '[ppt]', '[IRGA]')]
    df = _frame(cols, [[1.0, 5.0], [2.0, 6.0]])
    logger = logging.getLogger('test_stats_ok')

    with caplog.at_level(logging.WARNING, logger=logger.name):
        bstats.calc(stats_df=df, stats_coll_df=pd.DataFrame(),
                    bin_filedate=pd.Timestamp('2026-01-01'),
                    counter_bin_files=1, logger=logger)

    assert not [r for r in caplog.records if r.levelno == logging.WARNING]


def test_raw_numpy_runtimewarning_is_suppressed():
    """The all-NaN agg must not leak a RuntimeWarning to stderr/the warnings system."""
    cols = [('ghost', '[ppm]', '[IRGA2]')]
    df = _frame(cols, [[-9999], [-9999]])
    logger = logging.getLogger('test_stats_quiet')

    with warnings.catch_warnings():
        warnings.simplefilter('error', RuntimeWarning)  # any leaked RuntimeWarning -> failure
        bstats.calc(stats_df=df, stats_coll_df=pd.DataFrame(),
                    bin_filedate=pd.Timestamp('2026-01-01'),
                    counter_bin_files=1, logger=logger)


def test_empty_frame_does_not_list_every_variable(caplog):
    """A file with no rows at all should not spam a warning per column."""
    cols = [('co2', '[ppm]', '[IRGA]'), ('h2o', '[ppt]', '[IRGA]')]
    df = _frame(cols, [])  # no data rows
    logger = logging.getLogger('test_stats_norows')

    with caplog.at_level(logging.WARNING, logger=logger.name):
        bstats.calc(stats_df=df, stats_coll_df=pd.DataFrame(),
                    bin_filedate=pd.Timestamp('2026-01-01'),
                    counter_bin_files=1, logger=logger)

    assert not [r for r in caplog.records if r.levelno == logging.WARNING]
