def prepare_var_settings(data_block):
    vars_in_order = _sort_by_subdict(dict=data_block, by='order')
    # data_block = _calc_var_byte_pos(sorted_list=vars_in_order, dict=data_block)
    blocksize = _calc_blocksize(dict=data_block)
    struct_str = _make_bin_struct_str(dict=data_block)

    # Check
    _print_dict(dict=data_block)
    print(f"vars_in_order: {vars_in_order}")
    print(f"blocksize: {blocksize}")
    print(f"struct_str: {struct_str}")

    return data_block, blocksize, struct_str


def _sort_by_subdict(dict, by):
    """Sort dict by key in subdict"""
    # https://stackoverflow.com/questions/4110665/sort-nested-dictionary-by-value-and-remainder-by-another-value-in-python
    return sorted(dict.keys(), key=lambda x: (dict[x][by]))  # List


def _calc_var_byte_pos(sorted_list, dict):
    # Calc position(s) of var in Byte sequence
    pos = -1
    for var in sorted_list:
        bytes_counter = 0
        var_pos = []
        while bytes_counter < dict[var]['bytes']:
            bytes_counter += dict[var]['bytes']
            pos += 1
            var_pos.append(pos)
        dict[var]['pos'] = var_pos
    return dict


def _calc_blocksize(dict):
    """Total length of the data block in Bytes"""
    blocksize = 0
    for var, props in dict.items():
        blocksize += props['bytes']
    return blocksize


def _make_bin_struct_str(dict):
    """Construct binary struct string"""
    struct_str = '>'  # todo big-endian or other
    blocksize = 0
    for var, props in dict.items():
        struct_str += props['format'] + ' '
        blocksize += props['bytes']
    struct_str = struct_str.rstrip()  # Remove space at end of str
    return struct_str


def _print_dict(dict):
    for var, props in dict.items():
        print(f"{var}: {props}")
