"""Tests for deriving the file-search glob from the filename datetime format.

The separate file-extension setting was removed: the search glob is derived
from the datetime format (which already includes the extension after the dot).
"""
from bico.ops.file import search_glob_from_datetime_format as glob


def test_standard_format_matches_old_file_ext():
    # yyyymmddHH.CMM previously paired with file_ext '*.C*'
    assert glob('yyyymmddHH.CMM') == '*.C*'


def test_x_extension_format():
    assert glob('yyyymmddHH.XMM') == '*.X*'


def test_tokens_collapse_to_single_wildcard():
    assert glob('yyyymmdd') == '*'


def test_month_and_minute_both_replaced():
    # 'mm' (month) and 'MM' (minute) are distinct, both become wildcards
    out = glob('yyyy-mm-dd_HH-MM.dat')
    assert out == '*-*-*_*-*.dat'


def test_literal_only_format_is_unchanged():
    assert glob('rawdata.bin') == 'rawdata.bin'
