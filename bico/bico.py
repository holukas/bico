import datetime as dt
import multiprocessing
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

from bico.ops import bin, vis, file, cli, parallel
from bico.ops import logger as ops_logger, setup as ops_setup
from bico.settings import _version


class BicoEngine:

    def __init__(
            self,
            settings_dict: dict,
            usedgui: bool,
            avoidduplicates: bool = False,
            progress_callback=None
    ):

        self.settings_dict = settings_dict
        self.usedgui = usedgui
        self.avoidduplicates = avoidduplicates
        # Optional callable(done, total) invoked as each file finishes converting,
        # so a UI can show progress / estimated remaining time.
        self.progress_callback = progress_callback

        # Setup outdirs, run ID and logger
        self.run_id = ops_setup.generate_run_id()
        self.settings_dict['run_id'] = self.run_id
        self.settings_dict = ops_setup.make_run_outdirs(settings_dict=self.settings_dict)
        self.logger = ops_logger.setup_logger(settings_dict=self.settings_dict)

        self.stats_coll_df = pd.DataFrame()  # Collects agg stats
        self.dblocks_seq = []

        # self.run()

    def run(self):

        # Write a snapshot of this run's effective settings to its output folder
        # (the source bico.settings file is never modified by a run)
        file.write_run_settings_snapshot(self.settings_dict, self.settings_dict['dir_out_run'])

        # Log info
        self.logger.info(f"Run ID: {self.run_id}")
        self.logger.info(f"BICO Version: {_version.__version__} / {_version.__date__}")

        # Show settings in log
        self.logger.info("Contents of settings dictionary:")
        for key, val in self.settings_dict.items():
            self.logger.info(f"    {key}: {val}")

        # Format string to parse datetime info from filename
        self.settings_dict['filename_datetime_parsing_string'] = self.make_datetime_parsing_string()

        # Settings for file header
        self.bin_size_header = 29 if self.settings_dict['header'] == 'WECOM3' else 38  # todo better solution

        # Load settings for datablocks: their types, sequence and properties
        self.dblocks_seq = self.assemble_datablock_sequence()
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
        if self.settings_dict['plot_file_availability'] == '1':
            vis.availability_heatmap(bin_found_files_dict=bin_found_files_dict,
                                     bin_file_datefrmt=self.settings_dict['filename_datetime_parsing_string'],
                                     root_outdir=self.settings_dict['dir_out_run_plots'],
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
            file.export_stats_collection_csv(df=stats_coll_df, outdir=self.settings_dict['dir_out_run_plots_agg'],
                                             run_id=self.run_id, logger=self.logger)

            # Plot aggregated stats collection from files
            if self.settings_dict['plot_ts_agg'] == '1':
                self._plot_stats_collection_agg()
        else:
            self.logger.info("(!) Aggregated plots not generated because aggregated stats are empty.")
            self.logger.info(f"    This can happen if CLI flag `-a` to avoid"
                             f" duplicates in {self.settings_dict['dir_out']} is set and ")
            self.logger.info(f"    *all* files that should be converted in this run")
            self.logger.info(f"    are already available in {self.settings_dict['dir_out']}")

        self._log_bicofinish()

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
            dir=self.settings_dict['dir_out_run_plots_agg'],
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
            vis.aggs_ts(df=df, outdir=self.settings_dict['dir_out_run_plots_agg'], logger=self.logger)

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
        logger.info("")
        logger.info(f"Converting {total} file(s) of {num_bin_files} found, using {n_workers} process(es) ...")
        self._report_progress(0, total)
        results = [None] * total
        done = 0
        if n_workers == 1:
            for i, task in enumerate(tasks):
                results[i] = parallel.process_file(task)
                done += 1
                self._report_progress(done, total)
        else:
            with ProcessPoolExecutor(max_workers=n_workers) as executor:
                future_to_index = {executor.submit(parallel.process_file, task): i
                                   for i, task in enumerate(tasks)}
                for future in as_completed(future_to_index):
                    results[future_to_index[future]] = future.result()
                    done += 1
                    self._report_progress(done, total)

        # Replay each file's captured log (in file order) and collect per-file stats
        stats_rows = []
        for task, result in zip(tasks, results):
            banner = f"[{task['bin_file']}]"
            logger.info("")
            logger.info("")
            logger.info(banner)
            logger.info("=" * len(banner))
            self._replay_log(logger, result['log'])
            if result['status'] == 'error':
                logger.info(f"(!) ERROR converting {task['bin_file']}, file skipped: {result['error']}")
                continue
            if result['stats_row'] is not None:
                stats_rows.append(result['stats_row'])

        if stats_rows:
            stats_coll_df = pd.concat([stats_coll_df] + stats_rows) if not stats_coll_df.empty \
                else pd.concat(stats_rows)
        return stats_coll_df

    def _build_tasks(self, bin_found_files_dict, availablefiles, logger):
        """Build picklable per-file work descriptions, applying file-limit and duplicate checks."""
        tasks = []
        file_limit = int(self.settings_dict['file_limit'])
        counter_bin_files = 0
        for bin_file, bin_filepath in bin_found_files_dict.items():
            counter_bin_files += 1
            if (counter_bin_files > 1) and (file_limit > 0) and (counter_bin_files > file_limit):
                logger.info(f"File limit ({file_limit}) reached, ignoring other files.")
                break

            bin_filedate = dt.datetime.strptime(bin_filepath.name,
                                                self.settings_dict['filename_datetime_parsing_string'])
            ascii_filename = f"{self.settings_dict['site']}_{bin_filedate.strftime('%Y%m%d%H%M')}"

            if availablefiles and any(ascii_filename in f for f in availablefiles):
                logger.info(f"[{bin_file}] [DUPLICATE CHECK] (!) Skipping, converted file already available in "
                            f"{self.settings_dict['dir_out']}")
                continue

            sd = self.settings_dict
            tasks.append({
                'counter': counter_bin_files,
                'bin_file': bin_file,
                'bin_filepath': bin_filepath,
                'bin_filedate': bin_filedate,
                'ascii_filename': ascii_filename,
                'size_header': self.bin_size_header,
                'dblocks_props': self.dblocks_props,
                'row_limit': int(sd['row_limit']),
                'add_instr_to_varname': sd['add_instr_to_varname'] == '1',
                'compression': sd['file_compression'],
                'dir_raw_data_ascii': sd['dir_out_run_raw_data_ascii'],
                'dir_plots_hires': sd['dir_out_run_plots_hires'],
                'plot_ts_hires': sd['plot_ts_hires'] == '1',
                'plot_histogram_hires': sd['plot_histogram_hires'] == '1',
            })
        return tasks

    def _n_workers(self, num_tasks):
        """Number of worker processes: optional 'num_processes' setting, else (cpu_count - 1)."""
        configured = self.settings_dict.get('num_processes')
        try:
            n = int(configured)
        except (TypeError, ValueError):
            n = 0
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

    def make_datetime_parsing_string(self):
        return file.datetime_parsing_string(self.settings_dict['filename_datetime_format'])

    def assemble_datablock_sequence(self):
        dblocks_seq = []
        instrument_settings = ['instrument_1', 'instrument_2', 'instrument_3']
        for key, val in self.settings_dict.items():
            if key in instrument_settings:
                dblocks_seq.append(val)
        return dblocks_seq


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
