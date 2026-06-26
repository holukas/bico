# bico

<img src="images/logo_bico2.png" alt="bico logo" width="200">

**Binary Converter for converting ETH eddy covariance binary raw data to ASCII CSV files**

`bico` converts eddy covariance raw data files from a compressed binary format
to uncompressed ASCII (human-readable). Converted files can then be used for
flux calculations in EddyPro.

Instruments send their data in data blocks. One data block contains all data
from the respective instrument at the time of measurement. For example, the
data blocks sent by sonic anemometers comprise the wind variables, sonic temperature
and other variables. Data blocks from gas analyzers comprise concentrations (e.g., CO2,
H2O), instrument metrics (e.g., signal strength), among others.

The data blocks implemented in `bico` live in
[`bico/settings/data_blocks`](bico/settings/data_blocks). The information used to
convert binary to ASCII is given in `.dblock` files, with accompanying notes in
the respective `.md` files. See the
[**data blocks overview**](bico/settings/data_blocks/README.md) for the full list
of supported instruments (sonic anemometers, IRGA / QCL / LGR gas analyzers), each
linked to its spec and documentation.

## Installation

`bico` requires Python 3.12 and uses [`uv`](https://docs.astral.sh/uv/) for dependency management.

- Latest release: https://github.com/holukas/bico/releases/latest
- From a clone (recommended): run `uv sync` in the repository root to create the virtual environment (`.venv`)
  with all pinned dependencies from `pyproject.toml` / `uv.lock`, then run the app with `uv run bico` (see Usage).
- As a package: `bico` can also be installed directly from a release tag, e.g.
  `pip install https://github.com/holukas/bico/archive/refs/tags/v2.0.tar.gz`, which provides the `bico` command.

### From scratch on a new machine

These steps take a clean machine from nothing to a running `bico`. `uv` handles both the dependencies
and the Python 3.12 interpreter, so you do not need to install Python yourself first.

1. **Install `uv`.** Pick the command for your system:
    - Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
    - macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`

   Then open a new terminal so `uv` is on your `PATH`. Check it with `uv --version`.
2. **Get the source.** Clone the repository (or download a release zip and unpack it):
    - `git clone https://github.com/holukas/bico.git`
    - `cd bico`
3. **Create the environment.** From the repository root, run `uv sync`. This downloads Python 3.12 if it
   is missing, creates the `.venv` virtual environment, and installs every pinned dependency from
   `pyproject.toml` / `uv.lock`. No separate `pip install` or manual `venv` activation is needed.
4. **Run it.** Start the terminal UI with `uv run bico` (see Usage for the TUI and the headless CLI).

To update later, run `git pull` and then `uv sync` again to pick up any changed dependencies.

## Usage

`bico` is installed as a package and exposes a `bico` command (run `uv sync` once to set up the environment).
The same command is available as `uv run python -m bico`.

`bico` can be run two ways: an interactive **terminal UI (TUI)** for configuring and launching conversions
by hand, or a **headless CLI** for automated/scheduled runs.

### TUI (terminal UI)

- Start the TUI with either of:
    - `uv run bico -t`
    - `uv run bico` (the TUI is the default when no other action is given)
- The TUI runs full-screen in your terminal but also adapts to smaller window sizes. Settings are on the
  left, and a live console showing the run log is on the right. It needs no display server, so it also works
  over SSH.
- Layout and controls:
    - **Instruments**: site, logger header, and up to three instrument data blocks (sonic and gas analyzers).
    - **Raw data**: source folder; start/end date (`YYYY-MM-DD HH:MM`, both ends inclusive); the filename
      datetime format (which includes the extension and also determines which files are searched, so there is no
      separate file-extension setting); and file-selection settings (`0` = no limit for the file/row limits).
    - **Output**: output folder, folder-name prefix, compression, worker processes (`0` = auto), and which plots
      to produce.
    - **Stop**: press while a conversion is running to end it early. The file currently being converted finishes,
      then no further files are started and the run winds down. Already-converted files are kept.
    - **Run options**: convert only the most recent *N* days (`0` = use the date range), and skip files already
      present in the output folder.
    - **Source folder** and **Output folder** have a **Browse…** button that opens a folder picker; in the picker
      you can browse the tree, go **Up**, or type/paste a path and press Enter to jump to it. You can also type the
      path directly into the field.
- Workflow: configure the settings, press **Validate** (`v`), then **Run** (`r`). **Validate** checks every field,
  prints the exact settings the run will use (with a short note on each), and counts the matching files in the
  source folder. **Run is disabled until validation passes**, and editing any field disables it again, so you
  always run exactly what you validated. **Test run** (`t`) does a quick dry conversion of the first rows of the
  first matching file (writing nothing), to confirm the settings produce a valid result before a full run. While a
  run is in progress, a progress bar shows files done/total with an estimated remaining time, and below it each
  file currently being converted gets its own line with a per-file percentage and the current step (Reading,
  Converting, Saving, and so on), so with several worker processes you see every in-flight file at once. Each
  file's detailed, colour-coded log appears in the console as soon as that file finishes.
- Key bindings (also shown in the footer):
    - `v`: validate settings (enables Run when everything is OK)
    - `d`: detect the time range from the source files (fills Start/End date)
    - `t`: test run (dry conversion of the first file, nothing written)
    - `r`: run the conversion
    - `s`: save the current settings to `bico.settings`
    - `f`: show / hide the settings panel (console fills the width)
    - `Ctrl+L`: clear the console
    - `h`: open the in-app help
    - `q`: quit
- The TUI opens with the settings you last saved to `bico/settings/bico.settings`, so it always starts where you
  left off. Saving writes only the user-editable settings back to that file (run-only options such as "recent days"
  and "avoid duplicates" are not persisted). Each run also writes a `bico.settings` snapshot of its effective
  settings and a log file into that run's output folder; the source `bico.settings` is never modified by a run.
- To reuse a previous run's settings, **drag and drop its `bico.settings` file anywhere onto the TUI**, and the form
  is filled from it. (Most terminals deliver a dropped file as its pasted path, which the TUI recognises.)
- To set the **source** or **output** folder without browsing, **click the field to focus it, then drag and drop a
  file or folder onto the TUI**. The field is filled with the folder path (a dropped file uses the folder that
  contains it). The terminal sends the dropped path to the focused field, so make sure the field you want is focused.
- To copy from the **console**, drag with the mouse to select text and press **Ctrl+C** (double-click selects a line).
- **Detect dates from source files** (`d`) scans the source folder, parses every file's date with the filename
  datetime format, and fills Start/End date with the earliest and latest file (resetting "recent days" to 0 so the
  range is used). You can still adjust the dates afterwards.

### CLI (headless)

- `bico` can also be run from the command-line interface (CLI) without the TUI. This is useful to
  execute conversions automatically at certain intervals. For example, `bico` is used to
  convert binary files to ASCII csv files for the site CH-OE2 once a day:
    - `uv run bico -f Z:\CH-OE2_Oensingen\20_ec_fluxes\2022\raw_data_ascii -d 8 -a`
    - `uv run bico` runs the installed `bico` command (use `uv run --project <bico-dir> bico ...` from another directory,
      or activate the project's virtual environment)
    - `-f Z:\CH-OE2_Oensingen\20_ec_fluxes\2022\raw_data_ascii` specifies the folder where the `bico.settings` file
      and the raw binary files for this site (CH-OE2) are located. The settings file can be created/edited in the TUI
      (via **Save settings**), or edited directly with a text editor.
    - `-d 8` converts binary files from the last 8 days to ASCII
    - `-a` means "avoid duplicates", converts only binary files that were not converted before. The folder specified
      with `-f` is checked if a specific files was already converted. If the file already exists in the folder, then it
      is not converted again.
- Run `uv run bico -h` to see all available options.

## Documentation

- [Data blocks overview](bico/settings/data_blocks/README.md): all supported
  instruments and logging variants, each linked to its `.dblock` spec and `.md` notes.
- [Settings reference](bico/settings/data_blocks/_help_bico_settings.md): explains
  every variable property used inside a `.dblock` file.
- [Reference comparisons](tests/reference_comparisons.md): regression tests that
  assert byte-identical converted output against a known-good (bico-1.6.0) reference
  across several sites.
- [Changelog](CHANGELOG.md): release history and notable changes.

## Testing

Set up the environment with `uv sync`, then run the test suite:

```bash
uv run pytest
```

The default run is fast. The [reference comparisons](tests/reference_comparisons.md)
are marked `slow` and excluded by default (they need large data that lives outside
the repo); run them with `uv run pytest -m slow`.
