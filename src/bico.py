import datetime as dt
import os
import sys
from pathlib import Path

import pandas as pd
from PyQt5 import QtCore as qtc
from PyQt5 import QtGui as qtg
from PyQt5 import QtWidgets as qtw

import ops.logger
import ops.setup
from gui.gui import Ui_MainWindow
from ops import bin, vis, file, stats, cli, format_data
from settings import _version


class BicoEngine():

    def __init__(
            self,
            settings_dict: dict,
            usedgui: bool
    ):

        self.settings_dict = settings_dict
        self.usedgui = usedgui

        # Setup outdirs, run ID and logger
        self.run_id = ops.setup.generate_run_id()
        self.settings_dict['run_id'] = self.run_id
        self.settings_dict = ops.setup.make_run_outdirs(settings_dict=self.settings_dict)
        self.logger = ops.logger.setup_logger(settings_dict=self.settings_dict)

        self.stats_coll_df = pd.DataFrame()  # Collects agg stats
        self.dblocks_seq = []

        # self.run()

    def run(self):

        # If engine was called from GUI the selected settings need to be saved
        # to account for adjustments made in the GUI before starting conversion.
        if self.usedgui:
            file.save_settings_to_file(self.settings_dict, copy_to_outdir=True)

        # Log info
        self.logger.info(f"Run ID: {self.run_id}")
        self.logger.info(f"BICO Version: {_version.__version__} / {_version.__date__}")

        # Format string to parse datetime info from filename
        self.settings_dict['filename_datetime_parsing_string'] = self.make_datetime_parsing_string()

        # Settings for file header
        self.bin_size_header = 29 if self.settings_dict['header'] == 'WECOM3' else 38  # todo better solution

        # Load settings for datablocks: their types, sequence and properties
        self.dblocks_seq = self.assemble_datablock_sequence()
        self.dblocks_props = file.load_dblocks_props(dblocks_types=self.dblocks_seq,
                                                     settings_dict=self.settings_dict)  # Load data block settings

        # Search valid files, depending on settings
        bin_found_files_dict = file.SearchAll(settings_dict=self.settings_dict,
                                              logger=self.logger).keep_valid_files()

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
                                  logger=self.logger)
        self._log_fileloopfinish()

        # Stats collection export
        file.export_stats_collection_csv(df=stats_coll_df, outdir=self.settings_dict['dir_out_run_plots_agg'],
                                         run_id=self.run_id, logger=self.logger)

        # Plot aggregated stats collection from files
        if self.settings_dict['plot_ts_agg'] == '1':
            self._plot_stats_collection_agg()

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
                keep_date_col=True,
                parse_dates=True,
                date_parser=None,
                index_col=0,
                dtype=None
            )

            # Generate plots for aggregated data
            vis.aggs_ts(df=df, outdir=self.settings_dict['dir_out_run_plots_agg'], logger=self.logger)

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
            ascii_filedate = bin_filedate.strftime('%Y%m%d%H%M')  # w/o extension
            ascii_filename = f"{self.settings_dict['site']}_{ascii_filedate}"  # w/o extension

            counter_bin_files += 1
            # self.statusbar.showMessage(f"Working on file #{counter_bin_files}: {bin_file}")

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
            obj = bin.ConvertData(binary_filename=bin_filepath,
                                  size_header=self.bin_size_header,
                                  dblocks=dblocks_props,
                                  limit_read_lines=int(self.settings_dict['row_limit']),
                                  logger=self.logger,
                                  cur_file_number=counter_bin_files)
            obj.run()
            # ascii_df = obj.get_data()
            dblock_headers, file_data_rows = obj.get_data()

            # Add instrument info to variable name
            if self.settings_dict['add_instr_to_varname'] == '1':
                dblock_headers = self.add_instr_to_varname(dblock_headers=dblock_headers)

            # Make dataframe of data
            ascii_df = format_data.make_df(data_lines=file_data_rows,
                                           header=dblock_headers,
                                           logger=self.logger)

            # Save to file
            ascii_filepath = file.export_raw_data_ascii(df=ascii_df,
                                                        outdir=self.settings_dict['dir_out_run_raw_data_ascii'],
                                                        outfilename=ascii_filename,
                                                        logger=self.logger,
                                                        compression=self.settings_dict['file_compression'])

            # Read the converted file that was created
            file_contents_ascii_df = file.read_converted_ascii(filepath=ascii_filepath,
                                                               compression=self.settings_dict['file_compression'])

            # Stats
            stats_coll_df = stats.calc(stats_df=file_contents_ascii_df.copy(),
                                       stats_coll_df=stats_coll_df,
                                       bin_filedate=bin_filedate,
                                       counter_bin_files=counter_bin_files,
                                       logger=logger)
            stats_coll_df.loc[bin_filedate, ('_filesize', '[Bytes]', '[FILE]', 'total')] = os.path.getsize(bin_filepath)
            stats_coll_df.loc[bin_filedate, ('_columns', '[#]', '[FILE]', 'total')] = len(
                file_contents_ascii_df.columns)
            stats_coll_df.loc[bin_filedate, ('_total_values', '[#]', '[FILE]', 'total')] = file_contents_ascii_df.size

            # Plot high-resolution data
            if self.settings_dict['plot_ts_hires'] == '1':
                vis.high_res_ts(df=file_contents_ascii_df.copy(), outfile=ascii_filename,
                                outdir=self.settings_dict['dir_out_run_plots_hires'], logger=logger)
            if self.settings_dict['plot_histogram_hires'] == '1':
                vis.high_res_histogram(df=file_contents_ascii_df.copy(), outfile=ascii_filename,
                                       outdir=self.settings_dict['dir_out_run_plots_hires'], logger=logger)

        return stats_coll_df

    def add_instr_to_varname(self, dblock_headers):
        """Add instrument info to variable name to avoid duplicates

            e.g. The var STATUS_CODE exists both in IRGA72-A and QCL-C
            and are renamed to STATUS_CODE_IRGA75-A and STATUS_CODE_QCL-C
        """
        for idx_h, h in enumerate(dblock_headers):
            dblock_headers[idx_h] = (f"{h[0]}_{h[2]}", h[1], h[2])
        return dblock_headers

    def make_datetime_parsing_string(self):
        _parsing_string = self.settings_dict['filename_datetime_format']
        _parsing_string = _parsing_string.replace('yyyy', '%Y')
        _parsing_string = _parsing_string.replace('mm', '%m')
        _parsing_string = _parsing_string.replace('dd', '%d')
        _parsing_string = _parsing_string.replace('HH', '%H')
        _parsing_string = _parsing_string.replace('MM', '%M')
        return _parsing_string

    def assemble_datablock_sequence(self):
        dblocks_seq = []
        instrument_settings = ['instrument_1', 'instrument_2', 'instrument_3']
        for key, val in self.settings_dict.items():
            if key in instrument_settings:
                dblocks_seq.append(val)
        return dblocks_seq


class BicoGUI(qtw.QMainWindow, Ui_MainWindow):
    """Run BICO from GUI"""

    def __init__(self, parent=None):
        super(BicoGUI, self).__init__(parent)
        self.setupUi(self)

        self.dblocks_seq = []  # Data block sequence, order of instruments

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
        self._show_settings_in_gui()

        # Connect GUI elements
        self._connections()

    def run(self):
        self.btn_ctr_save.setDisabled(True)
        self.btn_ctr_run.setDisabled(True)

        # Setup
        self._get_settings_from_gui()

        bicoengine = BicoEngine(settings_dict=self.settings_dict,
                                usedgui=True)
        bicoengine.run()

    def update_dict_key(self, key, new_val):
        """ Updates key in Dict with new_val """
        self.settings_dict[key] = new_val
        ('{}: {}'.format(key, self.settings_dict[key]))

    def _get_settings_from_gui(self):
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
        self.update_dict_key(key='add_instr_to_varname',
                             new_val='1' if self.chk_output_variables_add_instr_to_varname.isChecked() else '0')
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
        self.settings_dict['dir_script'] = os.path.join(os.path.dirname(dir_script))
        self.settings_dict['dir_settings'] = dir_settings
        self.settings_dict['dir_bico'] = Path(self.settings_dict['dir_script']).parents[0]
        self.settings_dict['dir_root'] = Path(self.settings_dict['dir_script']).parents[1]

        # Update dirs that can be changed in the gui
        self.settings_dict['dir_source'] = \
            self.dir_bico if not self.settings_dict['dir_source'] else self.settings_dict['dir_source']
        self.settings_dict['dir_out'] = \
            self.dir_bico if not self.settings_dict['dir_out'] else self.settings_dict['dir_out']

    def _set_gui_combobox(self, combobox, find_text):
        idx = combobox.findText(find_text, qtc.Qt.MatchContains)
        if idx >= 0:
            combobox.setCurrentIndex(idx)

    def _set_gui_datetimepicker(self, datetimepicker, date_str):
        qtDate = qtc.QDateTime.fromString(date_str, 'yyyy-MM-dd hh:mm')
        datetimepicker.setDateTime(qtDate)

    def _set_gui_lineedit(self, lineedit, string):
        lineedit.setText(string)

    def _set_gui_checkbox(self, checkbox, state):
        checkbox.setChecked(True if state == '1' else False)

    def _show_settings_in_gui(self):
        """Update GUI from dict"""
        # Instruments
        self._set_gui_combobox(combobox=self.cmb_instr_site_selection, find_text=self.settings_dict['site'])
        self._set_gui_combobox(combobox=self.cmb_instr_header, find_text=self.settings_dict['header'])
        self._set_gui_combobox(combobox=self.cmb_instr_instrument_1, find_text=self.settings_dict['instrument_1'])
        self._set_gui_combobox(combobox=self.cmb_instr_instrument_2, find_text=self.settings_dict['instrument_2'])
        self._set_gui_combobox(combobox=self.cmb_instr_instrument_3, find_text=self.settings_dict['instrument_3'])

        # Raw Data
        self.lbl_rawdata_selected_source_folder.setText(str(self.settings_dict['dir_source']))
        self._set_gui_datetimepicker(datetimepicker=self.dtp_rawdata_time_range_start,
                                     date_str=self.settings_dict['start_date'])
        self._set_gui_datetimepicker(datetimepicker=self.dtp_rawdata_time_range_end,
                                     date_str=self.settings_dict['end_date'])
        self._set_gui_lineedit(lineedit=self.lne_rawdata_datetime_format_in_filename,
                               string=self.settings_dict['filename_datetime_format'])
        self._set_gui_lineedit(lineedit=self.lne_rawdata_file_extension, string=self.settings_dict['file_ext'])
        self._set_gui_lineedit(lineedit=self.lne_rawdata_min_filesize, string=self.settings_dict['file_size_min'])
        self._set_gui_lineedit(lineedit=self.lne_rawdata_file_limit, string=self.settings_dict['file_limit'])
        self._set_gui_lineedit(lineedit=self.lne_rawdata_row_limit, string=self.settings_dict['row_limit'])
        self._set_gui_lineedit(lineedit=self.lne_rawdata_randomfiles, string=self.settings_dict['select_random_files'])

        # Output
        self.lbl_output_folder.setText(str(self.settings_dict['dir_out']))
        self._set_gui_lineedit(lineedit=self.lne_output_folder_name_prefix,
                               string=self.settings_dict['output_folder_name_prefix'])
        self._set_gui_checkbox(checkbox=self.chk_output_variables_add_instr_to_varname,
                               state=self.settings_dict['add_instr_to_varname'])
        self._set_gui_combobox(combobox=self.cmb_output_compression, find_text=self.settings_dict['file_compression'])
        self._set_gui_checkbox(checkbox=self.chk_output_plots_file_availability,
                               state=self.settings_dict['plot_file_availability'])
        self._set_gui_checkbox(checkbox=self.chk_output_plots_ts_hires,
                               state=self.settings_dict['plot_ts_hires'])
        self._set_gui_checkbox(checkbox=self.chk_output_plots_histogram_hires,
                               state=self.settings_dict['plot_histogram_hires'])
        self._set_gui_checkbox(checkbox=self.chk_output_plots_ts_agg,
                               state=self.settings_dict['plot_ts_agg'])

    def _call_link(self, link_str):
        """Call hyperlink from label, opens in browser"""
        qtg.QDesktopServices.openUrl(qtc.QUrl(link_str))

    def _connections(self):
        """Connect GUI elements to functions"""
        # Logo
        self.lbl_link_changelog.linkActivated.connect(self._call_link)
        self.lbl_link_datablocks.linkActivated.connect(self._call_link)
        self.lbl_link_releases.linkActivated.connect(self._call_link)
        self.lbl_link_source_code.linkActivated.connect(self._call_link)
        self.lbl_link_license.linkActivated.connect(self._call_link)
        self.lbl_link_help.linkActivated.connect(self._call_link)

        # Raw Data
        self.btn_rawdata_source_folder.clicked.connect(lambda: self._select_dir(
            start_dir=self.settings_dict['dir_source'], dir_setting='dir_source',
            update_label=self.lbl_rawdata_selected_source_folder, dialog_txt='Select Source Folder For Raw Data Files'))

        # Output
        self.btn_output_folder.clicked.connect(lambda: self._select_dir(
            start_dir=self.settings_dict['dir_out'], dir_setting='dir_out',
            update_label=self.lbl_output_folder, dialog_txt='Select Output Folder'))

        # Controls
        self.btn_ctr_save.clicked.connect(lambda: self._save_settings())
        self.btn_ctr_run.clicked.connect(lambda: self.run())

    def _save_settings(self):
        """Get selected settings from GUI elements, store in dict and save to file"""
        self._get_settings_from_gui()
        file.save_settings_to_file(self.settings_dict)

    def _select_dir(self, start_dir, dir_setting, update_label, dialog_txt):
        """ Select directory, update dict and label"""
        selected_dir = qtw.QFileDialog.getExistingDirectory(None, dialog_txt, str(start_dir))  # Open dialog
        self.settings_dict[dir_setting] = selected_dir  # Update settings dict
        update_label.setText(self.settings_dict[dir_setting])  # Update gui
        # ops.setup.settings_dict_to_file(settings_dict=self.settings_dict)  # Save to file


class BicoFolder:
    """Run BICO in specified folder without GUI

    This starts BicoEngine.
    """

    def __init__(self, folder: str):
        self.folder = Path(folder)

        self.settings_dict = {}

    def run(self):
        settingsfilefound = self.search_settingsfile()
        if settingsfilefound:
            # Read Settings: File --> Dict
            self.settings_dict = \
                ops.setup.read_settings_file_to_dict(dir_settings=self.folder,
                                                     file='Bico.settings',
                                                     reset_paths=False)
            self.execute_in_folder()
        else:
            print(f"(!)ERROR: No 'Bico.settings' file found. Please make sure it is in folder '{self.folder}'")

    def search_settingsfile(self):
        files = os.listdir(self.folder)
        settingsfilefound = True if 'Bico.settings' in files else False
        return settingsfilefound

    def execute_in_folder(self):
        bicoengine = BicoEngine(settings_dict=self.settings_dict,
                                usedgui=False)
        bicoengine.run()


def main(args):
    # Run BICO w/o GUI
    if args.folder:
        # todo
        bicofromfolder = BicoFolder(folder=args.folder)
        bicofromfolder.run()

    # Run BICO with GUI
    elif args.gui:
        app = qtw.QApplication(sys.argv)
        bicofromgui = BicoGUI()
        bicofromgui.show()
        app.exec_()

    else:
        print("Please add arg how BICO should be executed. Add '-h' for help.")


if __name__ == '__main__':
    args = cli.get_args()
    args = cli.validate_args(args)
    main(args)

# # Compress uncompressed ASCII to gzip, delete uncompressed if gzip selected
# if self.settings_dict['file_compression'] == 'gzip':
#     with open(ascii_filepath, 'rb') as f_in, gzip.open(ascii_filepath_gzip, 'wb') as f_out:
#         f_out.writelines(f_in)
#     os.remove(ascii_filepath)  # Delete uncompressed
