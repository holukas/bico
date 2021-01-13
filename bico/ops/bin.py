import pandas as pd
import csv
import mmap
import os
import struct
import time

import settings.data_blocks.header.wecom3
from . import bin_conversion_exceptions as bce
from ops import format_data, file

def make_header(dblock):
    """Get header info for data block, including for variables from bit maps"""
    dblock_header = []  # Collects header
    for var, props in dblock.items():
        if 'bytes' not in props.keys():  # Skip bit map variables
            continue
        # Add var name, units in brackets and datablock in brackets
        dblock_header.append((var, f"[{props['units']}]", f"[{props['datablock']}]"))

        # Extract variables from bit map
        if props['units'] == 'bit_map':
            bit_map_dict = ConvertData.bit_map_get_vars(dblock=dblock)
            bit_map_headers = bit_map_extract_header(bit_map_dict=bit_map_dict)
            for bmh in bit_map_headers:
                dblock_header.append(bmh)
    return dblock_header


def bit_map_extract_header(bit_map_dict):
    """Extract bit map values from binary string"""
    bit_map_headers = []
    for bit_map_var, bit_map_props in bit_map_dict.items():
        if bit_map_props['output'] == 1:
            # Collect header info
            cur_var = bit_map_var
            cur_units = bit_map_props['units']
            cur_datablock = bit_map_props['datablock']
            cur_header = (cur_var, f"[{cur_units}]", f"[{cur_datablock}]")
            bit_map_headers.append(cur_header)
    return bit_map_headers


class ConvertData:
    """
    Read and convert binary data to ASCII, write to file
    """

    def __init__(self, binary_filename, size_header, dblocks, limit_read_lines, logger, file_number):
        self.tic = time.time()  # Start time
        self.binary_filename = binary_filename
        self.binary_filesize = os.path.getsize(self.binary_filename)
        self.size_header = size_header
        self.dblocks = dblocks
        self.limit_read_lines = limit_read_lines
        self.logger = logger
        self.file_counter_lines = 0
        self.file_total_bytes_read = 0
        self.file_data_rows = []  # Collects all data, i.e. all line records
        self.data_df = pd.DataFrame()
        # self.ascii_filename = outfile_ascii_path
        self.dblock_headers = []

        self.logger.info(f"    File size: {self.binary_filesize} Bytes")

    def run(self):
        self.open_binary = self.read_bin_file_to_mem(binary_filename=self.binary_filename, logger=self.logger)

        # First read binary header at top of file, but don't write to output file
        settings.data_blocks.header.wecom3.data_block_header(open_file_object=self.open_binary,
                                                             size_header=self.size_header)

        self.convert_to_ascii()

    def get_data(self):
        return self.dblock_headers, self.file_data_rows

    def write_multirow_header_to_ascii(self, asciiWriter):
        """Write header info from list of tuples to file as multi-row header

        Since self.dblock_headers is a list of tuples and the output ascii is
        written row-by-row, the header info is extracted from the list: each tuple
        in the list comprises three elements (variable name, units and instrument).
        Therefore, first the first element of each tuple (all variable names) is written
        to the first row of the file, then all second elements (units) are written to the
        second row, and finally the third elements (instrument) are written to the
        third row of the output file.

        """
        for headerrow in range(0, 3):
            headerrow_out = [i[headerrow] for i in self.dblock_headers]
            asciiWriter.writerow(headerrow_out)

    def convert_to_ascii(self):
        self.logger.info(f"    Reading file data, converting to ASCII ...")
        end_of_data_reached = False  # Reset for each file

        # with open(self.ascii_filename, 'w', newline='') as open_ascii:
        #     asciiWriter = csv.writer(open_ascii, delimiter=',')

        # File header
        self.dblock_headers = self.make_file_header()
        self.data_df = pd.DataFrame(columns=self.dblock_headers)
        # self.write_multirow_header_to_ascii(asciiWriter=asciiWriter)

        # Data records
        while not end_of_data_reached:
            # Read data blocks per instrument
            file_newrow_records = []
            for instr in self.dblocks:
                incoming_dblock_data, end_of_data_reached = self.read_instr_dblock(dblock=instr)
                if not end_of_data_reached:
                    file_newrow_records = file_newrow_records + incoming_dblock_data
                else:
                    file_newrow_records = False
                    break  # Breaks FOR loop

            if file_newrow_records:
                self.file_counter_lines += 1
                # asciiWriter.writerow(file_newrow_records)
                self.file_data_rows.append(file_newrow_records)
                self.data_df.append(file_newrow_records)

            # Limit = 0 means no limit
            if self.limit_read_lines > 0:
                if self.file_counter_lines == self.limit_read_lines:
                    break

        self.open_binary.close()
        # open_ascii.close()

        self.logger.info(f"    Finished conversion to ASCII.")
        # self.logger.info(f"    ASCII data saved to file {self.ascii_filename}")
        self.file_speedstats()

    def read_instr_dblock(self, dblock):
        """Cycle through vars in data block"""
        dblock_nominal_size, dblock_numvars = self.block_info(dblock=dblock)
        dblock_true_size = False  # Reset to False for each datablock
        dblock_data = []
        dblock_bytes_read = 0
        dblock_vars_read = 0
        end_of_data_reached = False

        for var, props in dblock.items():

            if 'bit_pos_start' in props.keys():  # Skip bit map variables, will be extracted later
                continue
            varbytes = self.open_binary.read(props['bytes'])  # Read Bytes for current var

            # Check if end of data
            end_of_data_reached = self.check_if_end_of_data(varbytes=varbytes,
                                                            required_varbytes=props['bytes'])
            if end_of_data_reached:
                break  # Stop for loop

            # Continue if bytes are available
            self.file_total_bytes_read += len(varbytes)  # Total bytes of data file
            dblock_bytes_read += len(varbytes)  # Bytes read for current instrument data block
            dblock_vars_read += 1

            # Get var value
            var_val = self.get_var_val(var=var, varbytes=varbytes,
                                       gain_on_signal=props['gain_on_signal'],
                                       offset_on_signal=props['offset_on_signal'],
                                       apply_gain=props['apply_gain'],
                                       add_offset=props['add_offset'],
                                       conversion_type=props['conversion_type'],
                                       datablock=props['datablock'],
                                       format=props['format'])

            # Check if variable gives data block size info
            if 'DATA_SIZE' in var:
                dblock_true_size = int(var_val)
                self.check_if_dblock_size_zero(dblock_true_size=dblock_true_size)
                if end_of_data_reached:
                    break  # Stop for loop

            # Check for missing or erroneous data blocks
            if dblock_true_size:
                # If datablock has the expected size, proceed normally
                if dblock_true_size == dblock_nominal_size:
                    pass
                # If datablock does not have the expected size, generate missing data
                elif dblock_bytes_read == 2:
                    # In this case there are analyzer data missing, i.e. the whole data block is either only 2 Bytes
                    # instead of e.g. 34 Bytes, or any other size, e.g. due to logging errors (e.g. the IRGA72 datablock
                    # can be 16 instead of 26). It is still necessary to read 2 Bytes in total. If the 2 Bytes were read,
                    # then stop this data block and return.

                    # Convert to hex or octal if needed
                    var_val = self.convert_val(units=props['units'], var_val=var_val)

                    # Add value to data
                    dblock_data.append(var_val)

                    # Missing values for missing main vars
                    dblock_data = self.set_vars_notread_to_missing(dblock_data_so_far=dblock_data,
                                                                   dblock_numvars=dblock_numvars,
                                                                   dblock_vars_read=dblock_vars_read)

                    # Add missing value -9999 for each of the bit map vars that was selected for output
                    dblock_data = self.set_extracted_vars_to_missing(dblock=dblock,
                                                                     dblock_data_so_far=dblock_data)

                    if dblock_true_size != 2:
                        self.read_rest_of_bytes(dblock_true_size=dblock_true_size,
                                                dblock_bytes_read=dblock_bytes_read)
                    break

            # Convert to hex or octal if needed
            var_val = self.convert_val(units=props['units'], var_val=var_val)

            # Add value to data
            dblock_data.append(var_val)

            # Extract variables from bit map
            if props['units'] == 'bit_map':
                bit_map_vals = self.extract_bit_map(var_val=var_val,
                                                    num_bytes=props['bytes'],
                                                    dblock=dblock)
                for bmv in bit_map_vals:
                    dblock_data.append(bmv)

        return dblock_data, end_of_data_reached

    def convert_val(self, units, var_val):
        """Convert var value to hex or octal"""
        if units == 'diag_val_hs':
            var_val = self.convert_val_to_diag_val_hs(var_val=var_val)
        if units == 'status_code_irga':
            var_val = self.convert_val_to_status_code_irga(var_val=var_val)
        if units == 'status_code_lgr':
            var_val = self.convert_val_to_status_code_lgr(var_val=var_val)
        return var_val

    @staticmethod
    def convert_val_to_diag_val_hs(var_val):
        """Convert value to diagnostic value for Gill HS-50 and HS-100 sonic anemometers

        Saved as an integer value. The integer can be converted to binary to get more
        information. Since the information in this variable is quite complex, please
        refer to the sonic anemometer manual for details.

        Examples:
            - var_val = 47.0, is converted to integer 47, this is the value that is
              then stored in the converted ASCII file.

        Notes:
            - The variable SA_DIAG_TYPE from the sonic HS anmometers gives info
              which type of information is given in SA_DIAG_VAL.
            - To get more information from the integer, it can be converted to
              binary, e.g. integer 47 becomes binary "0b101111"
              In Python, this can be done with bin(47) --> "0b101111"
            - The first two characters "0b" mean that this is binary format
            - The information is contained in "101111", it tells us which bits are
              set to 1 or 0. This can be interpreted using the sonic manual, there
              is a list what each bit set to 1 or 0 means.

        Returns: string
        """
        # hex_val = hex(int(var_val))  # Note: has hexadecimal prefix '0x' at start, e.g. '0x28'
        # hex_val_no_prefix = hex_val[2:]  # Remove hex prefix from val
        diag_val_hs = int(var_val)
        return diag_val_hs

    @staticmethod
    def convert_val_to_status_code_irga(var_val):
        """Convert value to octal

        Examples:
            - var_val = 0.0, is converted to integer 0,
                is converted to octal '0o0', is converted to octal without prefix '0'
        Returns: int
        """
        # if var_val != 0:
        #     print("x")
        var_val_int = int(var_val)  # Convert to integer
        # var_val_bin = bin(var_val_int)[2:]  # Convert to binary string
        # var_val_bin = var_val_bin.zfill(8)  # F
        # var_val_oct = int(var_val_bin, 8)  # Elegant way to convert binary string to octal
        # bin(int(var_val))[2:].zfill(16)
        oct_val = oct(var_val_int)  # Note: has octal prefix '0o' at start, e.g. '0o0'
        oct_val_no_prefix = oct_val[2:]  # Remove octal prefix from val
        return int(oct_val_no_prefix)

    @staticmethod
    def convert_val_to_status_code_lgr(var_val):
        """Convert value to status code for LGR laser analyzer

        Format for the LGR status code that is recorded in the raw binary files.

        Example:
            - var_val = 113.0
            - var_val_int = 113
            - var_val_bin = '0001'
            - status_code = 1
        Returns: int
        """
        # try:
        var_val_int = int(var_val)  # Convert to integer
        var_val_bin = bin(var_val_int)[-4:]  # Convert to binary string, relevant info is in last 4 bits
        status_code = int(var_val_bin, 2)  # Convert binary back to integer with base 2
        # var_val_oct = int(var_val_bin, 8)  # Elegant way to convert binary string to octal
        # except:
        #     print("X1")
        # else:
        #     var_val_oct = -9999
        # return var_val_int
        return status_code

    def extract_bit_map(self, var_val, num_bytes, dblock):
        """Extract multiple variables from one bit map variable"""
        var_binary_string = self.bit_map_var_to_bin(var_val=var_val, num_bytes=num_bytes)
        bit_map_dict = self.bit_map_get_vars(dblock=dblock)
        bit_map_vals = self.bit_map_extract_vals(bit_map_dict=bit_map_dict,
                                                 var_binary_string=var_binary_string)
        return bit_map_vals

    def read_rest_of_bytes(self, dblock_true_size, dblock_bytes_read):
        """Read rest of datablock bytes but do nothing with the data

        This happens when the datablock is not the nominal size (e.g. 26 for IRGA72)
        and also not 2 bytes (which would mean datablock is missing). This can happen
        e.g. for the IRGA72 that sometimes shows a datasize of 16 bytes due to
         inconsistencies in the logging script.
        """
        bytes_notread = dblock_true_size - dblock_bytes_read
        _varbytes = self.open_binary.read(bytes_notread)
        return None

    @staticmethod
    def set_extracted_vars_to_missing(dblock, dblock_data_so_far):
        """Add missing value -9999 for each of the bit map vars that was selected for output"""
        for var, props in dblock.items():
            if 'bit_pos_start' in props.keys():
                if props['output'] == 1:
                    dblock_data_so_far.append(-9999)
        return dblock_data_so_far

    @staticmethod
    def set_vars_notread_to_missing(dblock_data_so_far, dblock_numvars, dblock_vars_read):
        """Generate missing values for main vars that were not read"""
        vars_notread = dblock_numvars - dblock_vars_read
        for v in range(0, vars_notread):
            dblock_data_so_far.append(-9999)
        return dblock_data_so_far

    @staticmethod
    def check_if_dblock_size_zero(dblock_true_size):
        """Immediately stop if data block is zero bytes"""
        end_of_data_reached = True if dblock_true_size == 0 else False
        return end_of_data_reached

    def check_if_end_of_data(self, varbytes, required_varbytes):
        """Check if the end of available data is reached"""
        # Check if no more bytes available, True if length equals zero
        varbytes_zero = len(varbytes) == 0

        # Check if enough bytes for this var available, True if not enough bytes
        varbytes_not_enough_bytes = (len(varbytes) != 0) and (len(varbytes) < required_varbytes)

        if varbytes_zero | varbytes_not_enough_bytes:
            end_of_data_reached = True
        else:
            end_of_data_reached = False

        return end_of_data_reached

    def get_var_val(self, var, varbytes, gain_on_signal, offset_on_signal,
                    apply_gain, add_offset, conversion_type, datablock, format):
        dblock_struct = struct.Struct(format)  # Define format of read bytes
        dblock_unpacked = dblock_struct.unpack(varbytes)
        var_val = self.convert_bytes_to_value(unpacked_data=dblock_unpacked)

        if conversion_type == 'regular':
            var_val = self.remove_gain_offset(var_value=var_val,
                                              gain=gain_on_signal,
                                              offset=offset_on_signal)
            var_val = self.apply_gain_offset(var_value=var_val, gain=apply_gain, offset=add_offset)

        elif conversion_type == 'exception':
            if (datablock == 'R2-A') & (var == 'T_SONIC'):
                var_val = bce.dblock_r2a_t_sonic(var_val=var_val)

        else:
            var_val = '-conversion-type-not-defined-'
        return var_val

    @staticmethod
    def remove_gain_offset(var_value, gain, offset):
        """Remove gain by division and subtract offset"""
        return (var_value / gain) - offset

    @staticmethod
    def apply_gain_offset(var_value, gain, offset):
        """Apply gain by multiplication and add offset"""
        return (var_value * gain) + offset

    @staticmethod
    def convert_bytes_to_value(unpacked_data):
        """Convert multiple Bytes to one value, or use value from one Byte"""
        # based on: u = ((unpacked_data[0] * 256) + unpacked_data[1]) / 100
        if len(unpacked_data) > 1:
            length = len(unpacked_data) - 1
            power = list(range(length, -1, -1))
            power = [256 ** p for p in power]
            var_value = [unpacked_data[i] * power[i] for i in range(len(unpacked_data))]
            var_value = sum(var_value)
        else:
            var_value = unpacked_data[0]
        return var_value

    @staticmethod
    def bit_map_extract_vals(bit_map_dict, var_binary_string):
        """Extract bit map values from binary string"""
        bit_map_vals = []
        for bit_map_var, bit_map_props in bit_map_dict.items():
            if bit_map_props['output'] == 1:
                start = bit_map_props['bit_pos_start']
                end = bit_map_props['bit_pos_end']
                val = var_binary_string[start:end]
                val = int(str(val), 2)  # Convert binary string to integer with base 2
                val = val * bit_map_props['apply_gain']
                val = val + bit_map_props['add_offset']
                bit_map_vals.append(val)
        # print(bit_map_vals)
        return bit_map_vals

    @staticmethod
    def bit_map_var_to_bin(var_val, num_bytes):
        """Convert bit map var to 8-bit or 16-bit binary string"""
        var_binary_string = '-binary-string-empty-'
        if num_bytes == 2:
            # 16-bit binary string, yields e.g. '0001111111111111'
            var_binary_string = bin(int(var_val))[2:].zfill(16)
        if num_bytes == 1:
            # 8-bit binary string, yields e.g. '11111001'
            var_binary_string = bin(int(var_val))[2:].zfill(8)
        return var_binary_string

    @staticmethod
    def block_info(dblock):
        """Data block info: get nominal size in Bytes and number of vars"""
        dblock_nominal_size = 0
        dblock_numvars = 0
        for var, props in dblock.items():
            # Only count bytes of variables in original datastream, do not count extracted vars
            if 'bytes' in props.keys():
                dblock_nominal_size += props['bytes']
                dblock_numvars += 1
        return dblock_nominal_size, dblock_numvars

    @staticmethod
    def bit_map_get_vars(dblock):
        """Collect all bit map vars in separate dict"""
        bit_map_dict = {}
        for bit_map_var, bit_map_props in dblock.items():
            if 'bit_pos_start' in bit_map_props.keys():
                bit_map_dict[bit_map_var] = bit_map_props
        return bit_map_dict

    def make_file_header(self):
        """Make header for converted ASCII file, for all data blocks

        Returns list of tuples
        """
        dblock_headers = []
        for dblock in self.dblocks:
            dblock_header = make_header(dblock=dblock)
            for dblock_var in dblock_header:
                dblock_headers.append(dblock_var)
        return dblock_headers

    def read_bin_file_to_mem(self, binary_filename, logger):
        """Read binary file to memory

        This works much faster than previously.
        see: http://infinityquest.com/python-tutorials/memory-mapping-binary-files-python/
        """
        size = os.path.getsize(binary_filename)
        fd = os.open(binary_filename, os.O_RDONLY)
        open_binary = mmap.mmap(fd, size, access=mmap.ACCESS_READ)
        logger.info(f"    Done reading file to memory.")
        return open_binary

    def file_speedstats(self):
        toc = time.time() - self.tic
        try:
            runtime_line_avg = self.file_counter_lines / toc
        except ZeroDivisionError:
            runtime_line_avg = 0
        _len = f"    {self.file_counter_lines} rows read in {toc:.2f}s, speed: {int(runtime_line_avg)} rows s-1"
        self.logger.info(_len)

# def read_file(binary_filename, size_header, dblocks, limit_read_lines, logger, statusbar):
# binary_filesize = os.path.getsize(binary_filename)
# logger.info(f"    File size: {binary_filesize} Bytes")

# # File header
# # Make header for all data blocks
# dblock_headers = []
# for dblock in dblocks:
#     dblock_header = make_header(dblock=dblock)
#     for dblock_var in dblock_header:
#         dblock_headers.append(dblock_var)

# Open binary file
# tic = time.time()
# open_binary = read_bin_file_to_mem(binary_filename=binary_filename, logger=logger)
# counter_lines = 0
# total_bytes_read = 0
# data_rows = []  # Collects all data, i.e. all line records

# # First read header at top of file
# settings.data_blocks.header.wecom3.data_block_header(open_binary, size_header)

# Then loop through rest of binary file contents
# logger.info(f"    Reading file data, converting to ASCII ...")
# end_of_data_reached = False
# while not end_of_data_reached:
#     newdata_onerow_records = []
#     # Read data blocks per instrument
#     for instr in dblocks:
#         obj = ReadInstrDatablock(open_binary=open_binary,
#                                  dblock=instr,
#                                  total_bytes_read=total_bytes_read,
#                                  logger=logger)
#         newdata_instr, total_bytes_read, end_of_data_reached = obj.get_dblock_data()
#         # print(len(newdata_instr))
#
#         if not end_of_data_reached:
#             newdata_onerow_records = newdata_onerow_records + newdata_instr
#         else:
#             newdata_onerow_records = False
#             break  # Breaks FOR loop
#
#     if newdata_onerow_records:
#         counter_lines += 1
#         data_rows.append(newdata_onerow_records)
#         # Check if all bytes of current files were read
#         # if total_bytes_read >= binary_filesize:
#         #     print("X")
#
#         # # Info stats
#         # if counter_lines % 15000 == 0:
#         #     toc = time.time() - tic
#         #     time_per_byte = toc / total_bytes_read
#         #     bytes_not_read = binary_filesize - total_bytes_read
#         #     rem_time = bytes_not_read * time_per_byte
#         #     bytes_read_perc = (total_bytes_read / binary_filesize) * 100
#         #     print(f"\r    Read {counter_lines} lines / {total_bytes_read} Bytes ({bytes_read_perc:.1f}%) / "
#         #           f"time remaining: {rem_time:.1f}s ...", end='')
#
#     # Limit = 0 means no limit
#     if limit_read_lines > 0:
#         if counter_lines == limit_read_lines:
#             break

# open_binary.close()
# data_header = dblock_headers
# return data_rows, data_header, tic, counter_lines

# def generate_file_header(dblocks):
#     """Make header for converted output file"""
#     header = []
#     units = []
#     for instr in dblocks:
#         header += list(instr.keys())
#         for key, val in instr.items():
#             units += f"[{val['units']}]",
#     header = list(zip(header, units))  # List of tuples: header name and units
#     return header
#     # a= (instr.keys(), key = lambda x: (instr[x][by])


# # Info stats
# if counter_lines % 15000 == 0:
#     toc = time.time() - tic
#     time_per_byte = toc / total_bytes_read
#     bytes_not_read = binary_filesize - total_bytes_read
#     rem_time = bytes_not_read * time_per_byte
#     bytes_read_perc = (total_bytes_read / binary_filesize) * 100
#     print(f"\r    Read {counter_lines} lines / {total_bytes_read} Bytes ({bytes_read_perc:.1f}%) / "
#           f"time remaining: {rem_time:.1f}s ...", end='')
