import datetime as dt
import os
import sys
from pathlib import Path
from shutil import copyfile

import pandas as pd
from PyQt5 import QtCore as qtc
from PyQt5 import QtGui as qtg
from PyQt5 import QtWidgets as qtw

import ops.logger
import ops.setup
from gui.gui import Ui_MainWindow
from ops import bin, format_data, vis, file, stats
from settings import _version


# TODO LATER parallelize, multiprocessing?
# import multiprocessing as mp
# print("Number of processors: ", mp.cpu_count())


class Bico(qtw.QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super(Bico, self).__init__(parent)
        self.setupUi(self)
        self.stats_coll_df = pd.DataFrame()  # Collects agg stats
        self.dblocks_seq = []  # Data block sequence, order of instruments

        self.run_id = ops.setup.generate_run_id()

        # Detect Folders
        dir_script = os.path.abspath(__file__)  # Dir of this file
        dir_settings = Path(
            os.path.join(os.path.dirname(dir_script))) / 'settings'  # Preload settings dir to load settings file

        # Read Settings: File --> Dict
        self.settings_dict = \
            ops.setup.read_settings_file_to_dict(dir_settings=dir_settings,
                                                 file='Bico.settings',
                                                 reset_paths=False)

        # Update dir settings in dict, for current run
        self.update_dict_dir_settings(dir_script=dir_script, dir_settings=dir_settings)

        # Fill-In Settings: Dict --> GUI
        self.show_settings_in_gui()

        # Connect GUI elements
        self.connections()

    def run(self):
        # Setup run
        self.get_settings_from_gui()
        self.settings_dict = ops.setup.make_run_outdirs(settings_dict=self.settings_dict)
        self.save_settings_to_file(copy_to_outdir=True)

        self.logger = ops.logger.setup_logger(settings_dict=self.settings_dict)
        self.logger.info(f"Run ID: {self.run_id}")

        self.logger.info(f"BICO Version: {_version.__version__} / {_version.__date__}")
        self.settings_dict['filename_datetime_parsing_string'] = self.make_datetime_parsing_string()

        self.bin_size_header = 29 if self.settings_dict['header'] == 'WECOM3' else 38  # todo better solution

        self.dblocks_seq = self.assemble_datablock_sequence()
        self.dblocks_props = file.load_dblocks_props(dblocks_types=self.dblocks_seq,
                                                     settings_dict=self.settings_dict)  # Load data block settings

        # Search valid files, depending on settings
        self.bin_found_files_dict = file.SearchAll(settings_dict=self.settings_dict,
                                                   logger=self.logger).keep_valid_files()

        # Availability heatmap
        if self.settings_dict['plot_file_availability'] == '1':
            vis.availability_heatmap(bin_found_files_dict=self.bin_found_files_dict,
                                     bin_file_datefrmt=self.settings_dict['filename_datetime_parsing_string'],
                                     root_outdir=self.settings_dict['dir_out_run_plots'],
                                     logger=self.logger)

        # Loop through binary files
        stats_coll_df = self.loop(bin_found_files_dict=self.bin_found_files_dict,
                                  dblocks_props=self.dblocks_props,
                                  stats_coll_df=self.stats_coll_df,
                                  logger=self.logger)

        # File loop finished
        self.logger.info("")
        self.logger.info("=" * 20)
        self.logger.info(f"File loop finished.")
        self.logger.info("=" * 20)
        self.logger.info("")

        # Stats collection export
        file.export_stats_collection_csv(df=stats_coll_df, outdir=self.settings_dict['dir_out_run_plots_agg'],
                                         run_id=self.run_id, logger=self.logger)

        # Plot stats collection from file
        if self.settings_dict['plot_ts_agg'] == '1':
            bin_found_files_dict = file.SearchAll.search_all(dir=self.settings_dict['dir_out_run_plots_agg'],
                                                             file_id='stats_*.csv',
                                                             logger=self.logger)
            for fid, filepath in bin_found_files_dict.items():
                df = pd.read_csv(filepath,
                                 skiprows=None,
                                 header=[0, 1, 2, 3],
                                 na_values=-9999,
                                 encoding='utf-8',
                                 delimiter=',',
                                 keep_date_col=True,
                                 parse_dates=True,
                                 date_parser=None,
                                 index_col=0,
                                 dtype=None)
                vis.aggs_ts(df=df, outdir=self.settings_dict['dir_out_run_plots_agg'], logger=self.logger)

        self.logger.info("")
        self.logger.info("")
        self.logger.info("")
        self.logger.info("=" * 20)
        self.logger.info("BICO FINISHED.")
        self.logger.info("=" * 20)

    def make_datetime_parsing_string(self):
        _parsing_string = self.settings_dict['filename_datetime_format']
        _parsing_string = _parsing_string.replace('yyyy', '%Y')
        _parsing_string = _parsing_string.replace('mm', '%m')
        _parsing_string = _parsing_string.replace('dd', '%d')
        _parsing_string = _parsing_string.replace('HH', '%H')
        _parsing_string = _parsing_string.replace('MM', '%M')
        return _parsing_string

    def update_dict_key(self, key, new_val):
        """ Updates key in Dict with new_val """
        self.settings_dict[key] = new_val
        ('{}: {}'.format(key, self.settings_dict[key]))

    def get_settings_from_gui(self):
        """Read settings from GUI and store in dict"""
        # Instruments
        self.update_dict_key(key='site', new_val=self.cmb_instr_site_selection.currentText())
        self.update_dict_key(key='header', new_val=self.cmb_instr_header.currentText())
        self.update_dict_key(key='instrument_1', new_val=self.cmb_instr_instrument_1.currentText())
        self.update_dict_key(key='instrument_2', new_val=self.cmb_instr_instrument_2.currentText())
        self.update_dict_key(key='instrument_3', new_val=self.cmb_instr_instrument_3.currentText())

        # Raw Data
        self.update_dict_key(key='dir_source', new_val=self.lbl_rawdata_selected_source_folder.text())
        self.update_dict_key(key='start_date',
                             new_val=self.dtp_rawdata_time_range_start.dateTime().toString('yyyy-MM-dd hh:mm'))
        self.update_dict_key(key='end_date',
                             new_val=self.dtp_rawdata_time_range_end.dateTime().toString('yyyy-MM-dd hh:mm'))
        self.update_dict_key(key='filename_datetime_format',
                             new_val=self.lne_rawdata_datetime_format_in_filename.text())
        self.update_dict_key(key='file_ext', new_val=self.lne_rawdata_file_extension.text())
        self.update_dict_key(key='file_size_min', new_val=self.lne_rawdata_min_filesize.text())
        self.update_dict_key(key='file_limit', new_val=self.lne_rawdata_file_limit.text())
        self.update_dict_key(key='row_limit', new_val=self.lne_rawdata_row_limit.text())
        self.update_dict_key(key='select_random_files', new_val=self.lne_rawdata_randomfiles.text())

        # Output
        self.update_dict_key(key='dir_out', new_val=self.lbl_output_folder.text())
        self.update_dict_key(key='output_folder_name_prefix', new_val=self.lne_output_folder_name_prefix.text())
        self.update_dict_key(key='file_compression', new_val=self.cmb_output_compression.currentText())
        self.update_dict_key(key='plot_file_availability',
                             new_val='1' if self.chk_output_plots_file_availability.isChecked() else '0')
        self.update_dict_key(key='plot_ts_hires',
                             new_val='1' if self.chk_output_plots_ts_hires.isChecked() else '0')
        self.update_dict_key(key='plot_histogram_hires',
                             new_val='1' if self.chk_output_plots_histogram_hires.isChecked() else '0')
        self.update_dict_key(key='plot_ts_agg',
                             new_val='1' if self.chk_output_plots_ts_agg.isChecked() else '0')

    def update_dict_dir_settings(self, dir_script, dir_settings):
        """Update dir info for current run"""
        self.settings_dict['run_id'] = self.run_id
        self.settings_dict['dir_script'] = os.path.join(os.path.dirname(dir_script))
        self.settings_dict['dir_settings'] = dir_settings
        self.settings_dict['dir_bico'] = Path(self.settings_dict['dir_script']).parents[0]
        self.settings_dict['dir_root'] = Path(self.settings_dict['dir_script']).parents[1]

        # Update dirs that can be changed in the gui
        self.settings_dict['dir_source'] = \
            self.dir_bico if not self.settings_dict['dir_source'] else self.settings_dict['dir_source']
        self.settings_dict['dir_out'] = \
            self.dir_bico if not self.settings_dict['dir_out'] else self.settings_dict['dir_out']

    def set_gui_combobox(self, combobox, find_text):
        idx = combobox.findText(find_text, qtc.Qt.MatchContains)
        if idx >= 0:
            combobox.setCurrentIndex(idx)

    def set_gui_datetimepicker(self, datetimepicker, date_str):
        qtDate = qtc.QDateTime.fromString(date_str, 'yyyy-MM-dd hh:mm')
        datetimepicker.setDateTime(qtDate)

    def set_gui_lineedit(self, lineedit, string):
        lineedit.setText(string)

    def set_gui_checkbox(self, checkbox, state):
        checkbox.setChecked(True if state == '1' else False)

    def show_settings_in_gui(self):
        """Update GUI from dict"""
        # Instruments
        self.set_gui_combobox(combobox=self.cmb_instr_site_selection, find_text=self.settings_dict['site'])
        self.set_gui_combobox(combobox=self.cmb_instr_header, find_text=self.settings_dict['header'])
        self.set_gui_combobox(combobox=self.cmb_instr_instrument_1, find_text=self.settings_dict['instrument_1'])
        self.set_gui_combobox(combobox=self.cmb_instr_instrument_2, find_text=self.settings_dict['instrument_2'])
        self.set_gui_combobox(combobox=self.cmb_instr_instrument_3, find_text=self.settings_dict['instrument_3'])

        # Raw Data
        self.lbl_rawdata_selected_source_folder.setText(str(self.settings_dict['dir_source']))
        self.set_gui_datetimepicker(datetimepicker=self.dtp_rawdata_time_range_start,
                                    date_str=self.settings_dict['start_date'])
        self.set_gui_datetimepicker(datetimepicker=self.dtp_rawdata_time_range_end,
                                    date_str=self.settings_dict['end_date'])
        self.set_gui_lineedit(lineedit=self.lne_rawdata_datetime_format_in_filename,
                              string=self.settings_dict['filename_datetime_format'])
        self.set_gui_lineedit(lineedit=self.lne_rawdata_file_extension, string=self.settings_dict['file_ext'])
        self.set_gui_lineedit(lineedit=self.lne_rawdata_min_filesize, string=self.settings_dict['file_size_min'])
        self.set_gui_lineedit(lineedit=self.lne_rawdata_file_limit, string=self.settings_dict['file_limit'])
        self.set_gui_lineedit(lineedit=self.lne_rawdata_row_limit, string=self.settings_dict['row_limit'])
        self.set_gui_lineedit(lineedit=self.lne_rawdata_randomfiles, string=self.settings_dict['select_random_files'])

        # Output
        self.lbl_output_folder.setText(str(self.settings_dict['dir_out']))
        self.set_gui_lineedit(lineedit=self.lne_output_folder_name_prefix,
                              string=self.settings_dict['output_folder_name_prefix'])
        self.set_gui_combobox(combobox=self.cmb_output_compression, find_text=self.settings_dict['file_compression'])
        self.set_gui_checkbox(checkbox=self.chk_output_plots_file_availability,
                              state=self.settings_dict['plot_file_availability'])
        self.set_gui_checkbox(checkbox=self.chk_output_plots_ts_hires,
                              state=self.settings_dict['plot_ts_hires'])
        self.set_gui_checkbox(checkbox=self.chk_output_plots_histogram_hires,
                              state=self.settings_dict['plot_histogram_hires'])
        self.set_gui_checkbox(checkbox=self.chk_output_plots_ts_agg,
                              state=self.settings_dict['plot_ts_agg'])

    def link(self, link_str):
        """Call hyperlink from label, opens in browser"""
        qtg.QDesktopServices.openUrl(qtc.QUrl(link_str))

    def connections(self):
        """Connect GUI elements to functions"""
        # Logo
        self.lbl_link_releases.linkActivated.connect(self.link)
        self.lbl_link_source_code.linkActivated.connect(self.link)
        self.lbl_link_license.linkActivated.connect(self.link)
        self.lbl_link_help.linkActivated.connect(self.link)

        # Raw Data
        self.btn_rawdata_source_folder.clicked.connect(lambda: self.select_dir(
            start_dir=self.settings_dict['dir_source'], dir_setting='dir_source',
            update_label=self.lbl_rawdata_selected_source_folder, dialog_txt='Select Source Folder For Raw Data Files'))

        # Output
        self.btn_output_folder.clicked.connect(lambda: self.select_dir(
            start_dir=self.settings_dict['dir_out'], dir_setting='dir_out',
            update_label=self.lbl_output_folder, dialog_txt='Select Output Folder'))

        # Controls
        self.btn_ctr_save.clicked.connect(lambda: self.save_settings())
        self.btn_ctr_run.clicked.connect(lambda: self.run())

    def save_settings(self):
        """Get selected settings from GUI elements, store in dict and save to file"""
        self.get_settings_from_gui()
        self.save_settings_to_file()

    def save_settings_to_file(self, copy_to_outdir=False):
        """Save settings dict to settings file """
        old_settings_file = os.path.join(self.settings_dict['dir_settings'], 'Bico.settings')
        new_settings_file = os.path.join(self.settings_dict['dir_settings'], 'Bico.settingsTemp')
        with open(old_settings_file) as infile, open(new_settings_file, 'w') as outfile:
            for line in infile:  # cycle through all lines in settings file
                if ('=' in line) and (not line.startswith('#')):  # identify lines that contain setting
                    line_id, line_setting = line.strip().split('=')
                    line = '{}={}\n'.format(line_id, self.settings_dict[line_id])  # insert setting from dict
                outfile.write(line)
        try:
            os.remove(old_settings_file + 'Old')
        except:
            pass
        os.rename(old_settings_file, old_settings_file + 'Old')
        os.rename(new_settings_file, old_settings_file)

        if copy_to_outdir:
            # Save a copy of the settings file also in the output dir
            run_settings_file_path = Path(self.settings_dict['dir_out_run']) / 'Bico.settings'
            copyfile(old_settings_file, run_settings_file_path)
            pass

        # return settings_dict

    def select_dir(self, start_dir, dir_setting, update_label, dialog_txt):
        """ Select directory, update dict and label"""
        selected_dir = qtw.QFileDialog.getExistingDirectory(None, dialog_txt, str(start_dir))  # Open dialog
        self.settings_dict[dir_setting] = selected_dir  # Update settings dict
        update_label.setText(self.settings_dict[dir_setting])  # Update gui
        # ops.setup.settings_dict_to_file(settings_dict=self.settings_dict)  # Save to file

    def loop(self, bin_found_files_dict, dblocks_props, stats_coll_df, logger):
        """Process files"""
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

        counter_bin_files = 0
        for bin_file, bin_filepath in bin_found_files_dict.items():
            bin_filedate = dt.datetime.strptime(bin_filepath.name,
                                                self.settings_dict['filename_datetime_parsing_string'])
            csv_filedate = bin_filedate.strftime('%Y%m%d%H%M')  # w/o extension
            counter_bin_files += 1
            self.statusbar.showMessage(f"Working on file #{counter_bin_files}: {bin_file}")

            # Check if file limit is exceeded, break
            if (counter_bin_files > 1) & (int(self.settings_dict['file_limit']) > 0):
                if counter_bin_files > int(self.settings_dict['file_limit']):
                    logger.info(f"File limit ({self.settings_dict['file_limit']}) reached,"
                                f" ignoring other files.")
                    break

            logger.info(f"[{bin_file}]")
            logger.info("=" * (len(bin_file) + 2))
            logger.info(f"    Reading binary file #{counter_bin_files} of {num_bin_files}: {bin_file}...")
            logger.info(f"    Data block sequence: {self.dblocks_seq}")

            # Read binary data file
            obj = bin.ReadFile(binary_filename=bin_filepath,
                               size_header=self.bin_size_header,
                               dblocks=dblocks_props,
                               limit_read_lines=int(self.settings_dict['row_limit']),
                               logger=self.logger)
            obj.run()
            data_lines, header, tic, counter_lines = obj.get_data()

            bin.speedstats(tic=tic, counter_lines=counter_lines, logger=logger)

            # Make DataFrame
            df = format_data.make_df(data_lines=data_lines, header=header, logger=logger)

            # Stats #todo -9999 NaNs
            stats_coll_df = stats.calc(stats_df=df.copy(),
                                       stats_coll_df=stats_coll_df,
                                       bin_filedate=bin_filedate,
                                       counter_bin_files=counter_bin_files,
                                       logger=logger)
            stats_coll_df.loc[bin_filedate, ('_filesize', '[Bytes]', '[FILE]', 'total')] = os.path.getsize(bin_filepath)
            stats_coll_df.loc[bin_filedate, ('_columns', '[#]', '[FILE]', 'total')] = len(df.columns)
            stats_coll_df.loc[bin_filedate, ('_total_values', '[#]', '[FILE]', 'total')] = df.size

            csv_filename = f"{self.settings_dict['site']}_{csv_filedate}"

            # Export file CSV
            file.export_raw_data_ascii(df=df, outfile=csv_filename, logger=logger,
                                       outdir=self.settings_dict['dir_out_run_raw_data_ascii'],
                                       compression=self.settings_dict['file_compression'])

            # Plot high-resolution data
            if self.settings_dict['plot_ts_hires'] == '1':
                vis.high_res_ts(df=df.copy(), outfile=csv_filename,
                                outdir=self.settings_dict['dir_out_run_plots_hires'], logger=logger)
            if self.settings_dict['plot_histogram_hires'] == '1':
                vis.high_res_histogram(df=df.copy(), outfile=csv_filename,
                                       outdir=self.settings_dict['dir_out_run_plots_hires'], logger=logger)

        return stats_coll_df

    def assemble_datablock_sequence(self):
        dblocks_seq = []
        instrument_settings = ['instrument_1', 'instrument_2', 'instrument_3']
        for key, val in self.settings_dict.items():
            if key in instrument_settings:
                dblocks_seq.append(val)
        return dblocks_seq


def main():
    app = qtw.QApplication(sys.argv)
    bico = Bico()
    bico.show()
    app.exec_()


if __name__ == '__main__':
    main()
