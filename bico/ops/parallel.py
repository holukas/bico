"""Per-file conversion worker, usable sequentially or in a process pool.

Converting binary files is independent per file, so a run can process several
files concurrently. ``process_file`` does the whole per-file pipeline for one
file (convert -> write -> stats -> plots) and returns a small, picklable result
(a one-row stats frame, captured log text, and a status), so it is safe to run in
a separate process. Stats and plots are computed from the in-memory frame (no CSV
re-read). It never returns the large converted DataFrame.
"""
import io
import logging
import os
import traceback

import pandas as pd

from bico.ops import bin as bbin, file as bfile, stats as bstats, vis
from bico.ops.logger import get_formatter


def _capture_logger(name):
    """A logger that writes only to an in-memory buffer (returned for replay)."""
    logger = logging.getLogger(name)
    logger.handlers.clear()
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(get_formatter())
    logger.addHandler(handler)
    return logger, buf


def _extract_plot_series(df, n_vars, n):
    """First ``n`` values of the first ``n_vars`` numeric columns.

    Returns a list of small picklable dicts ``{'var', 'units', 'y'}`` (``y`` a
    plain list of floats, missing values left as -9999 for the renderer to drop),
    one per variable, in column order. Non-numeric columns (e.g. text status
    fields) are skipped, so the list holds the first ``n_vars`` *plottable*
    variables. May be shorter than ``n_vars`` if the frame has fewer.
    """
    out = []
    for col in df.columns:
        if len(out) >= n_vars:
            break
        try:
            y = [float(v) for v in df[col].head(n).tolist()]
        except (TypeError, ValueError):
            continue  # skip non-numeric columns
        name = col[0] if isinstance(col, tuple) else col
        units = str(col[1]) if isinstance(col, tuple) and len(col) > 1 else ''
        out.append({'var': str(name), 'units': units, 'y': y})
    return out


def _make_reporter(task):
    """Build a ``report(step, fraction)`` callback for live per-file progress.

    Sequential runs pass an in-process callable (``task['progress_cb']``);
    parallel runs pass a picklable ``multiprocessing`` queue
    (``task['progress_queue']``) that the main process drains. Headless runs pass
    neither, so reporting is a no-op. Failures here never disturb conversion.
    """
    cb = task.get('progress_cb')
    queue = task.get('progress_queue')
    if cb is None and queue is None:
        return lambda step, frac: None

    idx = task.get('task_index', task['counter'])
    bin_file = task['bin_file']

    def report(step, frac):
        try:
            if cb is not None:
                cb(step, frac)
            else:
                queue.put_nowait({'idx': idx, 'file': bin_file, 'step': step, 'frac': frac})
        except Exception:
            pass

    return report


def _make_plot_reporter(task):
    """Build a ``report_plot(series)`` callback for the live plot.

    Emits one file's plot series as soon as it is available (right after the
    table is built, before the slower save/stats/plots tail), so the plot updates
    during conversion rather than only when the file's future completes. Like
    ``_make_reporter``: sequential runs use an in-process callable
    (``task['plot_cb']``), parallel runs push onto the shared
    ``task['progress_queue']`` (drained live by the main process). A no-op when
    neither is set. Failures never disturb conversion.
    """
    cb = task.get('plot_cb')
    queue = task.get('progress_queue')
    if cb is None and queue is None:
        return lambda series: None

    idx = task.get('task_index', task['counter'])
    bin_file = task['bin_file']

    def report_plot(series):
        if not series:
            return
        try:
            if cb is not None:
                cb(idx, bin_file, series)
            else:
                queue.put_nowait({'idx': idx, 'file': bin_file, 'plot': series})
        except Exception:
            pass

    return report_plot


def process_file(task):
    """Convert a single binary file and produce its outputs.

    Parameters
    ----------
    task : dict
        Fully picklable description of the work (paths, flags, the data-block
        properties, etc.). See ``BicoEngine._build_tasks`` in bico.py.

    Returns
    -------
    dict with keys: counter, bin_filedate, status ('ok'|'error'), error,
    stats_row (one-row DataFrame or None), log (captured log text).
    """
    logger, buf = _capture_logger(f"bico_worker_{task['counter']}")
    report = _make_reporter(task)
    report_plot = _make_plot_reporter(task)
    result = {
        'counter': task['counter'],
        'bin_filedate': task['bin_filedate'],
        'status': 'ok',
        'error': None,
        'stats_row': None,
        'plot_series': None,
        'log': '',
    }
    try:
        report('Reading file', 0.0)
        obj = bbin.ConvertData(
            binary_filename=task['bin_filepath'],
            size_header=task['size_header'],
            dblocks=task['dblocks_props'],
            limit_read_lines=task['row_limit'],
            logger=logger,
            cur_file_number=task['counter'],
            progress_cb=lambda frac: report('Converting', frac),
        )
        obj.run()
        dblock_headers, _ = obj.get_data()

        if task['add_instr_to_varname']:
            dblock_headers = [(f"{h[0]}_{h[2]}", h[1], h[2]) for h in dblock_headers]

        report('Building table', 0.85)
        ascii_df = obj.get_dataframe(dblock_headers)

        # Optional live plot: emit the first N values of the first few variables
        # as soon as the table exists (before the save/stats/plots tail), so the
        # plot updates live during conversion. Never let it disturb conversion.
        plot_vars = task.get('plot_vars', 0)
        if plot_vars:
            try:
                result['plot_series'] = _extract_plot_series(
                    ascii_df, plot_vars, task.get('plot_rows', 100))
                report_plot(result['plot_series'])
            except Exception:
                result['plot_series'] = None

        report('Saving CSV', 0.90)
        ascii_filepath = bfile.export_raw_data_ascii(
            df=ascii_df, outdir=task['dir_raw_data_ascii'], outfilename=task['ascii_filename'],
            logger=logger, compression=task['compression'],
        )

        # Stats and plots run on the in-memory frame we just wrote, so there is no
        # need to re-read (and gzip-decompress + reparse) the CSV. Both consumers
        # coerce -9999 -> NaN themselves, so this is equivalent to reading the file
        # back, minus a full serialize/parse round trip per file.

        # Per-file stats as a single-row frame (the main process concatenates them)
        report('Stats', 0.96)
        stats_row = bstats.calc(
            stats_df=ascii_df.copy(), stats_coll_df=pd.DataFrame(),
            bin_filedate=task['bin_filedate'], counter_bin_files=1, logger=logger,
        )
        bfd = task['bin_filedate']
        stats_row.loc[bfd, ('_filesize', '[Bytes]', '[FILE]', 'total')] = os.path.getsize(task['bin_filepath'])
        stats_row.loc[bfd, ('_columns', '[#]', '[FILE]', 'total')] = len(ascii_df.columns)
        stats_row.loc[bfd, ('_total_values', '[#]', '[FILE]', 'total')] = ascii_df.size
        result['stats_row'] = stats_row

        if task['plot_ts_hires'] or task['plot_histogram_hires']:
            report('Plotting', 0.98)
        if task['plot_ts_hires']:
            vis.high_res_ts(df=ascii_df.copy(), outfile=task['ascii_filename'],
                            outdir=task['dir_plots_hires'], logger=logger)
        if task['plot_histogram_hires']:
            vis.high_res_histogram(df=ascii_df.copy(), outfile=task['ascii_filename'],
                                   outdir=task['dir_plots_hires'], logger=logger)
        report('Done', 1.0)
    except Exception as exc:  # isolate failures: one bad file must not kill the batch
        result['status'] = 'error'
        result['error'] = f"{exc}\n{traceback.format_exc()}"

    result['log'] = buf.getvalue()
    return result
