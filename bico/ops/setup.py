import os
import time


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


def generate_run_id():
    """Generate unique id for this run"""
    # script_start_time = time.strftime("%Y-%m-%d %H:%M:%S")
    run_id = time.strftime("%Y%m%d-%H%M%S")
    run_id = f"BICO-{run_id}"
    return run_id
