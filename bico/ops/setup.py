import os
import time
from pathlib import Path


def read_settings_file_to_dict(dir_settings, file, reset_paths):
    """Read start values from settings file as strings into dict, with same variable names as in file"""

    settings_dict = {}
    settings_file_fullpath = os.path.join(dir_settings, file)

    with open(settings_file_fullpath) as input_file:
        for line in input_file:  # cycle through all lines in settings file
            if ('=' in line) and (not line.startswith('#')):  # identify lines that contain setting
                line_id, line_setting = line.strip().split('=')

                # reset all file paths, folder paths and instr info, will be filled during run
                if reset_paths:
                    if line_id.startswith('f_') or line_id.startswith('dir_') or line_id.startswith('instr_'):
                        line_setting = ''

                settings_dict[line_id] = line_setting  # store setting from file in dict

    return settings_dict


def make_run_outdirs(settings_dict):
    """Set output paths and create output folders"""

    # Run output folder
    # settings_dict['dir_out_run'] = Path(settings_dict['dir_out']) / "BICO_TEST_OUT"
    folder_name = settings_dict['output_folder_name_prefix'] + "_" + settings_dict['run_id']  # todo act
    settings_dict['dir_out_run'] = Path(settings_dict['dir_out']) / folder_name  # todo act
    if not Path.is_dir(settings_dict['dir_out_run']):
        print(f"Creating folder {settings_dict['dir_out_run']} ...")
        os.makedirs(settings_dict['dir_out_run'])

    # Plots
    settings_dict['dir_out_run_plots'] = settings_dict['dir_out_run'] / 'plots'
    settings_dict['dir_out_run_plots_hires'] = settings_dict['dir_out_run_plots'] / 'hires'
    settings_dict['dir_out_run_plots_agg'] = settings_dict['dir_out_run_plots'] / 'agg'

    # Files
    settings_dict['dir_out_run_raw_data_csv'] = settings_dict['dir_out_run'] / 'raw_data_csv'
    settings_dict['dir_out_run_log'] = settings_dict['dir_out_run'] / 'log'

    # Make dirs
    create_dirs = ['dir_out_run_plots', 'dir_out_run_plots_hires', 'dir_out_run_plots_agg',
                   'dir_out_run_raw_data_csv', 'dir_out_run_log']
    for d in create_dirs:
        if not Path.is_dir(settings_dict[d]):
            print(f"Creating folder {settings_dict[d]} ...")
            os.makedirs(settings_dict[d])

    return settings_dict


def generate_run_id():
    """Generate unique id for this run"""
    # script_start_time = time.strftime("%Y-%m-%d %H:%M:%S")
    run_id = time.strftime("%Y%m%d-%H%M%S")
    run_id = f"BICO-{run_id}"
    return run_id
