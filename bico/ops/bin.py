import mmap
import os
import time

import pandas as pd

from bico.settings.data_blocks.header import wecom3
from . import bin_conversion_exceptions as bce


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

    def __init__(self, binary_filename, size_header, dblocks, limit_read_lines, logger, cur_file_number):
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
        self.cur_file_number = cur_file_number

        # Precompute per-datablock conversion plans once (structs, sizes, flags),
        # so the hot per-row loop does not recompute constant metadata.
        self.dblock_plans = self._prepare_plans(dblocks)

        self.logger.info(f"    File size: {self.binary_filesize} Bytes")

    def run(self):
        self.open_binary = self.read_bin_file_to_mem(binary_filename=self.binary_filename, logger=self.logger)

        # First read binary header at top of file, but don't write to output file
        wecom3.data_block_header(open_file_object=self.open_binary,
                                 size_header=self.size_header)

        self.convert_to_ascii()

    def get_data(self):
        # return self.data_df
        return self.dblock_headers, self.file_data_rows

    def convert_to_ascii(self):
        self.logger.info(f"    Reading file data, converting to ASCII ...")
        end_of_data_reached = False  # Reset for each file

        # File header
        self.dblock_headers = self.make_file_header()

        # Data records
        while not end_of_data_reached:
            # Read data blocks per instrument
            file_newrow_records = []
            _end_of_data_reached = []

            onerow_records = [self.read_instr_dblock(plan=p) for p in self.dblock_plans]
            for dblock_records in onerow_records:
                file_newrow_records.extend(dblock_records[0])
                _end_of_data_reached.append(dblock_records[1])
            if True in _end_of_data_reached:
                end_of_data_reached = True
                file_newrow_records = False

            if file_newrow_records:
                self.file_counter_lines += 1
                self.file_data_rows.append(file_newrow_records)

            # Limit = 0 means no limit
            if self.limit_read_lines > 0:
                if self.file_counter_lines == self.limit_read_lines:
                    break

        self.open_binary.close()

        self.logger.info(f"    Finished conversion to ASCII.")
        self.file_speedstats()

    def _prepare_plans(self, dblocks):
        """Precompute a conversion plan per data block.

        The per-row conversion loop is the performance bottleneck, so anything
        constant per data block is computed once here instead of on every row:
        the nominal block size and variable count, the signed/unsigned decode
        flag per variable, the bit map dict, and the per-variable conversion
        flags. Produces results identical to the original per-row logic, just
        without the repeated work.
        """
        plans = []
        for dblock in dblocks:
            var_plans = []
            nominal_size = 0
            numvars = 0
            for name, props in dblock.items():
                if 'bit_pos_start' in props:  # Bit map var, extracted later, not read from stream
                    continue
                nbytes = props['bytes']
                nominal_size += nbytes
                numvars += 1
                # The .dblock formats are big-endian byte values: unsigned bytes (`B`,
                # combined big-endian) except the signed short `>h`. convert_bytes_to_value
                # recombined them as a base-256 integer, which is exactly int.from_bytes(.., 'big').
                signed = 'h' in props['format']
                units = props['units']
                conversion_type = props['conversion_type']
                convert_kind = units if units in ('diag_val_hs', 'status_code_irga',
                                                   'status_code_lgr') else None
                var_plans.append({
                    'name': name,
                    'nbytes': nbytes,
                    'signed': signed,
                    'conversion_type': conversion_type,
                    'gain_on_signal': props['gain_on_signal'],
                    'offset_on_signal': props['offset_on_signal'],
                    'apply_gain': props['apply_gain'],
                    'add_offset': props['add_offset'],
                    'units': units,
                    'is_data_size': 'DATA_SIZE' in name,
                    'is_bit_map': units == 'bit_map',
                    'convert_kind': convert_kind,
                    'is_exception_r2a_tsonic': (conversion_type == 'exception'
                                                and props['datablock'] == 'R2-A'
                                                and name == 'T_SONIC'),
                })
            bit_map_dict = self.bit_map_get_vars(dblock=dblock)
            bitmap_output_count = sum(1 for p in bit_map_dict.values() if p['output'] == 1)
            plans.append({
                'nominal_size': nominal_size,
                'numvars': numvars,
                'var_plans': var_plans,
                'bit_map_dict': bit_map_dict,
                'bitmap_output_count': bitmap_output_count,
            })
        return plans

    @staticmethod
    def _get_var_val_fast(vp, varbytes):
        """get_var_val using int.from_bytes (C-level big-endian decode)"""
        var_val = int.from_bytes(varbytes, 'big', signed=vp['signed'])

        conversion_type = vp['conversion_type']
        if conversion_type == 'regular':
            var_val = (var_val / vp['gain_on_signal']) - vp['offset_on_signal']
            var_val = (var_val * vp['apply_gain']) + vp['add_offset']
        elif conversion_type == 'exception':
            if vp['is_exception_r2a_tsonic']:
                var_val = bce.dblock_r2a_t_sonic(var_val=var_val)
        else:
            var_val = '-conversion-type-not-defined-'
        return var_val

    @staticmethod
    def _convert_val_fast(vp, var_val):
        """convert_val branch selected once per variable via precomputed flag"""
        convert_kind = vp['convert_kind']
        if convert_kind is None:
            return var_val
        if convert_kind == 'diag_val_hs':
            return int(var_val)
        if convert_kind == 'status_code_irga':
            return int(oct(int(var_val))[2:])  # octal without '0o' prefix
        # status_code_lgr: relevant info is in last 4 bits
        return int(bin(int(var_val))[-4:], 2)

    def _extract_bit_map_fast(self, var_val, num_bytes, bit_map_dict):
        """extract_bit_map using the precomputed bit map dict"""
        var_binary_string = self.bit_map_var_to_bin(var_val=var_val, num_bytes=num_bytes)
        return self.bit_map_extract_vals(bit_map_dict=bit_map_dict, var_binary_string=var_binary_string)

    def read_instr_dblock(self, plan):
        """Cycle through vars in data block (optimized, uses a precomputed plan)"""
        dblock_nominal_size = plan['nominal_size']
        dblock_numvars = plan['numvars']
        bit_map_dict = plan['bit_map_dict']
        dblock_true_size = False  # Reset to False for each datablock
        dblock_data = []
        dblock_bytes_read = 0
        dblock_vars_read = 0
        end_of_data_reached = False
        read = self.open_binary.read

        for vp in plan['var_plans']:
            nbytes = vp['nbytes']
            varbytes = read(nbytes)  # Read Bytes for current var
            nread = len(varbytes)

            # Check if end of data (no bytes, or not enough bytes for this var)
            if nread < nbytes:
                end_of_data_reached = True
                break  # Stop for loop

            # Continue if bytes are available
            self.file_total_bytes_read += nread  # Total bytes of data file
            dblock_bytes_read += nread  # Bytes read for current instrument data block
            dblock_vars_read += 1

            # Get var value
            var_val = self._get_var_val_fast(vp, varbytes)

            # Check if variable gives data block size info
            if vp['is_data_size']:
                dblock_true_size = int(var_val)
                if dblock_true_size == 0:  # Immediately stop if data block is zero bytes
                    end_of_data_reached = True
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
                    var_val = self._convert_val_fast(vp, var_val)

                    # Add value to data
                    dblock_data.append(var_val)

                    # Missing values for missing main vars
                    for _ in range(dblock_numvars - dblock_vars_read):
                        dblock_data.append(-9999)

                    # Add missing value -9999 for each of the bit map vars that was selected for output
                    for _ in range(plan['bitmap_output_count']):
                        dblock_data.append(-9999)

                    if dblock_true_size != 2:
                        self.read_rest_of_bytes(dblock_true_size=dblock_true_size,
                                                dblock_bytes_read=dblock_bytes_read)
                    break

            # Convert if needed
            var_val = self._convert_val_fast(vp, var_val)

            # Add value to data
            dblock_data.append(var_val)

            # Extract variables from bit map
            if vp['is_bit_map']:
                dblock_data.extend(self._extract_bit_map_fast(var_val, nbytes, bit_map_dict))

        # return dblock_data
        return dblock_data, end_of_data_reached

    def read_rest_of_bytes(self, dblock_true_size, dblock_bytes_read):
        """Read rest of datablock bytes but do nothing with the data

        This happens when the datablock is not the nominal size (e.g. 26 for IRGA72)
        and also not 2 bytes (which would mean datablock is missing). This can happen
        e.g. for the IRGA72 that sometimes shows a datasize of 16 bytes due to
         inconsistencies in the logging script.
        """
        bytes_notread = dblock_true_size - dblock_bytes_read
        # bytes_notread = 0  # for testing
        _varbytes = self.open_binary.read(bytes_notread)
        return None

    @staticmethod
    def bit_map_extract_vals(bit_map_dict, var_binary_string):
        """Extract bit map values from binary string"""
        bit_map_vals = []
        for bit_map_var, bit_map_props in bit_map_dict.items():
            if bit_map_props['output'] == 1:
                start = bit_map_props['bit_pos_start']
                end = bit_map_props['bit_pos_end']
                val = var_binary_string[start:end]
                try:
                    val = int(str(val), 2)  # Convert binary string to integer with base 2
                    val = val * bit_map_props['apply_gain']
                    val = val + bit_map_props['add_offset']
                except ValueError as e:
                    val = -9999
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
        _len = f"    {self.file_counter_lines} data rows converted in {toc:.2f}s, speed: {int(runtime_line_avg)} rows s-1"
        self.logger.info(_len)
