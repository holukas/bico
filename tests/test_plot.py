"""Tests for the TUI live-plot helpers.

These cover the two pure pieces behind the live plot: the worker-side column
extraction (``_extract_plot_series``, the first few variables) and the
dependency-free braille renderer (``render_braille_plot``, several series
overlaid in colour). Both are free of Textual/numpy-2 so they import and run in
the test environment without launching the TUI.
"""
import datetime as dt

import pandas as pd
from conftest import DATA_DIR, PACKAGE_DIR

from bico.ops import file as bfile
from bico.ops import parallel
from bico.ops.parallel import _extract_plot_series
from bico.tui.plot import render_braille_plot


def _frame(columns):
    """A 100-row MultiIndex frame with the given (name, units, datablock) columns."""
    data = {i: list(range(100)) for i in range(len(columns))}
    df = pd.DataFrame(data)
    df.columns = pd.MultiIndex.from_tuples(columns)
    return df


def test_extract_plot_series_returns_first_n_vars():
    df = _frame([("U", "[m+1_s-1]", "[HS50-A]"), ("V", "[m+1_s-1]", "[HS50-A]"),
                 ("W", "[m+1_s-1]", "[HS50-A]"), ("T_SONIC", "[K]", "[HS50-A]")])
    series = _extract_plot_series(df, 3, 5)
    assert [s["var"] for s in series] == ["U", "V", "W"]
    assert series[0] == {"var": "U", "units": "[m+1_s-1]", "y": [0.0, 1.0, 2.0, 3.0, 4.0]}


def test_extract_plot_series_skips_non_numeric_columns():
    # A non-numeric column (e.g. a text status field) is skipped, so the list
    # holds the first n_vars *plottable* variables.
    df = _frame([("status", "[text]", "[LGR]"), ("CO2", "[ppm]", "[IRGA72]"),
                 ("H2O", "[mmol]", "[IRGA72]")])
    df[("status", "[text]", "[LGR]")] = ["ok"] * 100
    series = _extract_plot_series(df, 2, 3)
    assert [s["var"] for s in series] == ["CO2", "H2O"]


def test_extract_plot_series_fewer_columns_than_requested():
    df = _frame([("CO2", "[ppm]", "[IRGA72]")])
    series = _extract_plot_series(df, 3, 5)
    assert len(series) == 1 and series[0]["var"] == "CO2"


def test_render_braille_plot_draws_braille():
    text = render_braille_plot([{"y": [i % 13 for i in range(100)]}])
    # The canvas uses Unicode braille patterns (U+2800..U+28FF).
    assert any(0x2800 <= ord(ch) < 0x2900 for ch in text.plain)


def test_render_braille_plot_overlays_multiple_series_in_colour():
    series = [
        {"var": "U", "y": [i % 10 for i in range(100)], "color": "red"},
        {"var": "V", "y": [(i * 2) % 10 for i in range(100)], "color": "green"},
        {"var": "W", "y": [(i * 3) % 10 for i in range(100)], "color": "blue"},
    ]
    text = render_braille_plot(series)
    # Each series' colour should appear among the rendered spans.
    used = {span.style for span in text.spans}
    assert {"red", "green", "blue"} <= used


def test_render_braille_plot_skips_missing_values():
    # All -9999 (missing) → nothing finite to draw.
    text = render_braille_plot([{"y": [-9999] * 20}])
    assert "no finite values" in text.plain


def test_render_braille_plot_handles_flat_series():
    # A constant series must not divide by a zero range; it still renders.
    text = render_braille_plot([{"y": [7.0] * 30}])
    assert any(0x2800 <= ord(ch) < 0x2900 for ch in text.plain)


def test_render_braille_plot_empty_input():
    assert "no finite values" in render_braille_plot([]).plain


# --- live emission: the worker reports plot data during conversion ------------

def test_make_plot_reporter_queue_path():
    """Parallel runs push the series list onto the shared progress queue."""
    events = []

    class _Q:
        def put_nowait(self, ev):
            events.append(ev)

    report = parallel._make_plot_reporter(
        {'counter': 3, 'task_index': 3, 'bin_file': 'f.X00', 'progress_queue': _Q()})
    series = [{'var': 'U', 'units': '[m]', 'y': [1.0, 2.0]}]
    report(series)
    report([])  # empty series is a no-op
    assert events == [{'idx': 3, 'file': 'f.X00', 'plot': series}]


def test_make_plot_reporter_cb_path():
    """Sequential runs call the in-process callback directly."""
    calls = []
    report = parallel._make_plot_reporter(
        {'counter': 2, 'task_index': 2, 'bin_file': 'b.X00',
         'plot_cb': lambda idx, fname, s: calls.append((idx, fname, s))})
    series = [{'var': 'CO2', 'units': '[ppm]', 'y': [9.0]}]
    report(series)
    assert calls == [(2, 'b.X00', series)]


def test_process_file_emits_plot_series_live(tmp_path):
    """The worker emits the first variables' values via plot_cb as soon as the
    table is built (before it returns), so the plot updates during a run."""
    dblocks = ["HS50-A", "IRGA72-A", "QCL-C3"]
    props = bfile.load_dblocks_props(dblocks, {"dir_script": str(PACKAGE_DIR)})
    captured = []
    task = {
        'counter': 1,
        'task_index': 1,
        'bin_file': 'CH-DAV_2021111013_sample.X00',
        'bin_filepath': DATA_DIR / "CH-DAV_2021111013_sample.X00",
        'bin_filedate': dt.datetime(2021, 11, 10, 13, 0),
        'ascii_filename': 'CH-DAV_202111101300',
        'size_header': 29,
        'dblocks_props': props,
        'row_limit': 0,
        'add_instr_to_varname': True,
        'compression': 'None',
        'dir_raw_data_ascii': tmp_path,
        'dir_plots_hires': tmp_path,
        'plot_ts_hires': False,
        'plot_histogram_hires': False,
        'plot_vars': 3,
        'plot_cb': lambda idx, fname, series: captured.append((idx, fname, series)),
    }
    result = parallel.process_file(task)

    assert result['status'] == 'ok'
    assert len(captured) == 1, "plot series should be emitted exactly once, live"
    idx, fname, series = captured[0]
    assert idx == 1 and fname == 'CH-DAV_2021111013_sample.X00'
    # The first three variables are the sonic wind components U, V, W (renamed
    # with the instrument suffix because add_instr_to_varname is on).
    assert [s['var'] for s in series] == ['U_[HS50-A]', 'V_[HS50-A]', 'W_[HS50-A]']
    assert all(1 <= len(s['y']) <= 100 for s in series)
    # the same list is also in the result (completion path / debugging)
    assert result['plot_series'] == series
