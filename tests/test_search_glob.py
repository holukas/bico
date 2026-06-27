"""Tests for deriving the file-search glob from the filename datetime format.

The separate file-extension setting was removed: the search glob is derived
from the datetime format (which already includes the extension after the dot).
"""
import logging

from bico.ops.file import SearchAll
from bico.ops.file import search_glob_from_datetime_format as glob

_LOG = logging.getLogger("test_search")


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


def test_search_all_recurses_into_subfolders(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a" / "2025010100.C00").write_bytes(b"x")
    (tmp_path / "b" / "2025010101.C00").write_bytes(b"x")
    found = SearchAll.search_all(dir=str(tmp_path), file_id="*.C*", logger=_LOG)
    assert set(found) == {"2025010100.C00", "2025010101.C00"}


def test_search_all_keeps_larger_file_on_duplicate_name(tmp_path):
    # Same filename in two subfolders: the larger file wins.
    (tmp_path / "small").mkdir()
    (tmp_path / "big").mkdir()
    small = tmp_path / "small" / "2025010100.C00"
    big = tmp_path / "big" / "2025010100.C00"
    small.write_bytes(b"x" * 10)
    big.write_bytes(b"x" * 100)
    found = SearchAll.search_all(dir=str(tmp_path), file_id="*.C*", logger=_LOG)
    assert list(found) == ["2025010100.C00"]
    assert found["2025010100.C00"] == big


def test_search_all_equal_size_duplicate_keeps_one(tmp_path):
    # Equal sizes are interchangeable; the result still collapses to one entry.
    (tmp_path / "x").mkdir()
    (tmp_path / "y").mkdir()
    (tmp_path / "x" / "2025010100.C00").write_bytes(b"x" * 50)
    (tmp_path / "y" / "2025010100.C00").write_bytes(b"y" * 50)
    found = SearchAll.search_all(dir=str(tmp_path), file_id="*.C*", logger=_LOG)
    assert list(found) == ["2025010100.C00"]
