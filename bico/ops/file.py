import ast
import datetime as dt
import fnmatch
import os
import random
from pathlib import Path


def load_dblocks_props(dblocks_types, settings_dict):
    """Load data block settings from file(s)"""

    dblocks_filepaths = search_dblock_files(dir=settings_dict['dir_settings'] / 'data_blocks',
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
        self.valid_files_dict = self.search_all(dir=self.settings_dict['dir_source'],
                                                file_id=self.settings_dict['file_ext'],
                                                logger=self.logger)
        self.valid_files_dict = self.keep_files_within_timerange()
        self.valid_files_dict = self.keep_files_with_min_filesize()
        self.valid_files_dict = self.keep_files_up_to_filelimit()
        self.valid_files_dict = self.keep_random_files(valid_files_dict=self.valid_files_dict)

        return self.valid_files_dict

    def keep_random_files(self, valid_files_dict):
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
        valid_files_dict = {}
        for root, dirs, found_files in os.walk(dir):
            for idx, file in enumerate(found_files):
                if fnmatch.fnmatch(file, file_id):
                    filepath = Path(root) / file
                    valid_files_dict[file] = filepath
        logger.info(f"Found {len(valid_files_dict)} files matching {file_id} in {dir}")
        return valid_files_dict

    def keep_files_within_timerange(self):
        """Check if file date is within selected time range"""
        suffix = "[FILE TIME RANGE CHECK]"
        run_start_date = dt.datetime.strptime(self.settings_dict['start_date'], '%Y-%m-%d %H:%M')
        run_end_date = dt.datetime.strptime(self.settings_dict['end_date'], '%Y-%m-%d %H:%M')
        _invalid_files_dict = {}
        valid_files_dict = {}
        for filename, filepath in self.valid_files_dict.items():
            bin_filedate = dt.datetime.strptime(filename,
                                                self.settings_dict['filename_datetime_parsing_string'])
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

    def keep_files_with_min_filesize(self):
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

    def keep_files_up_to_filelimit(self):
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


def export_raw_data_csv(df, outdir, logger, outfile='temp', compression='gzip'):
    logger.info("    Saving raw data csv ...")
    outpath = outdir / outfile
    if compression == 'gzip':
        df.to_csv(f"{outpath}.csv.gz", index=False, compression='gzip')
    elif compression == 'None':
        df.to_csv(f"{outpath}.csv", index=False)


def export_stats_collection_csv(df, outdir, run_id, logger):
    # outpath = outdir / f"stats_"
    outpath = outdir / f"stats_{run_id}"  # TODO act run_id
    logger.info(f"Saving stats collection to {outpath}")
    df.to_csv(f"{outpath}.csv", index=True)
