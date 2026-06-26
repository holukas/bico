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
