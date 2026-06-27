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


def test_run_snapshot_includes_all_keys_and_leaves_source_untouched(tmp_path):
    source = _write(tmp_path / "bico.settings", "site=CH-DAV\n")
    source_before = source.read_text()

    outdir = tmp_path / "run_out"
    outdir.mkdir()
    settings_dict = {
        "dir_settings": str(tmp_path),
        "site": "CH-DAV",
        "run_id": "BICO-xyz",
        "dir_out_run": str(outdir),
    }

    snapshot = bfile.write_run_settings_snapshot(settings_dict, outdir)
    snap_text = snapshot.read_text()

    # snapshot is a full provenance record (derived keys included)
    assert "site=CH-DAV" in snap_text
    assert "run_id=BICO-xyz" in snap_text
    # the source settings file is untouched by a run
    assert source.read_text() == source_before


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
