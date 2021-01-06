import mmap
import os
import struct
import time

import settings.data_blocks.header.wecom3


class ReadInstrDatablock:
    """Read datablock of instrument"""

    def __init__(self, open_binary, dblock, total_bytes_read, logger):
        self.open_binary = open_binary
        self.dblock = dblock
        self.total_bytes_read = total_bytes_read
        self.logger = logger

        self.end_of_data_reached = False
        self.dblock_true_size = False
        self.dblock_data = []
        self.dblock_bytes_read = 0
        self.dblock_vars_read = 0
        self.dblock_nominal_size, \
        self.dblock_numvars = self.block_info(dblock=self.dblock)
        self.dblock_true_size = False  # Reset to False for each datablock

        self.loop_dblock()

    def get_dblock_data(self):
        return self.dblock_data, self.total_bytes_read, self.end_of_data_reached

    def loop_dblock(self):
        """Cycle through vars in data block"""
        for var, props in self.dblock.items():

            if 'bit_pos_start' in props.keys():  # Skip bit map variables, will be extracted later
                continue
            varbytes = self.open_binary.read(props['bytes'])  # Read Bytes for current var

            # Check if end of data
            self.end_of_data_reached = self.check_if_end_of_data(varbytes=varbytes,
                                                                 required_varbytes=props['bytes'])
            if self.end_of_data_reached:
                break  # Stop for loop

            # Continue if bytes are available
            self.total_bytes_read += len(varbytes)  # Total bytes of data file
            self.dblock_bytes_read += len(varbytes)  # Bytes read for current instrument data block
            self.dblock_vars_read += 1

            # Get var value
            var_val = self.get_var_val(props=props, varbytes=varbytes)

            # Check if variable gives data block size info
            if 'DATA_SIZE' in var:
                self.dblock_true_size = int(var_val)
                self.check_if_dblock_size_zero()
                if self.end_of_data_reached:
                    break  # Stop for loop

            # Check for missing or erroneous data blocks
            if self.dblock_true_size:
                # If datablock has the expected size, proceed normally
                if self.dblock_true_size == self.dblock_nominal_size:
                    pass

                # If datablock does not have the expected size, generate missing data
                elif self.dblock_bytes_read == 2:
                    # In this case there are analyzer data missing, i.e. the whole data block is either only 2 Bytes
                    # instead of e.g. 34 Bytes, or any other size, e.g. due to logging errors (e.g. the IRGA72 datablock
                    # can be 16 instead of 26). It is still necessary to read 2 Bytes in total. If the 2 Bytes were read,
                    # then stop this data block and return.

                    # Convert to hex or octal if needed
                    var_val = self.convert_val(props=props, var_val=var_val)

                    # Add value to data
                    self.dblock_data.append(var_val)

                    # Missing values for missing main vars
                    self.dblock_data = self.set_vars_notread_to_missing(dblock_data_so_far=self.dblock_data)

                    # Add missing value -9999 for each of the bit map vars that was selected for output
                    self.dblock_data = self.set_extracted_vars_to_missing(dblock_data_so_far=self.dblock_data)

                    if self.dblock_true_size != 2:
                        self.read_rest_of_bytes()

                    break

                    # return self.dblock_data, self.total_bytes_read, self.end_of_data_reached

                # Convert to hex or octal if needed
                var_val = self.convert_val(props=props, var_val=var_val)

            # Add value to data
            self.dblock_data.append(var_val)

            # Extract variables from bit map
            if props['units'] == 'bit_map':
                bit_map_vals = self.extract_bit_map(var_val=var_val,
                                                    props=props,
                                                    dblock=self.dblock)
                for bmv in bit_map_vals:
                    self.dblock_data.append(bmv)

            # return self.dblock_data, self.total_bytes_read, self.end_of_data_reached

    def convert_val(self, props, var_val):
        """Convert var value to hex or octal"""
        # Convert to hex
        if props['units'] == 'hexadecimal_value':
            var_val = self.convert_val_to_hex(var_val=var_val)
        # Convert to octal
        if props['units'] == 'status_code_irga':
            var_val = self.convert_val_to_status_code_irga(var_val=var_val)
        # Convert to octal for LGR laser analyzer
        if props['units'] == 'status_code_lgr':
            var_val = self.convert_val_to_status_code_lgr(var_val=var_val)
        return var_val

    def convert_val_to_hex(self, var_val):
        """Convert value to hexadecimal

        Examples:
            - var_val = 40.0, is converted to integer 40,
                is converted to hex '0x28', is converted to hex without prefix '28'
            - var_val = 60.0, is converted to integer 60,
                is converted to hex '0x3c', is converted to hex without prefix '3c'
        Returns: string
        """
        hex_val = hex(int(var_val))  # Note: has hexadecimal prefix '0x' at start, e.g. '0x28'
        hex_val_no_prefix = hex_val[2:]  # Remove hex prefix from val
        return hex_val_no_prefix

    def convert_val_to_status_code_irga(self, var_val):
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

    def convert_val_to_status_code_lgr(self, var_val):
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

    def extract_bit_map(self, var_val, props, dblock):
        """Extract multiple variables from one bit map variable"""
        var_binary_string = self.bit_map_var_to_bin(var_val=var_val, num_bytes=props['bytes'])
        bit_map_dict = self.bit_map_get_vars(dblock=dblock)
        bit_map_vals = self.bit_map_extract_vals(bit_map_dict=bit_map_dict,
                                                 var_binary_string=var_binary_string)
        return bit_map_vals

    def read_rest_of_bytes(self):
        """Read rest of datablock bytes but do nothing with the data

        This happens when the datablock is not the nominal size (e.g. 26 for IRGA72)
        and also not 2 bytes (which would mean datablock is missing). This can happen
        e.g. for the IRGA72 that sometimes shows a datasize of 16 bytes due to
         inconsistencies in the logging script.
        """
        bytes_notread = self.dblock_true_size - self.dblock_bytes_read
        _varbytes = self.open_binary.read(bytes_notread)
        return None

    def set_extracted_vars_to_missing(self, dblock_data_so_far):
        """Add missing value -9999 for each of the bit map vars that was selected for output"""
        for var, props in self.dblock.items():
            if 'bit_pos_start' in props.keys():
                if props['output'] == 1:
                    dblock_data_so_far.append(-9999)
        return dblock_data_so_far

    def set_vars_notread_to_missing(self, dblock_data_so_far):
        """Generate missing values for main vars that were not read"""
        vars_notread = self.dblock_numvars - self.dblock_vars_read
        for v in range(0, vars_notread):
            dblock_data_so_far.append(-9999)
        return dblock_data_so_far

    def check_if_dblock_size_zero(self):
        """Immediately stop if data block is zero bytes"""
        end_of_data_reached = True if self.dblock_true_size == 0 else False
        return end_of_data_reached
        # self.dblock_data = self.set_datablock_to_missing()
        # else:
        #     end_of_data_reached = False
        # return dblock_data, end_of_data_reached

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

    def set_datablock_to_missing(self):
        """Set the complete datablock to missing values"""
        dblock_data = []

        # Set each var in data block to missing -9999
        for v in self.dblock.items():
            var_val = -9999
            dblock_data.append(var_val)

        # Set each extracted bit map var to missing -9999
        dblock_data = self.set_extracted_vars_to_missing(dblock_data_so_far=dblock_data)

        return dblock_data

    def get_var_val(self, props, varbytes):
        dblock_struct = struct.Struct(props['format'])  # Define format of read bytes
        dblock_unpacked = dblock_struct.unpack(varbytes)
        var_val = self.convert_bytes_to_value(unpacked_data=dblock_unpacked)
        var_val = self.remove_gain_offset(var_value=var_val, gain=props['gain_on_signal'],
                                          offset=props['offset_on_signal'])
        var_val = self.apply_gain_offset(var_value=var_val, gain=props['apply_gain'], offset=props['add_offset'])
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
            bit_map_dict = ReadInstrDatablock.bit_map_get_vars(dblock=dblock)
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


def read_bin_file_to_mem(binary_filename, logger):
    """Read binary file to memory

    This works much faster than previously.
    see: http://infinityquest.com/python-tutorials/memory-mapping-binary-files-python/
    """
    size = os.path.getsize(binary_filename)
    fd = os.open(binary_filename, os.O_RDONLY)
    open_binary = mmap.mmap(fd, size, access=mmap.ACCESS_READ)
    logger.info(f"    Done reading file to memory.")
    return open_binary


def read_file(binary_filename, size_header, dblocks, limit_read_lines, logger, statusbar):
    binary_filesize = os.path.getsize(binary_filename)
    logger.info(f"    File size: {binary_filesize} Bytes")

    # File header
    # Make header for all data blocks
    dblock_headers = []
    for dblock in dblocks:
        dblock_header = make_header(dblock=dblock)
        for dblock_var in dblock_header:
            dblock_headers.append(dblock_var)

    # Open binary file
    tic = time.time()
    open_binary = read_bin_file_to_mem(binary_filename=binary_filename, logger=logger)
    counter_lines = 0
    total_bytes_read = 0
    data_rows = []  # Collects all data, i.e. all line records

    # First read header at top of file
    settings.data_blocks.header.wecom3.data_block_header(open_binary, size_header)

    # Then loop through rest of binary file contents
    logger.info(f"    Reading file data, converting to ASCII ...")
    end_of_data_reached = False
    while not end_of_data_reached:
        newdata_onerow_records = []
        # Read data blocks per instrument
        # if counter_lines == 34227:
        #     print("34227")
        # print(counter_lines)
        for instr in dblocks:
            obj = ReadInstrDatablock(open_binary=open_binary,
                                     dblock=instr,
                                     total_bytes_read=total_bytes_read,
                                     logger=logger)
            newdata_instr, total_bytes_read, end_of_data_reached = obj.get_dblock_data()
            # print(len(newdata_instr))

            if not end_of_data_reached:
                newdata_onerow_records = newdata_onerow_records + newdata_instr
            else:
                newdata_onerow_records = False
                break  # Breaks FOR loop

        if newdata_onerow_records:
            counter_lines += 1
            data_rows.append(newdata_onerow_records)
            # Check if all bytes of current files were read
            # if total_bytes_read >= binary_filesize:
            #     print("X")

            # # Info stats
            # if counter_lines % 15000 == 0:
            #     toc = time.time() - tic
            #     time_per_byte = toc / total_bytes_read
            #     bytes_not_read = binary_filesize - total_bytes_read
            #     rem_time = bytes_not_read * time_per_byte
            #     bytes_read_perc = (total_bytes_read / binary_filesize) * 100
            #     print(f"\r    Read {counter_lines} lines / {total_bytes_read} Bytes ({bytes_read_perc:.1f}%) / "
            #           f"time remaining: {rem_time:.1f}s ...", end='')

        # Limit = 0 means no limit
        if limit_read_lines > 0:
            if counter_lines == limit_read_lines:
                break

    open_binary.close()
    data_header = dblock_headers
    return data_rows, data_header, tic, counter_lines


def speedstats(tic, counter_lines, logger):
    toc = time.time() - tic
    try:
        runtime_line_avg = counter_lines / toc
    except ZeroDivisionError:
        runtime_line_avg = 0
    _len = f"    {counter_lines} lines read in {toc:.2f}s, speed: {int(runtime_line_avg)} lines s-1"
    logger.info(_len)

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
