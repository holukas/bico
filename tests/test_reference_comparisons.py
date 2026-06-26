"""Integration reference comparisons against bico-1.6.0 output.

Unlike the committed golden-file test (``tests/data/*``), these checks convert
large real binaries that live OUTSIDE the repo and assert the current bico
produces byte-identical *decompressed* CSV content versus a committed manifest of
SHA-256 hashes (``tests/reference_comparisons.json``).

Data layout (per test ``N``), under the data root::

    test_<N>/A_test_in_<N>                  input binaries
    test_<N>/B_test_out_refererence_<N>     bico-1.6.0 reference output (the golden truth)
    test_<N>/C_test_out_claude_version_<N>  ignored here (runner uses a temp dir)

The data root is taken from the ``BICO_REFDATA_ROOT`` env var, else a default dev
path. If the root is absent (e.g. on CI) every test is skipped, so this module is
a no-op for anyone without the data.

Why hash the *decompressed* bytes: the gzip wrapper can differ (timestamp / OS
byte) even when the CSV content is identical, so the ``.csv.gz`` files are not
directly comparable.

Regenerate the manifest after an intentional, reviewed change to converted
values (hashes are read straight from the reference ``B`` folders)::

    uv run python tests/test_reference_comparisons.py --update

Run just these checks (slow; converts ~16 files)::

    uv run pytest tests/test_reference_comparisons.py -v
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

DEFAULT_ROOT = Path(r"F:/Sync/luhk_work/dev-data/flux-data/bico-data")
MANIFEST_FILE = Path(__file__).with_name("reference_comparisons.json")

# Per-test conversion parameters, taken from each reference ``BICO.settings``.
# Date ranges are widened to comfortably bracket the input files of each case.
CASES: dict[str, dict] = {
    "test_1": dict(site="CH-DAV", header="WECOM3",
                   instrument_1="HS50-A", instrument_2="IRGA72-A", instrument_3="QCL-C3",
                   filename_datetime_format="yyyymmddHH.XMM",
                   start_date="2021-11-01 00:00", end_date="2021-11-30 23:59",
                   output_folder_name_prefix="test"),
    "test_2": dict(site="CH-AWS", header="WECOM3",
                   instrument_1="HS50-A", instrument_2="IRGA72-A", instrument_3="-None-",
                   filename_datetime_format="yyyymmddHH.AMM",
                   start_date="2025-07-01 00:00", end_date="2025-07-31 23:59",
                   output_folder_name_prefix="CH-AWS_2025"),
    "test_3": dict(site="CH-CHA", header="WECOM3",
                   instrument_1="R350-B", instrument_2="IRGA75-A", instrument_3="-None-",
                   filename_datetime_format="yyyymmddHH.CMM",
                   start_date="2025-09-01 00:00", end_date="2025-09-30 23:59",
                   output_folder_name_prefix="CH-CHA_2025_1"),
    "test_4": dict(site="CH-DAS", header="WECOM3",
                   instrument_1="R350-B", instrument_2="IRGA75-A", instrument_3="QCL-C2",
                   filename_datetime_format="yyyymmddHH.YMM",
                   start_date="2023-05-01 00:01", end_date="2024-01-01 00:00",
                   output_folder_name_prefix="CH-DAS_BICO_2023"),
    "test_5": dict(site="CH-DAV", header="WECOM3",
                   instrument_1="HS50-A", instrument_2="IRGA72-A", instrument_3="-None-",
                   filename_datetime_format="yyyymmddHH.XMM",
                   start_date="2026-06-01 00:00", end_date="2026-06-30 23:59",
                   output_folder_name_prefix="CH-DAV_autotask"),
    "test_6": dict(site="CH-LAE", header="WECOM3",
                   instrument_1="HS50-B", instrument_2="IRGA72-A", instrument_3="-None-",
                   filename_datetime_format="yyyymmddHH.LMM",
                   start_date="2026-06-01 00:00", end_date="2026-06-30 23:59",
                   output_folder_name_prefix="CH-LAE_autotask"),
    "test_7": dict(site="CH-OE2", header="WECOM3",
                   instrument_1="R350-B", instrument_2="IRGA72-A", instrument_3="-None-",
                   filename_datetime_format="yyyymmddHH.oMM",
                   start_date="2025-02-01 00:00", end_date="2025-03-31 23:59",
                   output_folder_name_prefix="CH-OE2_2025_1-3"),
}


def data_root() -> Path | None:
    """Return the external data root if it exists, else None."""
    root = Path(os.environ.get("BICO_REFDATA_ROOT", DEFAULT_ROOT))
    return root if root.is_dir() else None


def _case_dirs(root: Path, name: str) -> tuple[Path, Path]:
    n = name.split("_")[1]
    return (root / name / f"A_test_in_{n}", root / name / f"B_test_out_refererence_{n}")


def _sha256_decompressed(path: Path) -> str:
    h = hashlib.sha256()
    with gzip.open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _settings_text(params: dict, dir_source: Path, dir_out: Path) -> str:
    return (
        f"site={params['site']}\n"
        f"header={params['header']}\n"
        f"instrument_1={params['instrument_1']}\n"
        f"instrument_2={params['instrument_2']}\n"
        f"instrument_3={params['instrument_3']}\n"
        f"dir_source={dir_source.as_posix()}\n"
        f"start_date={params['start_date']}\n"
        f"end_date={params['end_date']}\n"
        f"filename_datetime_format={params['filename_datetime_format']}\n"
        "file_size_min=900\n"
        "file_limit=0\n"
        "row_limit=0\n"
        "select_random_files=0\n"
        f"dir_out={dir_out.as_posix()}\n"
        f"output_folder_name_prefix={params['output_folder_name_prefix']}\n"
        "file_compression=gzip\n"
        "num_processes=4\n"
        "add_instr_to_varname=1\n"
        "plot_file_availability=0\n"
        "plot_ts_hires=0\n"
        "plot_histogram_hires=0\n"
        "plot_ts_agg=0\n"
    )


def reference_hashes(root: Path, name: str) -> dict[str, str]:
    """SHA-256 of the decompressed reference CSVs, keyed by file basename."""
    _, ref = _case_dirs(root, name)
    return {p.name: _sha256_decompressed(p) for p in sorted(ref.rglob("*.csv.gz"))}


def convert_and_hash(root: Path, name: str) -> dict[str, str]:
    """Run the current bico on a case's inputs and hash the produced CSVs."""
    src, _ = _case_dirs(root, name)
    with tempfile.TemporaryDirectory(prefix=f"bico_{name}_") as tmp:
        tmp = Path(tmp)
        cfg, out = tmp / "cfg", tmp / "out"
        cfg.mkdir(); out.mkdir()
        (cfg / "bico.settings").write_text(_settings_text(CASES[name], src, out), encoding="utf-8")
        subprocess.run([sys.executable, "-m", "bico", "-f", str(cfg)],
                       check=True, capture_output=True, text=True)
        return {p.name: _sha256_decompressed(p) for p in sorted(out.rglob("*.csv.gz"))}


def load_manifest() -> dict:
    return json.loads(MANIFEST_FILE.read_text(encoding="utf-8")) if MANIFEST_FILE.exists() else {}


def write_manifest() -> dict:
    """Rebuild the manifest from the reference (golden) folders and save it."""
    root = data_root()
    if root is None:
        raise SystemExit(f"Data root not found (set BICO_REFDATA_ROOT or place data at {DEFAULT_ROOT}).")
    manifest = {name: reference_hashes(root, name) for name in CASES}
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    total = sum(len(v) for v in manifest.values())
    print(f"Wrote {MANIFEST_FILE} ({len(manifest)} cases, {total} files).")
    return manifest


_root = data_root()
pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(_root is None, reason="reference data root not available"),
]


@pytest.mark.parametrize("name", list(CASES))
def test_reference_comparison(name: str):
    manifest = load_manifest()
    assert name in manifest and manifest[name], f"no manifest entry for {name}; run --update"
    produced = convert_and_hash(_root, name)
    assert produced == manifest[name], (
        f"{name}: converted output differs from golden reference manifest"
    )


if __name__ == "__main__":
    if "--update" in sys.argv:
        write_manifest()
    else:
        print("Use --update to (re)generate the manifest, or run via pytest to verify.")
