import mmap
import os
import struct
import time

import settings.data_blocks.header.wecom3


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

    # Get header for all data blocks
    dblock_headers = []
    for dblock in dblocks:
        dblock_header = make_header(dblock=dblock)
        for dblock_var in dblock_header:
            dblock_headers.append(dblock_var)

    # # Number of records per line
    # nominal_line_records = expected_records_per_line(dblocks=dblocks)

    # Open binary file
    tic = time.time()
    open_binary = read_bin_file_to_mem(binary_filename=binary_filename, logger=logger)
    counter_lines = 0
    total_bytes_read = 0
    data_rows = []  # Collects all data, i.e. all line records

    # First read header at top of file
    settings.data_blocks.header.wecom3.data_block_header(open_binary, size_header)

    # Then loop through rest of binary file contents
    while 1:
        newdata_onerow_records = []

        # Read data blocks per instrument
        for instr in dblocks:

            newdata_instr, total_bytes_read, end_of_data_reached = \
                read_bin_instr(open_binary=open_binary,
                               dblock=instr,
                               total_bytes_read=total_bytes_read,
                               logger=logger)

            if not end_of_data_reached:
                newdata_onerow_records = newdata_onerow_records + newdata_instr
            else:
                newdata_onerow_records = False
                break  # Breaks FOR loop

        if newdata_onerow_records:
            counter_lines += 1
            data_rows.append(newdata_onerow_records)
            if counter_lines % 25000 == 0:
                toc = time.time() - tic
                time_per_byte = toc / total_bytes_read
                bytes_not_read = binary_filesize - total_bytes_read
                rem_time = bytes_not_read * time_per_byte
                bytes_read_perc = (total_bytes_read / binary_filesize) * 100
                print(f"\r    Read {counter_lines} lines / {total_bytes_read} Bytes ({bytes_read_perc:.1f}%) / "
                      f"time remaining: {rem_time:.1f}s ...", end='')

        else:
            break  # Breaks WHILE loop

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


def bit_map_get_vars(dblock):
    """Collect all bit map vars in separate dict"""
    bit_map_dict = {}
    for bit_map_var, bit_map_props in dblock.items():
        if 'bit_pos_start' in bit_map_props.keys():
            bit_map_dict[bit_map_var] = bit_map_props
    return bit_map_dict


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
    return bit_map_vals


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
            bit_map_dict = bit_map_get_vars(dblock=dblock)
            bit_map_headers = bit_map_extract_header(bit_map_dict=bit_map_dict)
            for bmh in bit_map_headers:
                dblock_header.append(bmh)
    return dblock_header


def read_bin_instr(open_binary, dblock, total_bytes_read, logger):
    """Read data block of current instrument"""
    end_of_data_reached = False
    dblock_true_size = False
    dblock_data = []
    dblock_bytes_read = 0
    dblock_vars_read = 0

    dblock_nominal_size, dblock_numvars = block_info(dblock=dblock)

    for var, props in dblock.items():

        # Skip bit map variables
        if 'bit_pos_start' in props.keys():
            continue

        # Read Bytes for current var
        varbytes = open_binary.read(props['bytes'])

        # Check if Bytes for this var available
        zero_bytes = len(varbytes) == 0  # True if length equals zero
        not_enough_bytes = (len(varbytes) != 0) and (len(varbytes) < props['bytes'])  # True if not enough bytes
        if zero_bytes or not_enough_bytes:
            msg = ""
            if zero_bytes:
                msg = f"\n    (!)WARNING: Zero bytes available."
            if not_enough_bytes:
                msg = f"\n    (!)WARNING:\n" \
                      f"        {props['bytes']} bytes needed for {var} data but only {len(varbytes)} bytes available\n"
            msg = msg + "        Reached end of data."
            logger.info(msg)
            dblock_data = generate_missing_values(dict=dblock)
            end_of_data_reached = True
            return dblock_data, total_bytes_read, end_of_data_reached

        # Continue if var available
        total_bytes_read += len(varbytes)  # Total bytes of data file
        dblock_bytes_read += len(varbytes)  # Bytes read for current instrument data block
        dblock_vars_read += 1

        # Get var value
        dblock_struct = struct.Struct(props['format'])  # Define format of read bytes
        dblock_unpacked = dblock_struct.unpack(varbytes)

        var_val = convert_bytes_to_value(unpacked_data=dblock_unpacked)
        var_val = remove_gain_offset(var_value=var_val, gain=props['gain_on_signal'], offset=props['offset_on_signal'])
        var_val = apply_gain_offset(var_value=var_val, gain=props['apply_gain'], offset=props['add_offset'])

        # Convert to hex if needed
        if props['units'] == 'hexadecimal_value':
            var_val = convert_val_to_hex(var_val=var_val)
        # Convert to octal if needed
        if props['units'] == 'octal':
            var_val = convert_val_to_octal(var_val=var_val)

        # Check if size info available
        if 'DATA_SIZE' in var:
            dblock_true_size = int(var_val)
            # if dblock_true_size == 16:
            #     print(dblock_true_size)

        # Extract variables from bit map
        bit_map_vals = []
        if props['units'] == 'bit_map':
            var_binary_string = bit_map_var_to_bin(var_val=var_val, num_bytes=props['bytes'])
            bit_map_dict = bit_map_get_vars(dblock=dblock)
            bit_map_vals = bit_map_extract_vals(bit_map_dict=bit_map_dict,
                                                var_binary_string=var_binary_string)

        if dblock_true_size:
            if dblock_true_size == dblock_nominal_size:
                # Full datablock available
                pass

            elif dblock_bytes_read == 2:
                # In this case there are analyzer data missing, i.e. the whole data block is either only 2 Bytes
                # instead of e.g. 34 Bytes, or any other size, e.g. due to logging errors (e.g. the IRGA72 datablock
                # can be 16 instead of 26). It is still necessary to read 2 Bytes in total. If the 2 Bytes were read,
                # then stop this data block and return.
                dblock_data.append(var_val)
                vars_notread = dblock_numvars - dblock_vars_read
                for v in range(0, vars_notread):
                    dblock_data.append(-9999)

                if dblock_true_size != 2:
                    # Read rest of dblock but do nothing with data. This happens when the datablock is not the
                    # nominal size (e.g. 26 for IRGA72) and also not 2 bytes (which would mean datablock is
                    # missing). This can happen e.g. for the IRGA72 that sometimes shows a datasize of 16 bytes
                    # due to inconsistencies in the logging script.

                    # Add missing value -9999 for each of the bit map vars that was selected for output
                    for var, props in dblock.items():
                        if 'bit_pos_start' in props.keys():
                            if props['output'] == 1:
                                dblock_data.append(-9999)

                    # Read rest of bytes
                    bytes_notread = dblock_true_size - dblock_bytes_read
                    _varbytes = open_binary.read(bytes_notread)

                return dblock_data, total_bytes_read, end_of_data_reached

            # elif (dblock_true_size == 2) and (dblock_bytes_read == 2):
            #     # dblock_data.append(var_val)
            #     # vars_notread = dblock_numvars - dblock_vars_read
            #     # for v in range(0, vars_notread):
            #     #     dblock_data.append(-9999)
            #     return dblock_data, total_bytes_read, end_of_data_reached
            #
            # elif (dblock_true_size != 2) and (dblock_bytes_read == 2):
            #     # dblock_data.append(var_val)
            #     # vars_notread = dblock_numvars - dblock_vars_read
            #     # for v in range(0, vars_notread):
            #     #     dblock_data.append(-9999)
            #     # bytes_notread = dblock_true_size - dblock_bytes_read
            #     # _varbytes = open_binary.read(bytes_notread)  # Read rest of dblock but do nothing with data
            #     return dblock_data, total_bytes_read, end_of_data_reached

        # Add value to data
        dblock_data.append(var_val)

        # Add vars extracted from bit map
        if props['units'] == 'bit_map':
            for bmv in bit_map_vals:
                dblock_data.append(bmv)

    return dblock_data, total_bytes_read, end_of_data_reached


def convert_val_to_hex(var_val):
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
    # if hex_val_no_prefix == '3c':
    #     print("X")
    return hex_val_no_prefix

def convert_val_to_octal(var_val):
    """Convert value to octal

    Examples:
        - var_val = 0.0, is converted to integer 0,
            is converted to octal '0o0', is converted to octal without prefix '0'
    Returns: int
    """
    oct_val = oct(int(var_val))  # Note: has octal prefix '0o' at start, e.g. '0o0'
    oct_val_no_prefix = oct_val[2:]  # Remove octal prefix from val
    return int(oct_val_no_prefix)


def generate_missing_values(dict):
    missing_vals = []
    for v in dict.items():
        var_val = -9999
        missing_vals.append(var_val)  # Set each var in data block to missing -9999
    return missing_vals


def expected_records_per_line(dblocks):
    # Expected records per line
    nominal_line_records = []
    for d in dblocks:
        missing_vals = generate_missing_values(dict=d)
        nominal_line_records += missing_vals
    return len(nominal_line_records)


def remove_gain_offset(var_value, gain, offset):
    """Remove gain by division and subtract offset"""
    return (var_value / gain) - offset


def apply_gain_offset(var_value, gain, offset):
    """Apply gain by multiplication and add offset"""
    return (var_value * gain) + offset


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


def generate_header(dblocks):
    """Make header for converted output file"""
    header = []
    units = []
    for instr in dblocks:
        header += list(instr.keys())
        for key, val in instr.items():
            units += f"[{val['units']}]",
    header = list(zip(header, units))  # List of tuples: header name and units
    return header
    # a= (instr.keys(), key = lambda x: (instr[x][by])
