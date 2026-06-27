import ast
import datetime as dt
import fnmatch
import os
import random
from pathlib import Path

import pandas as pd


def search_glob_from_datetime_format(datetime_format: str) -> str:
    """Derive a filename glob from the filename datetime format.

    The datetime format (e.g. ``yyyymmddHH.CMM``) fully describes the binary
    filenames, including the extension after the dot. Replacing the datetime
    tokens with wildcards yields a glob (``*.C*``) that matches exactly those
    files, so a separate file-extension setting is not needed.
    """
    glob = datetime_format
    for token in ('yyyy', 'mm', 'dd', 'HH', 'MM'):  # 'mm'(month) before 'MM'(minute)
        glob = glob.replace(token, '*')
    while '**' in glob:  # collapse runs of wildcards
        glob = glob.replace('**', '*')
    return glob


def datetime_parsing_string(datetime_format: str) -> str:
    """Convert a filename datetime format (e.g. ``yyyymmddHH.CMM``) to a strptime
    pattern (``%Y%m%d%H.C%M``) used to parse a file's date from its name."""
    s = datetime_format
    s = s.replace('yyyy', '%Y')
    s = s.replace('mm', '%m')   # month (lowercase) before minute (uppercase)
    s = s.replace('dd', '%d')
    s = s.replace('HH', '%H')
    s = s.replace('MM', '%M')
    return s


def load_dblocks_props(dblocks_types, settings_dict):
    """Load data block settings from file(s)"""

    dblocks_filepaths = search_dblock_files(dir=Path(settings_dict['dir_script'])/'settings' / 'data_blocks',
                                            dblocks=dblocks_types)
    dblocks_props = []
    for dblock_type, dblock_filepath in dblocks_filepaths.items():
        var_info = {}
        with open(dblock_filepath) as input_file:
            for line in input_file:  # cycle through all lines in settings file
                if line.startswith('#'):
                    pass
                else:
                    if '==' in line:  # identify lines that contain setting
                        var_id, var_props = line.strip().split('==')
                        var_id = var_id.strip()
                        var_props = ast.literal_eval(var_props.strip())  # Parse as dict
                        var_info[var_id] = var_props  # store setting from file in dict
            dblocks_props.append(var_info)
    return dblocks_props


def search_dblock_files(dir, dblocks):
    found_dblock_files_dict = {}
    for dblock in dblocks:
        for root, dirs, found_files in os.walk(dir):
            for idx, file in enumerate(found_files):
                if fnmatch.fnmatch(file, f'{dblock}.dblock'):
                    filepath = Path(root) / file
                    found_dblock_files_dict[dblock] = filepath
    # found_files_dict = ops.format_data.sort_dict_by_list(dict=found_files_dict,
    #                                                      by_list=dblocks)
    return found_dblock_files_dict


class SearchAll():
    def __init__(self, settings_dict, logger):
        self.settings_dict = settings_dict
        self.logger = logger
        self.valid_files_dict = {}

    def keep_valid_files(self):
        """Search all files with file id, but then keep only those that fulfil selected requirements"""
        # The search glob is derived from the filename datetime format (which
        # already includes the extension), so no separate file-extension setting.
        file_glob = search_glob_from_datetime_format(self.settings_dict['filename_datetime_format'])
        self.valid_files_dict = self.search_all(dir=self.settings_dict['dir_source'],
                                                file_id=file_glob,
                                                logger=self.logger)
        self.valid_files_dict = self._keep_files_within_timerange()
        self.valid_files_dict = self._keep_files_with_min_filesize()
        self.valid_files_dict = self._keep_files_up_to_filelimit()
        self.valid_files_dict = self._keep_random_files(valid_files_dict=self.valid_files_dict)

        # sorted(self.valid_files_dict)  # todo sort dict necessary?

        return self.valid_files_dict

    def _keep_random_files(self, valid_files_dict):
        """Selects random items from dict"""
        num_random_files = int(self.settings_dict['select_random_files'])
        if num_random_files != 0:
            # Select random files
            suffix = "[*** RANDOM FILE SELECTION ***]"

            if num_random_files > len(valid_files_dict):
                num_random_files = int(len(valid_files_dict) / 2)
                self.logger.info(
                    f"{suffix} Reducing number of random files to {num_random_files} because "
                    f"number of selected random files was larger than number of available files "
                    f"{len(valid_files_dict)}")

            random_keys = random.sample(valid_files_dict.keys(), num_random_files)
            random_files_dict = {random_key: valid_files_dict[random_key] for random_key in random_keys}

            self.logger.info(
                f"{suffix} Selected the following {len(random_files_dict)} random files from a total of "
                f"{len(valid_files_dict)} files: {random_files_dict}")
            return random_files_dict
        else:
            # Do not select random files
            return valid_files_dict

    @staticmethod
    def search_all(dir, file_id, logger):
        """Search all files in dir that match file id"""
        logger.info(f"Searching for {file_id} files ...")
        valid_files_dict = {}
        for root, dirs, found_files in os.walk(dir):
            for idx, file in enumerate(found_files):
                if fnmatch.fnmatchcase(file, file_id):
                    filepath = Path(root) / file
                    valid_files_dict[file] = filepath
        logger.info(f"Found {len(valid_files_dict)} files matching {file_id} in {dir}")
        return valid_files_dict

    def _keep_files_within_timerange(self):
        """Check if file date is within selected time range"""
        suffix = "[FILE TIME RANGE CHECK]"
        run_start_date = dt.datetime.strptime(self.settings_dict['start_date'], '%Y-%m-%d %H:%M')
        run_end_date = dt.datetime.strptime(self.settings_dict['end_date'], '%Y-%m-%d %H:%M')
        _invalid_files_dict = {}
        valid_files_dict = {}
        for filename, filepath in self.valid_files_dict.items():
            try:
                bin_filedate = dt.datetime.strptime(filename,
                                                    self.settings_dict['filename_datetime_parsing_string'])
            except ValueError:
                # Name matched the glob but not the datetime format; skip it.
                self.logger.info(f"{suffix} (!) Skipping {filename}: name does not match the "
                                 f"datetime format, cannot read its date.")
                _invalid_files_dict[filename] = filepath
                continue
            if (bin_filedate < run_start_date) | (bin_filedate > run_end_date):
                self.logger.info(
                    f"{suffix} Date of file ({filename}, date: {bin_filedate}) is outside the selected time range"
                    f" (between {run_start_date} and {run_end_date}), skipping file.")
                _invalid_files_dict[filename] = filepath
            else:
                self.logger.info(f"{suffix} + Found file {filename} ({bin_filedate}), is within the selected time range"
                                 f" (between {run_start_date} and {run_end_date}), keeping file.")
                valid_files_dict[filename] = filepath

        self.logger.info(f"{suffix} ============================")
        self.logger.info(f"{suffix} Results of time range check:")
        self.logger.info(f"{suffix} +++ {len(valid_files_dict)} files were within the selected time range between"
                         f" {run_start_date} and {run_end_date}, keeping files: {list(valid_files_dict.keys())}")
        self.logger.info(f"{suffix} --- {len(_invalid_files_dict)} files were outside the selected time range between"
                         f" {run_start_date} and {run_end_date} and will not be used: {list(_invalid_files_dict.keys())}")
        self.logger.info(f"{suffix} ============================")
        return valid_files_dict

    def _keep_files_with_min_filesize(self):
        min_filesize_lim = int(self.settings_dict['file_size_min'])
        suffix = "[FILESIZE CHECK]"
        _invalid_files_dict = {}
        valid_files_dict = {}
        for filename, filepath in self.valid_files_dict.items():
            filesize = os.path.getsize(filepath)
            if filesize < min_filesize_lim:
                self.logger.info(f"{suffix} Filesize {filesize} of file {filename} is smaller than selected "
                                 f"limit ({min_filesize_lim}), skipping file.")
                _invalid_files_dict[filename] = filepath
            else:
                self.logger.info(f"{suffix} + Filesize {filesize} of file {filename} is larger than selected "
                                 f"limit ({min_filesize_lim}), keeping file.")
                valid_files_dict[filename] = filepath
        self.logger.info(f"{suffix} ============================")
        self.logger.info(f"{suffix} Results of filesize check:")
        self.logger.info(f"{suffix} +++ {len(valid_files_dict)} files were larger than the selected minimum"
                         f" filesize of {min_filesize_lim}, keeping files: {list(valid_files_dict.keys())}")
        self.logger.info(f"{suffix} --- {len(_invalid_files_dict)} files were smaller than the selected minimum"

                         f" filesize of {min_filesize_lim} and will not be used: {list(_invalid_files_dict.keys())}")
        self.logger.info(f"{suffix} ============================")
        return valid_files_dict

    def _keep_files_up_to_filelimit(self):
        file_limit = int(self.settings_dict['file_limit'])
        suffix = "[FILE LIMIT CHECK]"
        _invalid_files_dict = {}
        valid_files_dict = {}
        filecounter = 0

        for filename, filepath in self.valid_files_dict.items():
            filecounter += 1
            if (filecounter <= file_limit) | (file_limit == 0):
                self.logger.info(f"{suffix} + Keeping file #{filecounter} of max {filecounter} files: {filename}")
                valid_files_dict[filename] = filepath
            else:
                self.logger.info(
                    f"{suffix} Max number of files ({file_limit}) reached, file {filename} will not be used")
                _invalid_files_dict[filename] = filepath

        self.logger.info(f"{suffix} ============================")
        self.logger.info(f"{suffix} Results of file limit check:")
        self.logger.info(f"{suffix} +++ {len(valid_files_dict)} files will be used: {list(valid_files_dict.keys())}")
        self.logger.info(f"{suffix} --- {len(_invalid_files_dict)} files will not be used because the"
                         f" max number of files ({file_limit}) was already reached, files not used:"
                         f" {list(_invalid_files_dict.keys())}")
        self.logger.info(f"{suffix} ============================")
        return valid_files_dict


def export_raw_data_ascii(df, outdir, logger, outfilename='temp', compression='gzip'):
    logger.info("    Saving raw data csv ...")

    if compression == 'gzip':
        outfilename_ext = '.csv.gz'
        compression = 'gzip'

    elif compression == 'None':
        outfilename_ext = '.csv'
        compression = None

    else:
        outfilename_ext = '.csv'
        compression = None

    outfilename_ext = outfilename + outfilename_ext
    outpath = outdir / outfilename_ext
    df.to_csv(f"{outpath}", index=False, compression=compression)
    return outpath


def export_stats_collection_csv(df, outdir, run_id, logger):
    outpath = outdir / f"stats_agg_{run_id}"
    logger.info(f"Saving stats collection to {outpath}")
    df.to_csv(f"{outpath}.csv", index=True)


# Canonical settings filename, written and read in lowercase. A run also drops a
# copy of this name into each output folder as a provenance snapshot.
SETTINGS_FILENAME = 'bico.settings'


def find_settings_file(directory):
    """Return the path of the settings file in `directory`, or None if absent.

    Matches `bico.settings` case-insensitively so folders written by older
    versions (`BICO.settings`) still load. The lowercase name wins if both exist.
    """
    directory = Path(directory)
    if not directory.is_dir():
        return None
    target = SETTINGS_FILENAME.lower()
    match = None
    for name in os.listdir(directory):
        if name.lower() == target:
            path = directory / name
            if name == SETTINGS_FILENAME:  # exact lowercase match takes priority
                return path
            match = path
    return match


# Settings that are derived/computed at runtime. They must never be written back
# into the user's bico.settings file: doing so pollutes it with per-run values
# (run_id) and machine-specific absolute paths (dir_script, dir_out_run, ...).
DERIVED_SETTING_KEYS = {
    'run_id', 'filename_datetime_parsing_string',
    'dir_bico', 'dir_script', 'dir_settings', 'dir_root',
    'dir_out_run', 'dir_out_run_log', 'dir_out_run_plots',
    'dir_out_run_plots_hires', 'dir_out_run_plots_agg', 'dir_out_run_raw_data_ascii',
}


def _write_settings_from_template(template_path, dest_path, settings_dict):
    """Render a bico.settings file by substituting values into a template.

    Each setting line in `template_path` gets its value replaced from
    `settings_dict`; comments and section headers are preserved verbatim, and
    DERIVED_SETTING_KEYS are dropped so the result never carries per-run values
    or machine-specific paths. Written atomically (temp file + os.replace).
    """
    template_path = Path(template_path)
    dest_path = Path(dest_path)
    tmp_path = dest_path.with_name(f'{dest_path.name}Temp')
    with open(template_path) as infile, open(tmp_path, 'w') as outfile:
        for line in infile:  # cycle through all lines in settings file
            if ('=' in line) and (not line.startswith('#')):  # identify lines that contain a setting
                line_id = line.split('=', 1)[0].strip()
                if line_id in DERIVED_SETTING_KEYS:
                    continue  # never persist derived/runtime keys
                if line_id in settings_dict:
                    line = f"{line_id}={settings_dict[line_id]}\n"  # insert current value from dict
            outfile.write(line)
    os.replace(tmp_path, dest_path)  # atomic replace, no .settingsOld churn


def save_settings_to_file(settings_dict):
    """Persist user settings back to the source bico.settings file.

    Only user-configurable settings are written; keys in DERIVED_SETTING_KEYS are
    skipped (and dropped if an older file still contains them) so the file is not
    polluted with per-run values or machine-specific paths. Comments and section
    headers in the existing file are preserved. The file is replaced atomically.
    """
    settings_path = Path(settings_dict['dir_settings']) / SETTINGS_FILENAME
    # The existing file is its own template, so its layout is preserved in place.
    _write_settings_from_template(settings_path, settings_path, settings_dict)


def export_settings_to_folder(settings_dict, dest_dir, template_path):
    """Write a bico.settings into `dest_dir` for a headless run there.

    Renders from `template_path` (an existing bico.settings whose comments and
    layout are kept) with the current values from `settings_dict`. Returns the
    written path. Used by the TUI's "Export" so settings edited on screen can be
    dropped into a headless run folder.
    """
    dest_path = Path(dest_dir) / SETTINGS_FILENAME
    _write_settings_from_template(template_path, dest_path, settings_dict)
    return dest_path


def write_run_settings_snapshot(settings_dict, outdir):
    """Write the full effective settings of a run to its output folder.

    This is a provenance record of exactly what was run (it intentionally includes
    derived keys). It is written only into the run output folder; the source
    bico.settings file is never modified by a run.
    """
    snapshot_path = Path(outdir) / SETTINGS_FILENAME
    with open(snapshot_path, 'w') as outfile:
        for key, val in settings_dict.items():
            outfile.write(f"{key}={val}\n")
    return snapshot_path


def read_converted_ascii(filepath, compression):
    """Read converted file"""
    compression = None if compression == 'None' else compression
    file_contents_ascii_df = pd.read_csv(filepath,
                                         skiprows=None,
                                         header=[0, 1, 2],
                                         na_values=-9999,
                                         encoding='utf-8',
                                         delimiter=',',
                                         # keep_date_col=True,
                                         parse_dates=False,
                                         index_col=None,
                                         dtype=None,
                                         compression=compression)
    return file_contents_ascii_df
