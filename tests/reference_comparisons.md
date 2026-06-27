# Reference comparisons

Integration checks that the current bico still produces **byte-identical**
converted output versus a known-good reference (bico-1.6.0). Unlike the committed
golden-file test (`tests/data/*`), these use large real binaries that live
*outside* the repo, so only the expected hashes are committed, not the data.

- Runner + manifest generator: [`test_reference_comparisons.py`](test_reference_comparisons.py)
- Committed golden hashes: [`reference_comparisons.json`](reference_comparisons.json)

## Data layout

Under the data root (`BICO_REFDATA_ROOT` env var, else the default dev path
`F:\Sync\luhk_work\dev-data\flux-data\bico-data`), per test `N`:

```
test_<N>/A_test_in_<N>                  input binaries
test_<N>/B_test_out_refererence_<N>     bico-1.6.0 reference output (the golden truth)
test_<N>/C_test_out_claude_version_<N>  scratch output from earlier manual runs (ignored by the runner)
```

## How it works

`reference_comparisons.json` stores the SHA-256 of each reference CSV's
**decompressed** bytes. The gzip wrapper can differ (timestamp / OS byte) even
when the content is identical, so the `.csv.gz` files are never compared directly.

The runner builds a `bico.settings` for each case (parameters taken from the
reference `BICO.settings`, see `CASES` in the runner), converts the inputs into a
temp folder, and asserts the produced CSVs hash to the committed values.

If the data root is absent (e.g. CI), every case is skipped, so the module is a
no-op for anyone without the data.

### Verify (run all 7)

These are marked `slow` and deselected from the default `uv run pytest`. Run them
explicitly with `-m slow`:

```bash
uv run pytest tests/test_reference_comparisons.py -m slow -v
```

### Regenerate the manifest

Only after an **intentional, reviewed** change to converted values. Hashes are
read straight from the reference `B` folders:

```bash
uv run python tests/test_reference_comparisons.py --update
```

## Results

Last run 2026-06-27 — **7 cases, 24 files, all PASS** (byte-identical decompressed CSV).

| Test | Site | Header / instruments | Format | Files | Result |
|------|------|----------------------|--------|-------|--------|
| test_1 | CH-DAV | WECOM3 / HS50-A, IRGA72-A, QCL-C3 | `yyyymmddHH.XMM` | 2 | ✅ PASS |
| test_2 | CH-AWS | WECOM3 / HS50-A, IRGA72-A | `yyyymmddHH.AMM` | 2 | ✅ PASS |
| test_3 | CH-CHA | WECOM3 / R350-B, IRGA75-A | `yyyymmddHH.CMM` | 4 | ✅ PASS |
| test_4 | CH-DAS | WECOM3 / R350-B, IRGA75-A, QCL-C2 | `yyyymmddHH.YMM` | 2 | ✅ PASS |
| test_5 | CH-DAV | WECOM3 / HS50-A, IRGA72-A | `yyyymmddHH.XMM` | 4 | ✅ PASS |
| test_6 | CH-LAE | WECOM3 / HS50-B, IRGA72-A | `yyyymmddHH.LMM` | 4 | ✅ PASS |
| test_7 | CH-OE2 | WECOM3 / R350-B, IRGA72-A | `yyyymmddHH.oMM` | 6 | ✅ PASS |

### Coverage notes

- **Instruments:** R350-B, IRGA75-A, IRGA72-A, HS50-A, HS50-B, QCL-C2, QCL-C3,
  plus the `-None-` third-slot case. Header is `WECOM3` throughout.
- **Filename datetime formats / extensions:** `.XMM`, `.AMM`, `.CMM`, `.YMM`,
  `.LMM`, `.oMM` (note the lowercase `o`).
- **Edge cases:** non-zero start-minute files — `2025091708.C57` (test_3),
  `2026060517.X26` (test_5) — and a small/truncated file `2025070113.A00` (test_2).
