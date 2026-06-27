"""Golden-file tests for the binary-to-ASCII conversion.

The converted output must stay byte-for-byte stable: it feeds downstream flux
calculations, so any unintended change to values or formatting is a bug. Each
case converts a small truncated real binary file and compares the result against
a committed golden CSV.

Cases (see tests/data/):
- CH-DAV (HS50-A + IRGA72-A + QCL-C3, .X00): golden verified to match the output
  of the previous poetry / Python 3.9 version (see CHANGELOG v2.0). Its truncated
  sample also exercises the short/missing IRGA72 data-block path.
- CH-AWS (HS50-A + IRGA72-A, .A00): golden verified to be a byte-for-byte prefix
  of the output produced by the previous bico 1.6.7 version for the full file.
"""
import io
import logging
from dataclasses import dataclass

import pytest
from conftest import DATA_DIR, PACKAGE_DIR

from bico.ops import bin as bbin
from bico.ops import file as bfile

HEADER_SIZE = 29  # WECOM3 header
N_HEADER_ROWS = 3  # variable name / units / data block


@dataclass(frozen=True)
class Case:
    id: str
    dblocks: list
    sample: str
    golden: str
    n_cols: int


CASES = [
    Case(
        id="CH-DAV",
        dblocks=["HS50-A", "IRGA72-A", "QCL-C3"],
        sample="CH-DAV_2021111013_sample.X00",
        golden="CH-DAV_2021111013_sample.golden.csv",
        n_cols=31,
    ),
    Case(
        id="CH-AWS",
        dblocks=["HS50-A", "IRGA72-A"],
        sample="CH-AWS_2025070113_sample.A00",
        golden="CH-AWS_2025070113_sample.golden.csv",
        n_cols=20,
    ),
]


@pytest.fixture(scope="module")
def logger():
    lg = logging.getLogger("bico_test")
    lg.addHandler(logging.NullHandler())
    lg.setLevel(logging.CRITICAL)
    return lg


def _convert(case: Case, logger) -> list:
    """Run the conversion pipeline as bico.py does and return the CSV lines."""
    dblocks_props = bfile.load_dblocks_props(case.dblocks, {"dir_script": str(PACKAGE_DIR)})
    obj = bbin.ConvertData(
        binary_filename=DATA_DIR / case.sample,
        size_header=HEADER_SIZE,
        dblocks=dblocks_props,
        limit_read_lines=0,
        logger=logger,
        cur_file_number=1,
    )
    obj.run()
    headers, _ = obj.get_data()
    # add_instr_to_varname=1, as used to generate the golden / reference output
    headers = [(f"{h[0]}_{h[2]}", h[1], h[2]) for h in headers]
    df = obj.get_dataframe(headers)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().splitlines()


@pytest.fixture(scope="module", params=CASES, ids=[c.id for c in CASES])
def case_lines(request, logger):
    """(case, produced_lines) for each conversion case."""
    case = request.param
    return case, _convert(case, logger)


def test_sample_conversion_matches_golden(case_lines):
    case, produced_lines = case_lines
    expected = (DATA_DIR / case.golden).read_text().splitlines()
    assert len(produced_lines) == len(expected), (
        f"[{case.id}] row count differs: produced {len(produced_lines)}, golden {len(expected)}"
    )
    for i, (got, want) in enumerate(zip(produced_lines, expected)):
        assert got == want, f"[{case.id}] line {i} differs:\n  produced: {got}\n  golden:   {want}"


def test_sample_has_expected_shape(case_lines):
    case, produced_lines = case_lines
    # N header rows + at least one data row, with the expected column count
    assert len(produced_lines) >= N_HEADER_ROWS + 1
    assert produced_lines[0].count(",") == case.n_cols - 1


# --- CH-DAV-specific: the short/missing IRGA72 data-block path ----------------

IRGA72_NOMINAL_DATA_SIZE = 26.0
IRGA72_ANALYZER_COLS = [
    "GA_DIAG_CODE_[IRGA72-A]", "SIGNAL_STRENGTH_[IRGA72-A]",
    "H2O_DRY_[IRGA72-A]", "CO2_DRY_[IRGA72-A]", "H2O_CONC_[IRGA72-A]",
    "CO2_CONC_[IRGA72-A]", "T_CELL_[IRGA72-A]", "PRESS_CELL_[IRGA72-A]",
    "PRESS_BOX_[IRGA72-A]", "COOLER_V_[IRGA72-A]", "FLOW_VOLRATE_[IRGA72-A]",
]


def test_short_datablock_is_filled_with_missing(logger):
    """The short/missing IRGA72 data-block path must fill analyzer vars with -9999.

    This is the trickiest branch in the conversion (a data block smaller than its
    nominal size, e.g. the IRGA72 16-vs-26-byte logging quirk), so it is asserted
    explicitly rather than relying only on the golden comparison. The CH-DAV
    fixture is the one that contains such short blocks.
    """
    dav = next(c for c in CASES if c.id == "CH-DAV")
    produced_lines = _convert(dav, logger)
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
