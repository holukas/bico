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

from conftest import PACKAGE_DIR, DATA_DIR

from bico.ops import bin as bbin, file as bfile, format_data

# Matches the reference run: site CH-DAV with these three instruments, the
# WECOM3 header (29 bytes), and add_instr_to_varname enabled.
DBLOCK_SEQUENCE = ["HS50-A", "IRGA72-A", "QCL-C3"]
HEADER_SIZE = 29
SAMPLE_BIN = DATA_DIR / "CH-DAV_2021111013_sample.X00"
GOLDEN_CSV = DATA_DIR / "CH-DAV_2021111013_sample.golden.csv"

# Nominal size of the IRGA72-A data block; rows with a different size are
# short/missing analyzer blocks whose values get filled with -9999.
IRGA72_NOMINAL_DATA_SIZE = 26.0
IRGA72_ANALYZER_COLS = [
    "GA_DIAG_CODE_[IRGA72-A]", "SIGNAL_STRENGTH_[IRGA72-A]",
    "H2O_DRY_[IRGA72-A]", "CO2_DRY_[IRGA72-A]", "H2O_CONC_[IRGA72-A]",
    "CO2_CONC_[IRGA72-A]", "T_CELL_[IRGA72-A]", "PRESS_CELL_[IRGA72-A]",
    "PRESS_BOX_[IRGA72-A]", "COOLER_V_[IRGA72-A]", "FLOW_VOLRATE_[IRGA72-A]",
]
N_HEADER_ROWS = 3  # variable name / units / data block


@pytest.fixture(scope="module")
def logger():
    lg = logging.getLogger("bico_test")
    lg.addHandler(logging.NullHandler())
    lg.setLevel(logging.CRITICAL)
    return lg


@pytest.fixture(scope="module")
def dblocks_props(logger):
    return bfile.load_dblocks_props(DBLOCK_SEQUENCE, {"dir_script": str(PACKAGE_DIR)})


@pytest.fixture(scope="module")
def produced_lines(dblocks_props, logger):
    """Run the conversion pipeline as bico.py does and return the CSV lines."""
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
    return buf.getvalue().splitlines()


def test_sample_conversion_matches_golden(produced_lines):
    expected = GOLDEN_CSV.read_text().splitlines()
    assert len(produced_lines) == len(expected), (
        f"row count differs: produced {len(produced_lines)}, golden {len(expected)}"
    )
    for i, (got, want) in enumerate(zip(produced_lines, expected)):
        assert got == want, f"line {i} differs:\n  produced: {got}\n  golden:   {want}"


def test_sample_has_expected_shape(produced_lines):
    # 3 header rows + data rows, 31 columns
    assert len(produced_lines) >= N_HEADER_ROWS + 1
    assert produced_lines[0].count(",") == 30


def test_short_datablock_is_filled_with_missing(produced_lines):
    """The short/missing IRGA72 data-block path must fill analyzer vars with -9999.

    This is the trickiest branch in the conversion (a data block smaller than its
    nominal size, e.g. the IRGA72 16-vs-26-byte logging quirk), so it is asserted
    explicitly rather than relying only on the golden comparison.
    """
    names = produced_lines[0].split(",")
    i_data_size = names.index("DATA_SIZE_[IRGA72-A]")
    analyzer_idx = [names.index(c) for c in IRGA72_ANALYZER_COLS]

    data_rows = [line.split(",") for line in produced_lines[N_HEADER_ROWS:]]
    short_rows = [r for r in data_rows
                  if float(r[i_data_size]) != IRGA72_NOMINAL_DATA_SIZE]

    assert short_rows, "fixture should contain at least one short/missing IRGA72 data block"
    for row in short_rows:
        for j in analyzer_idx:
            assert float(row[j]) == -9999.0, (
                f"short-block row should have -9999 in {names[j]}, got {row[j]}"
            )
