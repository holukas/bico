"""Per-file conversion worker, usable sequentially or in a process pool.

Converting binary files is independent per file, so a run can process several
files concurrently. ``process_file`` does the whole per-file pipeline for one
file (convert -> write -> read back -> stats -> plots) and returns a small,
picklable result (a one-row stats frame, captured log text, and a status), so it
is safe to run in a separate process. It never returns the large converted
DataFrame.
"""
import io
import logging
import os
import traceback

import pandas as pd

from bico.ops import bin as bbin, file as bfile, format_data, stats as bstats, vis
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


def process_file(task):
    """Convert a single binary file and produce its outputs.

    Parameters
    ----------
    task : dict
        Fully picklable description of the work (paths, flags, the data-block
        properties, etc.). See ``build_task`` in bico.py.

    Returns
    -------
    dict with keys: counter, bin_filedate, status ('ok'|'error'), error,
    stats_row (one-row DataFrame or None), log (captured log text).
    """
    logger, buf = _capture_logger(f"bico_worker_{task['counter']}")
    report = _make_reporter(task)
    result = {
        'counter': task['counter'],
        'bin_filedate': task['bin_filedate'],
        'status': 'ok',
        'error': None,
        'stats_row': None,
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
        dblock_headers, file_data_rows = obj.get_data()

        if task['add_instr_to_varname']:
            dblock_headers = [(f"{h[0]}_{h[2]}", h[1], h[2]) for h in dblock_headers]

        report('Building table', 0.85)
        ascii_df = format_data.make_df(data_lines=file_data_rows, header=dblock_headers, logger=logger)

        report('Saving CSV', 0.90)
        ascii_filepath = bfile.export_raw_data_ascii(
            df=ascii_df, outdir=task['dir_raw_data_ascii'], outfilename=task['ascii_filename'],
            logger=logger, compression=task['compression'],
        )

        report('Verifying', 0.93)
        file_contents_ascii_df = bfile.read_converted_ascii(ascii_filepath, task['compression'])

        # Per-file stats as a single-row frame (the main process concatenates them)
        report('Stats', 0.96)
        stats_row = bstats.calc(
            stats_df=file_contents_ascii_df.copy(), stats_coll_df=pd.DataFrame(),
            bin_filedate=task['bin_filedate'], counter_bin_files=1, logger=logger,
        )
        bfd = task['bin_filedate']
        stats_row.loc[bfd, ('_filesize', '[Bytes]', '[FILE]', 'total')] = os.path.getsize(task['bin_filepath'])
        stats_row.loc[bfd, ('_columns', '[#]', '[FILE]', 'total')] = len(file_contents_ascii_df.columns)
        stats_row.loc[bfd, ('_total_values', '[#]', '[FILE]', 'total')] = file_contents_ascii_df.size
        result['stats_row'] = stats_row

        if task['plot_ts_hires'] or task['plot_histogram_hires']:
            report('Plotting', 0.98)
        if task['plot_ts_hires']:
            vis.high_res_ts(df=file_contents_ascii_df.copy(), outfile=task['ascii_filename'],
                            outdir=task['dir_plots_hires'], logger=logger)
        if task['plot_histogram_hires']:
            vis.high_res_histogram(df=file_contents_ascii_df.copy(), outfile=task['ascii_filename'],
                                   outdir=task['dir_plots_hires'], logger=logger)
        report('Done', 1.0)
    except Exception as exc:  # isolate failures: one bad file must not kill the batch
        result['status'] = 'error'
        result['error'] = f"{exc}\n{traceback.format_exc()}"

    result['log'] = buf.getvalue()
    return result
