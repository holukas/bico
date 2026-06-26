"""Tests for the per-run HTML log viewer builder (bico.ops.log_report).

A run writes a plain .log; when it ends, the engine renders a self-contained
HTML viewer next to it with the log embedded. These tests lock in that the embed
is safe (cannot break out of the <script> tag) and that the file is written.
"""
from bico.ops import log_report


def test_template_has_embed_marker():
    template = log_report.TEMPLATE_PATH.read_text(encoding="utf-8")
    assert log_report._EMBED_MARKER in template


def test_build_embeds_log_and_is_script_safe():
    # A log line that would break a naive embed: it contains </script>.
    log = "2026-06-26 13:40:02 | INFO    | tricky </script><b>x & y < z\n"
    template = log_report.TEMPLATE_PATH.read_text(encoding="utf-8")
    html = log_report.build_log_html(log, "run.log")

    # The marker is gone (replaced by the payload) and the globals are set.
    assert log_report._EMBED_MARKER not in html
    assert "window.__BICO_LOG__=" in html
    assert "window.__BICO_NAME__=" in html
    # Embedding must not introduce any new real </script> closers: every '<' in
    # the log is escaped to \\u003c, so it cannot terminate the script block.
    assert "\\u003c/script>" in html
    assert html.count("</script>") == template.count("</script>")


def test_write_log_html_creates_file_next_to_log(tmp_path):
    logfile = tmp_path / "BICO-xyz.log"
    logfile.write_text(
        "2026-06-26 13:40:02 | INFO    | Run ID: BICO-xyz\n"
        "2026-06-26 13:40:03 | ERROR   | (!) something failed\n",
        encoding="utf-8",
    )
    out = log_report.write_log_html(logfile)

    assert out == tmp_path / "BICO-xyz.log.html"
    assert out.is_file()
    html = out.read_text(encoding="utf-8")
    assert "Run ID: BICO-xyz" in html
    assert "window.__BICO_NAME__=" in html
    assert "BICO-xyz.log" in html  # source name embedded
