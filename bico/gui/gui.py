# -*- coding: utf-8 -*-
from PyQt5 import QtCore as qtc
from PyQt5 import QtGui as qtg
from PyQt5 import QtWidgets as qtw
from PyQt5.QtGui import QPixmap

import settings._version as info
from gui import gui_elements
from help import tooltips


class Ui_MainWindow(object):
    """
        Prepares the raw GUI, i.e. the canvas that is filled with content later.
    """

    def setupUi(self, mainwindow):
        # Main window
        mainwindow.setWindowTitle(f"BICO")
        mainwindow.setWindowIcon(qtg.QIcon('images/logo_BICO1.png'))
        # mainwindow.resize(250, 150)

        # # todo Center mainwindow on screen
        # qr = mainwindow.frameGeometry()  # geometry of the main window, yields: int x, int y, int width, int height
        # cp = qtw.QDesktopWidget().availableGeometry().center()  # center point of screen
        # qr.moveCenter(cp)  # move rectangle's center point to screen's center point
        # mainwindow.move(qr.topLeft())  # top left of rectangle becomes top left of window centering it
        # print(qr)
        mainwindow.move(100, 100)

        # mainwindow.resize(600, 800)
        centralwidget = qtw.QWidget(mainwindow)
        centralwidget.setObjectName("centralwidget")
        centralwidget.setAccessibleName('mainwindow')
        mainwindow.setCentralWidget(centralwidget)

        # Statusbar
        self.statusbar = qtw.QStatusBar(mainwindow)
        self.statusbar.setObjectName("statusbar")
        self.statusbar.showMessage('No processing running.')
        mainwindow.setStatusBar(self.statusbar)

        # CSS
        with open('gui/gui.css', "r") as fh:
            mainwindow.setStyleSheet(fh.read())


        # ADD SECTIONS to LAYOUT CONTAINER
        container = qtw.QHBoxLayout()
        container.addWidget(self.add_section_logo())
        container.addWidget(self.add_section_instruments())
        container.addWidget(self.add_section_raw_data())
        container.addWidget(self.add_section_output())
        # container.addWidget(self.add_section_flux_processing())
        container.addWidget(self.add_section_controls())
        container.setContentsMargins(0, 0, 0, 0)
        centralwidget.setLayout(container)

    def add_section_logo(self):
        section = qtw.QFrame()
        section.setProperty('labelClass', 'section_bg_output')
        grid = qtw.QGridLayout()
        label_image = qtw.QLabel()
        label_image.setPixmap(QPixmap('images/logo_BICO1_256px.png'))

        label_txt = qtw.QLabel("BICO - Binary Conversion")
        label_txt.setProperty('labelClass', 'header_3')
        label_txt.setAlignment(qtc.Qt.AlignCenter | qtc.Qt.AlignVCenter)

        label_txt2 = qtw.QLabel("Convert binary files to ASCII")
        label_txt2.setAlignment(qtc.Qt.AlignCenter | qtc.Qt.AlignVCenter)

        label_txt3 = qtw.QLabel(f"v{info.__version__} / {info.__date__}")
        label_txt3.setAlignment(qtc.Qt.AlignCenter | qtc.Qt.AlignVCenter)

        # Links
        # self.lbl_link_releases = qtw.QLabel(f"<a href='{info.__link_releases__}'>Releases</a>\n")
        # self.lbl_link_releases.setAlignment(qtc.Qt.AlignCenter | qtc.Qt.AlignVCenter)
        # grid.addWidget(self.lbl_link_releases, 5, 0)

        self.lbl_link_releases = gui_elements.add_label_link_to_grid(
            link_txt='Releases', link_str=info.__link_releases__, grid=grid, row=5)
        self.lbl_link_source_code = gui_elements.add_label_link_to_grid(
            link_txt='Source Code', link_str=info.__link_source_code__, grid=grid, row=6)
        self.lbl_link_license = gui_elements.add_label_link_to_grid(
            link_txt='License', link_str=info.__license__, grid=grid, row=7)
        self.lbl_link_help = gui_elements.add_label_link_to_grid(
            link_txt='Help', link_str=info.__link_wiki__, grid=grid, row=8)

        grid.addWidget(label_image, 0, 0)
        grid.addWidget(qtw.QLabel(), 1, 0)
        grid.addWidget(label_txt, 2, 0)
        grid.addWidget(label_txt2, 3, 0)
        grid.addWidget(label_txt3, 4, 0)

        grid.setRowStretch(9, 1)
        section.setLayout(grid)
        return section

    def add_section_output(self):
        # Instruments (instr)
        section = qtw.QFrame()
        section.setProperty('labelClass', 'section_bg_output')
        grid = qtw.QGridLayout()

        # Main Header
        header_output_output = qtw.QLabel('Output')
        header_output_output.setProperty('labelClass', 'header_1')
        grid.addWidget(header_output_output, 0, 0)

        # Output folder
        header_output_plots = qtw.QLabel('Output Folder')
        header_output_plots.setProperty('labelClass', 'header_2')
        grid.addWidget(header_output_plots, 1, 0, 1, 1)
        self.btn_output_folder = \
            gui_elements.add_button_to_grid(label='Select ...', grid=grid, row=2)
        self.btn_output_folder.setToolTip(tooltips.btn_output_folder)
        self.lbl_output_folder = qtw.QLabel("***Please select output folder...***")
        grid.addWidget(self.lbl_output_folder, 3, 0, 1, 2)

        # Output folder name
        header_rawdata_file_settings = qtw.QLabel('Output Folder Name')
        header_rawdata_file_settings.setProperty('labelClass', 'header_2')
        grid.addWidget(header_rawdata_file_settings, 4, 0, 1, 1)
        self.lne_output_folder_name_prefix = \
            gui_elements.add_label_lineedit_to_grid(label='Folder Name Prefix', grid=grid,
                                                    row=5, value='')
        # Variables
        header_output_file_variables = qtw.QLabel('Variables')
        header_output_file_variables.setProperty('labelClass', 'header_2')
        grid.addWidget(header_output_file_variables, 6, 0)
        self.chk_output_variables_add_instr_to_varname = \
            gui_elements.add_checkbox_to_grid(label='Add Instrument To Variable Name', grid=grid, row=7)

        # File Compression
        header_output_file_compression = qtw.QLabel('File Compression')
        header_output_file_compression.setProperty('labelClass', 'header_2')
        grid.addWidget(header_output_file_compression, 8, 0)
        self.cmb_output_compression = \
            gui_elements.add_label_combobox_to_grid(label='Compression', grid=grid, row=9,
                                                    items=['gzip', 'None'])

        self.cmb_output_compression.setToolTip(tooltips.cmb_output_compression)

        # Plots
        header_output_plots = qtw.QLabel('Plots')
        header_output_plots.setProperty('labelClass', 'header_2')
        grid.addWidget(header_output_plots, 10, 0, 1, 1)
        self.chk_output_plots_file_availability = \
            gui_elements.add_checkbox_to_grid(label='File Availability Heatmap', grid=grid, row=11)
        self.chk_output_plots_ts_hires = \
            gui_elements.add_checkbox_to_grid(label='High-res Time Series', grid=grid, row=12)
        self.chk_output_plots_histogram_hires = \
            gui_elements.add_checkbox_to_grid(label='High-res Histograms', grid=grid, row=13)
        self.chk_output_plots_ts_agg = \
            gui_elements.add_checkbox_to_grid(label='Aggregated Time Series', grid=grid, row=14)

        grid.setRowStretch(15, 1)
        section.setLayout(grid)
        return section

    def add_section_instruments(self):
        # Instruments (instr)
        section = qtw.QFrame()
        section.setProperty('labelClass', 'section_bg_instruments')
        grid = qtw.QGridLayout()

        # Main Header
        header_instr_instruments = qtw.QLabel('Instruments')
        header_instr_instruments.setProperty('labelClass', 'header_1')
        grid.addWidget(header_instr_instruments, 0, 0)

        # Site Selection
        header_instr_time_range = qtw.QLabel('Site')
        header_instr_time_range.setProperty('labelClass', 'header_2')
        grid.addWidget(header_instr_time_range, 1, 0)
        self.cmb_instr_site_selection = \
            gui_elements.add_label_combobox_to_grid(label='Select Site', grid=grid, row=2,
                                                    items=['CH-AES', 'CH-AWS', 'CH-CHA', 'CH-DAE', 'CH-DAV', 'CH-FRU',
                                                           'CH-INO', 'CH-LAE', 'CH-LAS', 'CH-OE2'])

        # Data Blocks
        sonic_anemometers = ['HS50-A', 'HS50-B', 'HS100-A', 'R2-A','R350-A', '-None-']
        gas_analyzers = ['IRGA72-A', 'IRGA72-B', 'IRGA75-A', 'IRGA75-A-GN1', 'LGR-A',
                         'QCL-A', 'QCL-A2', 'QCL-A3', 'QCL-A4', 'QCL-C', '-None-']

        header_instr_data_blocks = qtw.QLabel('Data Blocks')
        header_instr_data_blocks.setProperty('labelClass', 'header_2')
        grid.addWidget(header_instr_data_blocks, 3, 0)
        self.cmb_instr_header = \
            gui_elements.add_label_combobox_to_grid(label='Header', grid=grid, row=4, items=['WECOM3'])
        self.cmb_instr_instrument_1 = \
            gui_elements.add_label_combobox_to_grid(label='Instrument 1', grid=grid, row=5, items=sonic_anemometers)
        self.cmb_instr_instrument_2 = \
            gui_elements.add_label_combobox_to_grid(label='Instrument 2', grid=grid, row=6, items=gas_analyzers)
        self.cmb_instr_instrument_3 = \
            gui_elements.add_label_combobox_to_grid(label='Instrument 3', grid=grid, row=7, items=gas_analyzers)

        grid.setRowStretch(8, 1)
        section.setLayout(grid)

        return section

    def add_section_raw_data(self):
        """Add raw data section"""
        section = qtw.QFrame()
        section.setProperty('labelClass', 'section_bg_raw_data')
        grid = qtw.QGridLayout()

        # Main Header
        header_rd_raw_data = qtw.QLabel('Raw Data')
        header_rd_raw_data.setProperty('labelClass', 'header_1')
        grid.addWidget(header_rd_raw_data, 0, 0)

        # Source Folder
        header_rawdata_source_dir = qtw.QLabel('Source Folder')
        header_rawdata_source_dir.setProperty('labelClass', 'header_2')
        grid.addWidget(header_rawdata_source_dir, 1, 0)
        self.btn_rawdata_source_folder = \
            gui_elements.add_button_to_grid(label='Select ...', grid=grid, row=2)
        self.lbl_rawdata_selected_source_folder = qtw.QLabel("***Please select source folder***")
        grid.addWidget(self.lbl_rawdata_selected_source_folder, 3, 0, 1, 2)

        # Time Range
        header_rawdata_time_range = qtw.QLabel('Time Range')
        header_rawdata_time_range.setProperty('labelClass', 'header_2')
        grid.addWidget(header_rawdata_time_range, 4, 0)
        self.dtp_rawdata_time_range_start = \
            gui_elements.add_label_datetimepicker_to_grid(label='Start', grid=grid, row=5)
        self.dtp_rawdata_time_range_end = \
            gui_elements.add_label_datetimepicker_to_grid(label='End', grid=grid, row=6)

        # File Settings
        header_rawdata_file_settings = qtw.QLabel('File Settings')
        header_rawdata_file_settings.setProperty('labelClass', 'header_2')
        grid.addWidget(header_rawdata_file_settings, 7, 0, 1, 1)
        self.lne_rawdata_datetime_format_in_filename = \
            gui_elements.add_label_lineedit_to_grid(label='Date/Time Format In File Name', grid=grid,
                                                    row=8, value='*.X*')
        self.lne_rawdata_file_extension = \
            gui_elements.add_label_lineedit_to_grid(label='File Extension', grid=grid,
                                                    row=9, value='*.X*')
        self.lne_rawdata_min_filesize = \
            gui_elements.add_label_lineedit_to_grid(label='Minimum File Size', grid=grid,
                                                    row=10, value='900', only_int=True)
        self.lne_rawdata_file_limit = \
            gui_elements.add_label_lineedit_to_grid(label='File Limit', grid=grid,
                                                    row=11, value='0', only_int=True)
        self.lne_rawdata_row_limit = \
            gui_elements.add_label_lineedit_to_grid(label='Row Limit Per File', grid=grid,
                                                    row=12, value='0', only_int=True)

        # Special
        header_rawdata_special = qtw.QLabel('Special')
        header_rawdata_special.setProperty('labelClass', 'header_2')
        grid.addWidget(header_rawdata_special, 13, 0)
        self.lne_rawdata_randomfiles = \
            gui_elements.add_label_lineedit_to_grid(label='Select Random Files (0=No)', grid=grid,
                                                    row=14, value='0', only_int=True)

        grid.setRowStretch(15, 1)
        section.setLayout(grid)

        # # -- -- File Type
        # header_rd_file_type = qw.QLabel('File Type')
        # header_rd_file_type.setProperty('labelClass', 'header_3')
        # grid.addWidget(header_rd_file_type, 5, 0, 1, 1)
        # self.cmb_rd_file_type = qw.QComboBox()
        # self.cmb_rd_file_type.addItems(['ETH Binary',
        #                                 'ETH ASCII (previously converted)',
        #                                 'ICOS ASCII'])
        # grid.addWidget(self.cmb_rd_file_type, 5, 1, 1, 1)

        # # -- -- File Source
        # header_rd_source = qw.QLabel('File Source')
        # header_rd_source.setProperty('labelClass', 'header_3')
        # self.cmb_rd_source = qw.QComboBox()
        # self.cmb_rd_source.addItems(['grasslandserver (site-specific)', 'local default', 'select manually'])
        # grid.addWidget(header_rd_source, 7, 0, 1, 1)
        # grid.addWidget(self.cmb_rd_source, 7, 1, 1, 1)

        return section

    def add_section_controls(self):
        # ----------------------------------------------------------
        # CONTROLS (ctr)
        section = qtw.QFrame()
        section.setProperty('labelClass', 'section_bg_controls')
        grid = qtw.QGridLayout()

        # Main Header
        header_ctr_controls = qtw.QLabel('Controls')
        header_ctr_controls.setProperty('labelClass', 'header_1')
        grid.addWidget(header_ctr_controls, 0, 0)

        # Buttons
        self.btn_ctr_save = \
            gui_elements.add_button_to_grid(label='Save Settings', grid=grid, row=1)
        self.btn_ctr_run = \
            gui_elements.add_button_to_grid(label='Run', grid=grid, row=2)

        grid.setRowStretch(3, 1)
        section.setLayout(grid)

        return section

    # def add_section_flux_processing(self):
    #     # ----------------------------------------------------------
    #     # FLUX PROCESSING (fp)
    #     section = qw.QFrame()
    #     section.setProperty('labelClass', 'section_bg_flux_processing')
    #     grid = qw.QGridLayout()
    #
    #     # Main Header
    #     header_fp_flux_processing = qw.QLabel('Flux Processing')
    #     header_fp_flux_processing.setProperty('labelClass', 'header_1')
    #     grid.addWidget(header_fp_flux_processing, 0, 0)
    #
    #     # Skip
    #     header_fp_activate = qw.QLabel('Activate')
    #     header_fp_activate.setProperty('labelClass', 'header_2')
    #     self.chk_fp_activate = qw.QCheckBox()
    #     grid.addWidget(header_fp_activate, 1, 0)
    #     grid.addWidget(self.chk_fp_activate, 1, 1)
    #
    #     # Results
    #     header_fp_results = qw.QLabel('Results')
    #     header_fp_results.setProperty('labelClass', 'header_2')
    #     self.rdb_fp_results_calculate = qw.QRadioButton('New Run: Calculate Fluxes with EddyPro')
    #     self.rdb_fp_results_previous = qw.QRadioButton('Previous Run: Use Previously Calculated EddyPro Results')
    #     grid.addWidget(header_fp_results, 2, 0)
    #     grid.addWidget(self.rdb_fp_results_calculate, 2, 1)
    #     grid.addWidget(self.rdb_fp_results_previous, 3, 1)
    #     group = qw.QButtonGroup()
    #     group.addButton(self.rdb_fp_results_calculate)
    #     group.addButton(self.rdb_fp_results_previous)
    #
    #     # Plots
    #     header_fp_plots = qw.QLabel('Plots')
    #     header_fp_plots.setProperty('labelClass', 'header_2')
    #     self.chk_fp_plots_summary = qw.QCheckBox('Summaries')
    #     self.chk_fp_plots_diurnal_cycles = qw.QCheckBox('Diurnal Cycles')
    #     self.chk_fp_plots_heatmaps = qw.QCheckBox('Heatmaps')
    #     self.chk_fp_plots_windroses = qw.QCheckBox('Windroses')
    #     grid.addWidget(header_fp_plots, 4, 0)
    #     grid.addWidget(self.chk_fp_plots_summary, 4, 1)
    #     grid.addWidget(self.chk_fp_plots_diurnal_cycles, 5, 1)
    #     grid.addWidget(self.chk_fp_plots_heatmaps, 6, 1)
    #     grid.addWidget(self.chk_fp_plots_windroses, 7, 1)
    #
    #     grid.setRowStretch(8, 1)
    #     section.setLayout(grid)
    #
    #     return section]


class TesGui(qtw.QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super(TesGui, self).__init__(parent)
        self.setupUi(self)

# def main():
#     appp = qtw.QApplication(sys.argv)
#     testgui = TesGui()
#     testgui.show()
#     appp.exec_()


# if __name__ == '__main__':
#     main()
