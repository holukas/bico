"""Tests for settings persistence.

A run must never rewrite the user's source bico.settings file, and saving from
the GUI must not pollute it with derived/runtime keys (per-run ids and
machine-specific absolute paths). These tests lock in that behavior.
"""
from bico.ops import file as bfile


def _write(path, text):
    path.write_text(text)
    return path


def test_save_settings_drops_derived_keys_and_updates_user_keys(tmp_path):
    _write(tmp_path / "bico.settings", (
        "# INSTRUMENTS\n"
        "site=CH-OLD\n"
        "file_compression=gzip\n"
        "# OUTPUT\n"
        "run_id=BICO-old\n"
        "dir_out_run=/old/run\n"
        "dir_script=/old/script\n"
    ))
    settings_dict = {
        "dir_settings": str(tmp_path),
        "site": "CH-DAV",
        "file_compression": "None",
        # derived keys present in the dict must NOT be written back
        "run_id": "BICO-new",
        "dir_out_run": "/new/run",
        "dir_script": "/new/script",
    }

    bfile.save_settings_to_file(settings_dict)
    text = (tmp_path / "bico.settings").read_text()

    # user keys updated
    assert "site=CH-DAV" in text
    assert "file_compression=None" in text
    # derived keys dropped entirely
    assert "run_id" not in text
    assert "dir_out_run" not in text
    assert "dir_script" not in text
    # comments preserved
    assert "# INSTRUMENTS" in text
    # no leftover temp file
    assert not (tmp_path / "bico.settingsTemp").exists()


def test_run_snapshot_uses_canonical_structure_and_drops_derived(tmp_path):
    outdir = tmp_path / "run_out"
    outdir.mkdir()
    settings_dict = {
        "site": "CH-DAV",
        "dir_source": "/data/in",
        "run_id": "BICO-xyz",          # derived -> not persisted to the snapshot
        "dir_out_run": str(outdir),    # derived -> not persisted to the snapshot
    }

    snapshot = bfile.write_run_settings_snapshot(settings_dict, outdir)
    snap_text = snapshot.read_text()

    # user settings written, with the canonical structure (sections + comments)
    assert "site=CH-DAV" in snap_text
    assert "dir_source=/data/in" in snap_text
    assert "# INSTRUMENTS" in snap_text
    assert "num_processes" in snap_text   # present because the canonical file has it
    # derived/runtime keys are not persisted to the snapshot
    assert "run_id" not in snap_text
    assert "dir_out_run" not in snap_text


def test_snapshot_and_export_produce_identical_files(tmp_path):
    """The run-folder snapshot and an Export of the same settings must be byte
    identical: one canonical structure no matter where bico writes it."""
    settings_dict = {
        "site": "CH-DAV", "header": "WECOM3",
        "instrument_1": "HS50-A", "instrument_2": "IRGA72-A", "instrument_3": "QCL-C2",
        "dir_source": "Y:/in", "dir_out": "Z:/out",
        "start_date": "2026-06-22 07:33", "end_date": "2099-06-22 07:00",
        "filename_datetime_format": "yyyymmddHH.XMM",
        "file_size_min": "900", "file_limit": "0", "row_limit": "0",
        "select_random_files": "0",
        "output_folder_name_prefix": "CH-DAV_AUTOTASK", "file_compression": "gzip",
        "num_processes": "1", "add_instr_to_varname": "1",
        "plot_file_availability": "1", "plot_ts_hires": "1",
        "plot_histogram_hires": "0", "plot_ts_agg": "1",
        # derived/runtime keys present in the run dict, must not affect either file
        "run_id": "BICO-xyz", "dir_out_run": "/run",
    }
    exp_dir = tmp_path / "exp"; exp_dir.mkdir()
    snap_dir = tmp_path / "snap"; snap_dir.mkdir()

    exp = bfile.export_settings_to_folder(settings_dict, exp_dir)
    snap = bfile.write_run_settings_snapshot(settings_dict, snap_dir)

    assert exp.read_text() == snap.read_text()


def test_export_settings_to_folder_renders_from_template(tmp_path):
    """Export writes a bico.settings into a chosen folder, using a template for
    layout, with current values substituted and derived keys dropped."""
    template = _write(tmp_path / "template.settings", (
        "# INSTRUMENTS\n"
        "site=CH-OLD\n"
        "dir_source=/old/source\n"
        "dir_out=/old/out\n"
        "run_id=BICO-old\n"
    ))
    dest = tmp_path / "headless_run"
    dest.mkdir()
    settings_dict = {
        "site": "CH-DAV",
        "dir_source": "/new/source",
        "dir_out": "/new/out",
        "run_id": "BICO-new",  # derived, must not be written
    }

    out = bfile.export_settings_to_folder(settings_dict, dest, template)

    assert out == dest / "bico.settings"
    text = out.read_text()
    assert "site=CH-DAV" in text
    assert "dir_source=/new/source" in text
    assert "dir_out=/new/out" in text
    assert "run_id" not in text             # derived key dropped
    assert "# INSTRUMENTS" in text          # template comments preserved
    # the template/source file is left untouched
    assert "site=CH-OLD" in template.read_text()
    assert not (dest / "bico.settingsTemp").exists()


def test_export_appends_keys_missing_from_template(tmp_path):
    """A template that predates a setting must not drop it: the missing user key
    (e.g. num_processes) is appended so the exported file is complete."""
    template = _write(tmp_path / "old.settings", (
        "# OUTPUT\n"
        "site=CH-OLD\n"
        "dir_out=/old/out\n"
        # note: no num_processes line (older template)
    ))
    dest = tmp_path / "headless_run"
    dest.mkdir()
    settings_dict = {
        "site": "CH-DAV",
        "dir_out": "/new/out",
        "num_processes": "6",      # not in the template -> must be appended
        "run_id": "BICO-new",      # derived -> must stay out
    }

    out = bfile.export_settings_to_folder(settings_dict, dest, template)
    text = out.read_text()

    assert "site=CH-DAV" in text          # substituted in place
    assert "dir_out=/new/out" in text
    assert "num_processes=6" in text       # appended (was missing from template)
    assert "run_id" not in text            # derived still excluded


def test_export_drops_legacy_keys(tmp_path):
    """Legacy/removed keys (file_ext, dir_server_*) must never be written, whether
    they sit in the template or are carried in the settings dict."""
    template = _write(tmp_path / "legacy.settings", (
        "# RAW DATA\n"
        "site=CH-OLD\n"
        "file_ext=*.X*\n"                  # removed setting, present in template
        "# DIRECTORIES\n"
        "dir_server_CH-DAV=\\\\nas\\path\n"  # reference-only, present in template
    ))
    dest = tmp_path / "headless_run"
    dest.mkdir()
    settings_dict = {
        "site": "CH-DAV",
        "file_ext": "*.X*",                # carried in the dict too -> still dropped
        "dir_server_CH-DAV": "\\\\nas\\path",
        "num_processes": "4",
    }

    out = bfile.export_settings_to_folder(settings_dict, dest, template)
    text = out.read_text()

    assert "site=CH-DAV" in text
    assert "num_processes=4" in text
    assert "file_ext" not in text          # legacy key dropped
    assert "dir_server" not in text        # reference-only keys dropped
    # the now-empty section header is dropped too, no orphan left behind
    assert "DIRECTORIES" not in text


def test_emptied_section_header_is_dropped_but_others_kept(tmp_path):
    """Removing every setting under a header drops the header; headers that still
    have content (or stand alone over other sections) are preserved."""
    template = _write(tmp_path / "bico.settings", (
        "# RAW DATA\n"
        "# ========\n"
        "\n"
        "# File Settings\n"
        "filename_datetime_format=yyyymmddHH.XMM\n"
        "file_ext=*.X*\n"
        "file_size_min=900\n"
        "\n"
        "# DIRECTORIES\n"
        "# ===========\n"
        "dir_server_CH-DAV=\\\\nas\\path\n"
        "dir_server_CH-AWS=\\\\nas\\path2\n"
    ))
    dest = tmp_path / "out"
    dest.mkdir()
    settings_dict = {
        "filename_datetime_format": "yyyymmddHH.XMM",
        "file_size_min": "900",
    }

    out = bfile.export_settings_to_folder(settings_dict, dest, template)
    text = out.read_text()

    assert "# RAW DATA" in text             # standalone section header kept
    assert "# File Settings" in text        # still has surviving settings
    assert "file_size_min=900" in text
    assert "file_ext" not in text           # dropped, but its header stays
    assert "# DIRECTORIES" not in text      # whole emptied section gone
    assert "dir_server" not in text


def test_find_settings_file_prefers_lowercase_and_accepts_legacy(tmp_path):
    # nothing there yet
    assert bfile.find_settings_file(tmp_path) is None

    # a legacy uppercase file is still found
    legacy = _write(tmp_path / "BICO.settings", "site=CH-DAV\n")
    found = bfile.find_settings_file(tmp_path)
    assert found is not None and found.name.lower() == "bico.settings"

    # the canonical lowercase name wins when both exist (case-sensitive FS only;
    # on a case-insensitive FS the two are the same file, which is also fine)
    lower = tmp_path / "bico.settings"
    if not lower.exists() or lower.samefile(legacy) is False:
        _write(lower, "site=CH-FRU\n")
        assert bfile.find_settings_file(tmp_path).name == "bico.settings"
