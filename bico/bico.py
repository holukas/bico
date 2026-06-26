import datetime as dt
import multiprocessing
import os
import queue as _queue
import sys
from concurrent.futures import ProcessPoolExecutor, FIRST_COMPLETED, wait
from pathlib import Path

import pandas as pd

from bico.ops import bin, vis, file, cli, parallel
from bico.ops import logger as ops_logger, setup as ops_setup, log_report
from bico.settings import _version
from bico.settings.model import UserSettings, RunContext


class BicoEngine:

    def __init__(
            self,
            settings_dict: dict,
            usedgui: bool,
            avoidduplicates: bool = False,
            progress_callback=None,
            file_progress_callback=None,
            should_stop=None
    ):

        self.settings_dict = settings_dict
        # Typed snapshot of the user-configurable settings. Built here so both the
        # headless (BicoFolder) and TUI entry points get it, since both construct
        # BicoEngine. Nothing consumes it yet — call sites still read settings_dict
        # — but it is parsed in the live run path, ready for incremental migration.
        self.settings = UserSettings.from_raw(settings_dict)
        self.usedgui = usedgui
        self.avoidduplicates = avoidduplicates
        # Optional callable() -> bool. When it returns True the run stops as soon
        # as possible: no further files are started (the in-progress file, if any,
        # finishes), then the run winds down normally. None means never stop.
        self.should_stop = should_stop
        # Optional callable(done, total) invoked as each file finishes converting,
        # so a UI can show progress / estimated remaining time.
        self.progress_callback = progress_callback
        # Optional callable(idx, total, filename, step, fraction) invoked while a
        # file is converting, so a UI can show which file is in progress, the
        # current step, and a per-file percentage.
        self.file_progress_callback = file_progress_callback

        # Setup outdirs, run ID and logger. RunContext is the single source of
        # truth for this run's derived paths and strptime pattern; its values are
        # mirrored back onto settings_dict for the consumers that still read the
        # dict (file.SearchAll, the logger, the settings snapshot).
        self.run_id = ops_setup.generate_run_id()
        self.settings_dict['run_id'] = self.run_id
        self.run_context = RunContext.create(self.settings, self.run_id)
        self.run_context.make_dirs()
        self._mirror_run_context()
        self.logger = ops_logger.setup_logger(settings_dict=self.settings_dict)

        self.stats_coll_df = pd.DataFrame()  # Collects agg stats
        self.dblocks_seq = []

        # self.run()

    def run(self):

        # Write a snapshot of this run's effective settings to its output folder
        # (the source bico.settings file is never modified by a run)
        file.write_run_settings_snapshot(self.settings_dict, self.run_context.dir_out_run)

        # Log info
        self.logger.info(f"Run ID: {self.run_id}")
        self.logger.info(f"BICO Version: {_version.__version__} / {_version.__date__}")

        # Show settings in log
        self.logger.info("Contents of settings dictionary:")
        for key, val in self.settings_dict.items():
            self.logger.info(f"    {key}: {val}")

        # The strptime pattern (run_context) is already mirrored onto settings_dict
        # in __init__, so file.SearchAll and _build_tasks can read it from the dict.

        # Settings for file header
        self.bin_size_header = self.settings.header_size

        # Load settings for datablocks: their types, sequence and properties
        self.dblocks_seq = self.settings.instruments
        self.dblocks_props = file.load_dblocks_props(dblocks_types=self.dblocks_seq,
                                                     settings_dict=self.settings_dict)  # Load data block settings

        # Search valid source binary files, depending on settings
        bin_found_files_dict = file.SearchAll(settings_dict=self.settings_dict,
                                              logger=self.logger).keep_valid_files()

        # List all files (filenames only) already in dir_out (the base output dir,
        # not the run dir). This info is later used to avoid converting a binary file
        # that is already somewhere in dir_out (optional), i.e. to avoid duplicates.
        if self.avoidduplicates:
            availablefiles = file.SearchAll.search_all(dir=self.settings_dict['dir_out'], file_id='*',
                                                       logger=self.logger)
            availablefiles = list(availablefiles.keys())
            # availablefiles = [f.stem for f in availablefiles]
        else:
            availablefiles = False

        # Plot availability heatmap
        if self.settings.plot_file_availability:
            vis.availability_heatmap(bin_found_files_dict=bin_found_files_dict,
                                     bin_file_datefrmt=self.run_context.datetime_parsing_string,
                                     root_outdir=self.run_context.dir_out_run_plots,
                                     logger=self.logger)

        # Loop through binary files
        stats_coll_df = self.loop(bin_found_files_dict=bin_found_files_dict,
                                  dblocks_props=self.dblocks_props,
                                  stats_coll_df=self.stats_coll_df,
                                  logger=self.logger,
                                  availablefiles=availablefiles)
        self._log_fileloopfinish()

        if not stats_coll_df.empty:
            # Stats collection export
            file.export_stats_collection_csv(df=stats_coll_df, outdir=self.run_context.dir_out_run_plots_agg,
                                             run_id=self.run_id, logger=self.logger)

            # Plot aggregated stats collection from files
            if self.settings.plot_ts_agg:
                self._plot_stats_collection_agg()
        else:
            self.logger.info("(!) Aggregated plots not generated because aggregated stats are empty.")
            self.logger.info(f"    This can happen if CLI flag `-a` to avoid"
                             f" duplicates in {self.settings_dict['dir_out']} is set and ")
            self.logger.info(f"    *all* files that should be converted in this run")
            self.logger.info(f"    are already available in {self.settings_dict['dir_out']}")

        self._log_bicofinish()
        self._write_log_html_viewer()

    def _write_log_html_viewer(self):
        """Render an HTML viewer for this run's log file, next to the .log.

        Done once at the very end (not during logging) so it never slows the run.
        Any failure here is non-fatal — the plain .log is the source of truth.
        """
        try:
            logfile = self.run_context.dir_out_run_log / f"{self.run_id}.log"
            html_path = logfile.parent / f"{logfile.name}.html"
            self.logger.info("")
            self.logger.info(f"Saving HTML log viewer to {html_path}")
            # Flush so the .log contains everything (incl. the line above) before
            # we read it back to embed in the HTML.
            for handler in self.logger.handlers:
                try:
                    handler.flush()
                except Exception:
                    pass
            log_report.write_log_html(logfile, html_path)
        except Exception as exc:
            self.logger.info(f"(!) Could not build HTML log viewer: {exc}")

    def _log_fileloopfinish(self):
        """Log that file loop finished"""
        self.logger.info("")
        self.logger.info("=" * 20)
        self.logger.info(f"File loop finished.")
        self.logger.info("=" * 20)
        self.logger.info("")

    def _log_bicofinish(self):
        """Log that BICO finished"""
        self.logger.info("")
        self.logger.info("")
        self.logger.info("")
        self.logger.info("=" * 20)
        self.logger.info(f"[{self.run_id}] BICO FINISHED.")
        self.logger.info("=" * 20)

    def _plot_stats_collection_agg(self):
        """Plot aggregated data"""

        # Search for stats files
        bin_found_files_dict = file.SearchAll.search_all(
            dir=self.run_context.dir_out_run_plots_agg,
            file_id='stats_*.csv',
            logger=self.logger
        )

        # Read stats files
        for fid, filepath in bin_found_files_dict.items():
            df = pd.read_csv(
                filepath,
                skiprows=None,
                header=[0, 1, 2, 3],
                na_values=-9999,
                encoding='utf-8',
                delimiter=',',
                parse_dates=True,
                index_col=0,
                dtype=None
            )

            # Generate plots for aggregated data
            vis.aggs_ts(df=df, outdir=self.run_context.dir_out_run_plots_agg, logger=self.logger)

    def loop(self, bin_found_files_dict, dblocks_props, stats_coll_df, logger, availablefiles: list):
        """Process files, converting independent files concurrently across processes."""
        logger.info("Processing files ...")
        num_bin_files = len(bin_found_files_dict)

        # Get header for all data blocks
        logger.info("Found variables:")
        _idx = 0
        for _dblock in dblocks_props:
            _dblock_header = bin.make_header(dblock=_dblock)
            for _dblock_var in _dblock_header:
                _idx += 1
                logger.info(f"    #{_idx}    {_dblock_var[0]} {_dblock_var[1]} {_dblock_var[2]}")

        # Build the list of files to convert (file-limit and duplicate checks happen here)
        tasks = self._build_tasks(bin_found_files_dict, availablefiles, logger)
        if not tasks:
            return stats_coll_df

        # Convert files: in parallel across processes, or sequentially for a single file/worker.
        # Results are kept in task order, but progress is reported as each file *finishes*
        # (via as_completed) so a UI can show a live count / estimated remaining time.
        n_workers = self._n_workers(len(tasks))
        total = len(tasks)
        for i, task in enumerate(tasks):
            task['task_index'] = i + 1  # 1-based, for the live progress display
        logger.info("")
        logger.info(f"Converting {total} file(s) of {num_bin_files} found, using {n_workers} process(es) ...")
        self._report_progress(0, total)

        # Each file's captured log is replayed (and its stats collected) as soon as
        # that file finishes, so the console shows progress live instead of dumping
        # everything at the end. With several workers this is completion order.
        stats_rows = []
        done = 0
        if n_workers == 1:
            for task in tasks:
                if self._stop_requested():
                    self._log_stopped(logger, done, total)
                    break
                task['progress_cb'] = self._make_seq_progress_cb(task, total)
                result = parallel.process_file(task)
                done += 1
                self._consume_result(task, result, logger, stats_rows)
                self._report_progress(done, total)
        else:
            done = self._run_pool(tasks, n_workers, total, logger, stats_rows)

        if stats_rows:
            stats_coll_df = pd.concat([stats_coll_df] + stats_rows) if not stats_coll_df.empty \
                else pd.concat(stats_rows)
        return stats_coll_df

    def _run_pool(self, tasks, n_workers, total, logger, stats_rows):
        """Convert files across a process pool, draining live progress events and
        replaying each file's log as it completes."""
        # Workers report live progress through a picklable manager queue (only set
        # up when a UI asked for per-file progress, to avoid the manager overhead).
        manager = progress_queue = None
        if self.file_progress_callback is not None:
            manager = multiprocessing.Manager()
            progress_queue = manager.Queue()
            for task in tasks:
                task['progress_queue'] = progress_queue
        done = 0
        try:
            with ProcessPoolExecutor(max_workers=n_workers) as executor:
                future_to_index = {executor.submit(parallel.process_file, task): i
                                   for i, task in enumerate(tasks)}
                remaining = set(future_to_index)
                stopped = False
                while remaining:
                    if not stopped and self._stop_requested():
                        # Cancel files that haven't started; running ones finish.
                        for future in remaining:
                            future.cancel()
                        self._log_stopped(logger, done, total)
                        stopped = True
                    completed, remaining = wait(remaining, timeout=0.15,
                                                return_when=FIRST_COMPLETED)
                    self._drain_progress_queue(progress_queue, total)
                    for future in completed:
                        if future.cancelled():
                            continue
                        i = future_to_index[future]
                        result = future.result()
                        done += 1
                        self._consume_result(tasks[i], result, logger, stats_rows)
                        self._report_progress(done, total)
                self._drain_progress_queue(progress_queue, total)
        finally:
            if manager is not None:
                manager.shutdown()
        return done

    def _consume_result(self, task, result, logger, stats_rows):
        """Replay one file's captured log and collect its stats (or note an error)."""
        banner = f"[{task['bin_file']}]"
        logger.info("")
        logger.info("")
        logger.info(banner)
        logger.info("=" * len(banner))
        self._replay_log(logger, result['log'])
        if result['status'] == 'error':
            logger.info(f"(!) ERROR converting {task['bin_file']}, file skipped: {result['error']}")
            return
        if result['stats_row'] is not None:
            stats_rows.append(result['stats_row'])

    def _make_seq_progress_cb(self, task, total):
        """A (step, fraction) callback for the sequential path that forwards to the
        engine's file-progress callback."""
        idx = task['task_index']
        bin_file = task['bin_file']
        return lambda step, frac: self._emit_file_progress(idx, total, bin_file, step, frac)

    def _drain_progress_queue(self, progress_queue, total):
        """Forward any queued worker progress events to the file-progress callback."""
        if progress_queue is None:
            return
        while True:
            try:
                ev = progress_queue.get_nowait()
            except _queue.Empty:
                break
            self._emit_file_progress(ev['idx'], total, ev['file'], ev['step'], ev['frac'])

    def _stop_requested(self):
        """True if the caller asked to stop the run (never raises)."""
        if self.should_stop is None:
            return False
        try:
            return bool(self.should_stop())
        except Exception:
            return False

    def _log_stopped(self, logger, done, total):
        """Note in the log that the run is stopping at the user's request."""
        logger.info("")
        logger.info(f"(!) Stop requested — stopping after {done} of {total} file(s). "
                    f"A file already converting will finish; no new files are started.")

    def _emit_file_progress(self, idx, total, filename, step, frac):
        """Notify the optional file-progress callback; never let UI errors break a run."""
        if self.file_progress_callback is None:
            return
        try:
            self.file_progress_callback(idx, total, filename, step, max(0.0, min(1.0, frac)))
        except Exception:
            pass

    def _build_tasks(self, bin_found_files_dict, availablefiles, logger):
        """Build picklable per-file work descriptions, applying file-limit and duplicate checks."""
        tasks = []
        file_limit = self.settings.file_limit
        counter_bin_files = 0
        for bin_file, bin_filepath in bin_found_files_dict.items():
            counter_bin_files += 1
            if (counter_bin_files > 1) and (file_limit > 0) and (counter_bin_files > file_limit):
                logger.info(f"File limit ({file_limit}) reached, ignoring other files.")
                break

            bin_filedate = dt.datetime.strptime(bin_filepath.name,
                                                self.run_context.datetime_parsing_string)
            ascii_filename = f"{self.settings.site}_{bin_filedate.strftime('%Y%m%d%H%M')}"

            if availablefiles and any(ascii_filename in f for f in availablefiles):
                logger.info(f"[{bin_file}] [DUPLICATE CHECK] (!) Skipping, converted file already available in "
                            f"{self.settings_dict['dir_out']}")
                continue

            s = self.settings
            ctx = self.run_context
            tasks.append({
                'counter': counter_bin_files,
                'bin_file': bin_file,
                'bin_filepath': bin_filepath,
                'bin_filedate': bin_filedate,
                'ascii_filename': ascii_filename,
                'size_header': self.bin_size_header,
                'dblocks_props': self.dblocks_props,
                'row_limit': s.row_limit,
                'add_instr_to_varname': s.add_instr_to_varname,
                'compression': s.file_compression,
                'dir_raw_data_ascii': ctx.dir_out_run_raw_data_ascii,
                'dir_plots_hires': ctx.dir_out_run_plots_hires,
                'plot_ts_hires': s.plot_ts_hires,
                'plot_histogram_hires': s.plot_histogram_hires,
            })
        return tasks

    def _n_workers(self, num_tasks):
        """Number of worker processes: optional 'num_processes' setting, else (cpu_count - 1)."""
        n = self.settings.num_processes  # already an int; 0 when unset/invalid
        if n <= 0:
            n = max(1, (os.cpu_count() or 2) - 1)
        return max(1, min(n, num_tasks))

    def _report_progress(self, done, total):
        """Notify an optional progress callback; never let UI errors break a run."""
        if self.progress_callback is None:
            return
        try:
            self.progress_callback(done, total)
        except Exception:
            pass

    @staticmethod
    def _replay_log(logger, text):
        """Write a worker's already-formatted captured log verbatim to the real log destinations."""
        if not text:
            return
        for handler in logger.handlers:
            stream = getattr(handler, 'stream', None)
            if stream is None:
                continue
            handler.acquire()
            try:
                stream.write(text)
                handler.flush()
            finally:
                handler.release()

    def _mirror_run_context(self):
        """Copy the RunContext's derived values onto settings_dict.

        The engine itself reads ``self.run_context`` directly, but several
        consumers still take the raw dict: ``file.SearchAll`` (the strptime
        pattern), the logger (``run_id`` / log dir), and the run snapshot (which
        records every derived key as a provenance record). This shim keeps them
        working without threading the context through each one.
        """
        ctx = self.run_context
        self.settings_dict.update({
            'filename_datetime_parsing_string': ctx.datetime_parsing_string,
            'dir_out_run': ctx.dir_out_run,
            'dir_out_run_log': ctx.dir_out_run_log,
            'dir_out_run_plots': ctx.dir_out_run_plots,
            'dir_out_run_plots_hires': ctx.dir_out_run_plots_hires,
            'dir_out_run_plots_agg': ctx.dir_out_run_plots_agg,
            'dir_out_run_raw_data_ascii': ctx.dir_out_run_raw_data_ascii,
        })


class BicoFolder:
    """
    Run BICO in specified folder without GUI

    This starts BicoEngine.
    """

    def __init__(self, folder: str, days: int = None, avoidduplicates: bool = False):
        self.folder = Path(folder)
        self.days = days
        self.avoidduplicates = avoidduplicates

        self.settings_dict = {}

    def _update_settings_from_args(self, settings_dict: dict) -> dict:
        """Update settings according to given args"""
        if self.days:
            settings_dict = self._days_from_arg(settings_dict=settings_dict)
        return settings_dict

    def _days_from_arg(self, settings_dict: dict) -> dict:
        """Set new start and end date according to DAYS arg"""
        # Get current time, subtract number of days
        _currentdate = dt.datetime.now().date()
        _newstartdate = _currentdate - dt.timedelta(days=self.days)

        # Define new start date
        _newstartdatetime = dt.datetime(year=_newstartdate.year, month=_newstartdate.month,
                                        day=_newstartdate.day, hour=0, minute=0)
        _newstartdatetime = _newstartdatetime.strftime('%Y-%m-%d %H:%M')  # As string

        # Define new end date (now)
        _newenddatetime = dt.datetime.now()
        _newenddatetime = _newenddatetime.strftime('%Y-%m-%d %H:%M')

        # Update dict
        settings_dict['start_date'] = _newstartdatetime
        settings_dict['end_date'] = _newenddatetime

        return settings_dict

    def run(self):
        settings_file = file.find_settings_file(self.folder)

        if not settings_file:
            print(f"(!)ERROR: No 'bico.settings' file found. Please make sure it is in folder '{self.folder}'")
            sys.exit()

        # Read Settings: File --> Dict
        self.settings_dict = \
            ops_setup.read_settings_file_to_dict(dir_settings=self.folder,
                                                 file=settings_file.name,
                                                 reset_paths=False)

        # Update folder settings
        dir_script = os.path.abspath(__file__)  # Dir of this file
        self.settings_dict['dir_script'] = os.path.join(os.path.dirname(dir_script))
        self.settings_dict['dir_settings'] = Path(self.folder)
        self.settings_dict['dir_bico'] = Path(self.settings_dict['dir_script']).parents[0]
        self.settings_dict['dir_root'] = Path(self.settings_dict['dir_script']).parents[1]

        self.settings_dict = self._update_settings_from_args(settings_dict=self.settings_dict)

        self.execute_in_folder()

    def execute_in_folder(self):
        bicoengine = BicoEngine(settings_dict=self.settings_dict,
                                usedgui=False,
                                avoidduplicates=self.avoidduplicates)
        bicoengine.run()


def main(args):
    # Run BICO headless in a folder
    if args.folder:
        days = args.days if args.days else None
        bicofromfolder = BicoFolder(folder=args.folder, days=days, avoidduplicates=args.avoidduplicates)
        bicofromfolder.run()

    # Run BICO with the terminal UI (explicitly via -t, or by default when no FOLDER given)
    else:
        from bico.tui.app import run_tui  # imported lazily so headless runs never need Textual
        run_tui()


def main_cli():
    """Console-script entry point (``bico`` / ``python -m bico``)."""
    multiprocessing.freeze_support()  # required for process pool in a PyInstaller-frozen build
    args = cli.validate_args(cli.get_args())
    main(args)


if __name__ == '__main__':
    main_cli()

# # Compress uncompressed ASCII to gzip, delete uncompressed if gzip selected
# if self.settings_dict['file_compression'] == 'gzip':
#     with open(ascii_filepath, 'rb') as f_in, gzip.open(ascii_filepath_gzip, 'wb') as f_out:
#         f_out.writelines(f_in)
#     os.remove(ascii_filepath)  # Delete uncompressed
