import mmap
import os
import time

import numpy as np
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

    def __init__(self, binary_filename, size_header, dblocks, limit_read_lines, logger,
                 cur_file_number, progress_cb=None):
        self.tic = time.time()  # Start time
        # Optional callable(fraction) reporting how far through the file the row
        # conversion is (bytes read / file size). Used by the TUI for a live
        # per-file progress; None for the headless path.
        self._progress_cb = progress_cb
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

        # A flat, fixed-offset plan for the vectorized fast path (or None when the
        # format is not fast-eligible). When usable, the whole file is decoded with
        # numpy in a handful of array ops instead of the per-field Python loop.
        self._fast_plan = self._build_fast_plan()
        # Column arrays produced by the fast path; None means the slow path ran.
        self._fast_columns = None

        self.logger.info(f"    File size: {self.binary_filesize} Bytes")

    def run(self):
        self.open_binary = self.read_bin_file_to_mem(binary_filename=self.binary_filename, logger=self.logger)

        # First read binary header at top of file, but don't write to output file.
        # This advances the mmap read position to the start of the data region; the
        # fast path reads via the buffer protocol and does not disturb that position,
        # so a failed fast attempt can fall back to the sequential reader cleanly.
        wecom3.data_block_header(open_file_object=self.open_binary,
                                 size_header=self.size_header)

        if not self._try_fast_convert():
            self.convert_to_ascii()

    def get_data(self):
        # return self.data_df
        return self.dblock_headers, self.file_data_rows

    def get_dataframe(self, header):
        """Build the converted DataFrame with the given (possibly renamed) header.

        Uses the vectorized column arrays when the fast path ran, otherwise builds
        from the per-row records collected by the sequential reader. The header
        tuples must match the column order/count of either source (they do, since
        both follow ``make_file_header``).
        """
        self.logger.info("    Converting to dataframe ...")
        columns = pd.MultiIndex.from_tuples(header)
        if self._fast_columns is not None:
            # dict of {position: 1-D array} preserves each column's own dtype
            # (ints stay int, floats stay float), unlike a single 2-D block.
            data = {i: arr for i, arr in enumerate(self._fast_columns)}
            df = pd.DataFrame(data)
            df.columns = columns
            return df
        return pd.DataFrame(self.file_data_rows, columns=columns)

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
                # Report progress occasionally (every ~8192 rows) so the hot loop
                # stays cheap; fraction = bytes consumed / total file size.
                if self._progress_cb is not None and (self.file_counter_lines & 0x1FFF) == 0:
                    try:
                        self._progress_cb(self.file_total_bytes_read / self.binary_filesize)
                    except Exception:
                        pass

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

    def _build_fast_plan(self):
        """Flatten the per-datablock plans into a fixed-offset plan for numpy decode.

        Returns a dict describing every output column as a byte slice + conversion,
        plus the record stride and the DATA_SIZE fields used to confirm that all
        records are nominal-sized. Returns None when the format is not fast-eligible
        (an unknown conversion type, or the status_code_lgr quirk), in which case
        the sequential reader is used.
        """
        fields = []
        data_size_fields = []
        offset = 0
        for plan in self.dblock_plans:
            for vp in plan['var_plans']:
                ct = vp['conversion_type']
                if ct not in ('regular', 'exception'):
                    return None  # would yield a string sentinel; let slow path handle
                if vp['convert_kind'] == 'status_code_lgr':
                    return None  # fragile bin()[-4:] edge; not worth vectorizing
                field = {
                    'offset': offset,
                    'nbytes': vp['nbytes'],
                    'signed': vp['signed'],
                    'conversion_type': ct,
                    'gain_on_signal': vp['gain_on_signal'],
                    'offset_on_signal': vp['offset_on_signal'],
                    'apply_gain': vp['apply_gain'],
                    'add_offset': vp['add_offset'],
                    'convert_kind': vp['convert_kind'],
                    'is_exception_r2a_tsonic': vp['is_exception_r2a_tsonic'],
                    'is_bit_map': vp['is_bit_map'],
                    'bitmaps': [],
                }
                if vp['is_data_size']:
                    data_size_fields.append({'offset': offset, 'nbytes': vp['nbytes'],
                                             'nominal': plan['nominal_size']})
                if vp['is_bit_map']:
                    # Only output==1 bit-map vars become columns, in file order
                    # (same order make_header appends them).
                    for bp in plan['bit_map_dict'].values():
                        if bp['output'] == 1:
                            field['bitmaps'].append({
                                'bit_pos_start': bp['bit_pos_start'],
                                'bit_pos_end': bp['bit_pos_end'],
                                'apply_gain': bp['apply_gain'],
                                'add_offset': bp['add_offset'],
                            })
                fields.append(field)
                offset += vp['nbytes']
        return {'fields': fields, 'data_size_fields': data_size_fields, 'record_size': offset}

    @staticmethod
    def _decode_be(mat, offset, nbytes, signed):
        """Decode a big-endian integer column from the (nrows, record) byte matrix.

        Equivalent to ``int.from_bytes(bytes, 'big', signed=signed)`` applied per
        row, vectorized over all rows at once.
        """
        acc = np.zeros(mat.shape[0], dtype=np.int64)
        for k in range(nbytes):
            acc = (acc << 8) | mat[:, offset + k].astype(np.int64)
        if signed:
            bits = nbytes * 8
            acc = np.where(acc >= (1 << (bits - 1)), acc - (1 << bits), acc)
        return acc

    @staticmethod
    def _octal_as_decimal(arr):
        """Vectorized int(oct(n)[2:]): read n's octal digits as a base-10 number."""
        res = np.zeros_like(arr)
        mult = np.ones_like(arr)
        m = arr.copy()
        while np.any(m > 0):
            res = res + (m % 8) * mult
            mult = mult * 10
            m = m // 8
        return res

    def _try_fast_convert(self):
        """Decode the whole file with numpy when the format and data allow it.

        Returns True on success (``self._fast_columns`` is filled), or False to
        signal the caller to fall back to the sequential reader. Falls back when the
        format is not fast-eligible, the data region is not a whole number of
        nominal records, or any DATA_SIZE field shows a short/missing data block
        (which breaks the fixed-stride assumption).
        """
        fast = self._fast_plan
        if fast is None:
            return False
        rec = fast['record_size']
        if rec <= 0:
            return False

        data_bytes = self.binary_filesize - self.size_header
        if data_bytes < rec:
            return False
        nrows = data_bytes // rec
        if self.limit_read_lines > 0:
            nrows = min(nrows, self.limit_read_lines)
        if nrows <= 0:
            return False

        buf = np.frombuffer(self.open_binary, dtype=np.uint8,
                            count=nrows * rec, offset=self.size_header)
        mat = buf.reshape(nrows, rec)

        # Confirm every record is nominal-sized; a short block would shift all
        # following fields, so we bail to the sequential reader instead.
        for ds in fast['data_size_fields']:
            raw = self._decode_be(mat, ds['offset'], ds['nbytes'], signed=False)
            if not np.all(raw == ds['nominal']):
                return False

        columns = []
        for f in fast['fields']:
            raw = self._decode_be(mat, f['offset'], f['nbytes'], f['signed'])
            ct = f['conversion_type']
            if ct == 'regular':
                val = (raw / f['gain_on_signal']) - f['offset_on_signal']
                val = (val * f['apply_gain']) + f['add_offset']
            else:  # 'exception'
                if f['is_exception_r2a_tsonic']:
                    v = raw * 0.02
                    v = v * v
                    v = v / 403
                    v = v - 273.15
                    val = v
                else:
                    val = raw  # identity exception keeps the raw integer

            convert_kind = f['convert_kind']
            if convert_kind == 'diag_val_hs':
                col = val.astype(np.int64)
            elif convert_kind == 'status_code_irga':
                col = self._octal_as_decimal(val.astype(np.int64))
            else:
                col = val
            columns.append(col)

            if f['is_bit_map']:
                src = val.astype(np.int64)  # int(var_val), as the slow path does
                width = f['nbytes'] * 8
                for bm in f['bitmaps']:
                    shift = width - bm['bit_pos_end']
                    mask = (1 << (bm['bit_pos_end'] - bm['bit_pos_start'])) - 1
                    ext = (src >> shift) & mask
                    # Scalars carry the dtype: int gain/offset -> int column,
                    # float gain/offset -> float column, matching the slow path.
                    ext = ext * bm['apply_gain'] + bm['add_offset']
                    columns.append(ext)

        self.dblock_headers = self.make_file_header()
        if len(columns) != len(self.dblock_headers):
            # Defensive: header/column mismatch means our offset model is wrong.
            return False

        self._fast_columns = columns
        self.file_counter_lines = nrows
        self.file_total_bytes_read = nrows * rec
        if self._progress_cb is not None:
            try:
                self._progress_cb(1.0)
            except Exception:
                pass
        # The decoded columns are independent arrays, but ``buf``/``mat`` are views
        # into the mmap; drop them so the mmap has no exported pointers and can close.
        del mat, buf
        self.open_binary.close()
        self.logger.info("    Reading file data, converting to ASCII (vectorized) ...")
        self.logger.info("    Finished conversion to ASCII.")
        self.file_speedstats()
        return True

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
