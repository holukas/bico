"""Golden-file test for the binary-to-ASCII conversion.

The converted output must stay byte-for-byte stable: it feeds downstream flux
calculations, so any unintended change to values or formatting is a bug. This
test converts a small truncated real binary file (site CH-DAV, data blocks
HS50-A + IRGA72-A + QCL-C3) and compares the result against a committed golden
CSV. The golden was verified to match the output of the previous
poetry / Python 3.9 version (see CHANGELOG v2.0).

Fixtures live in tests/data/:
- CH-DAV_2021111013_sample.X00   truncated raw binary input
- CH-DAV_2021111013_sample.golden.csv   expected converted output
"""
import io
import logging

import pytest

from conftest import SRC_DIR, DATA_DIR

from ops import bin as bbin, file as bfile, format_data

# Matches the reference run: site CH-DAV with these three instruments, the
# WECOM3 header (29 bytes), and add_instr_to_varname enabled.
DBLOCK_SEQUENCE = ["HS50-A", "IRGA72-A", "QCL-C3"]
HEADER_SIZE = 29
SAMPLE_BIN = DATA_DIR / "CH-DAV_2021111013_sample.X00"
GOLDEN_CSV = DATA_DIR / "CH-DAV_2021111013_sample.golden.csv"


@pytest.fixture(scope="module")
def logger():
    lg = logging.getLogger("bico_test")
    lg.addHandler(logging.NullHandler())
    lg.setLevel(logging.CRITICAL)
    return lg


@pytest.fixture(scope="module")
def dblocks_props(logger):
    return bfile.load_dblocks_props(DBLOCK_SEQUENCE, {"dir_script": str(SRC_DIR)})


def _convert_to_csv(dblocks_props, logger):
    """Run the conversion pipeline as bico.py does and return CSV text."""
    obj = bbin.ConvertData(
        binary_filename=SAMPLE_BIN,
        size_header=HEADER_SIZE,
        dblocks=dblocks_props,
        limit_read_lines=0,
        logger=logger,
        cur_file_number=1,
    )
    obj.run()
    headers, rows = obj.get_data()
    # add_instr_to_varname=1, as used to generate the golden / reference output
    headers = [(f"{h[0]}_{h[2]}", h[1], h[2]) for h in headers]
    df = format_data.make_df(rows, headers, logger)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


def test_sample_conversion_matches_golden(dblocks_props, logger):
    produced = _convert_to_csv(dblocks_props, logger).splitlines()
    expected = GOLDEN_CSV.read_text().splitlines()

    assert len(produced) == len(expected), (
        f"row count differs: produced {len(produced)}, golden {len(expected)}"
    )
    for i, (got, want) in enumerate(zip(produced, expected)):
        assert got == want, f"line {i} differs:\n  produced: {got}\n  golden:   {want}"


def test_sample_has_expected_shape(dblocks_props, logger):
    produced = _convert_to_csv(dblocks_props, logger).splitlines()
    # 3 header rows (name / units / datablock) + data rows, 31 columns
    assert len(produced) >= 4
    assert produced[0].count(",") == 30
