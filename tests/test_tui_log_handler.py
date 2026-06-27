"""Tests for the TUI's logging->console bridge.

The bridge must capture both ways the engine emits logs:
* direct ``logger.info(...)`` calls (one record per ``StreamHandler`` write), and
* per-file worker logs that ``BicoEngine._replay_log`` writes *verbatim* into
  each handler's ``.stream`` as a multi-line block.

It must also split multi-line writes into individual styled widget lines. These
are validated with light fakes for the Textual app and RichLog widget, so the
test needs no running event loop.
"""
import logging

from bico.tui.log_handler import _style_for_line, _WidgetStream, format_log_line, make_tui_handler


class _FakeRichLog:
    def __init__(self):
        self.lines = []

    def write(self, renderable):
        # renderable is a rich.text.Text; record its plain text and style
        self.lines.append((renderable.plain, renderable.style))


class _FakeApp:
    """Stand-in for the Textual App: run the marshalled call synchronously."""
    def call_from_thread(self, fn, *args, **kwargs):
        return fn(*args, **kwargs)


def test_direct_logging_writes_one_line_per_record():
    widget = _FakeRichLog()
    logger = logging.getLogger("bico_test_direct")
    logger.handlers.clear()
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.addHandler(make_tui_handler(_FakeApp(), widget))

    logger.info("hello world")

    assert len(widget.lines) == 1
    text, _ = widget.lines[0]
    assert text.endswith("hello world")
    assert "| INFO" in text


def test_verbatim_replay_block_splits_into_lines():
    """Mirrors BicoEngine._replay_log writing a formatted multi-line block."""
    widget = _FakeRichLog()
    handler = make_tui_handler(_FakeApp(), widget)

    handler.stream.write("2026-01-01 00:00:00 | INFO    | a\n"
                         "2026-01-01 00:00:00 | INFO    | b\n")

    assert [t for t, _ in widget.lines] == [
        "2026-01-01 00:00:00 | INFO    | a",
        "2026-01-01 00:00:00 | INFO    | b",
    ]


def test_partial_writes_are_buffered_until_newline():
    widget = _FakeRichLog()
    stream = _WidgetStream(_FakeApp(), widget)
    stream.write("no newline yet")
    assert widget.lines == []           # nothing emitted without a newline
    stream.write(" and now\n")
    assert [t for t, _ in widget.lines] == ["no newline yet and now"]


def test_line_styling_by_level_marker():
    assert _style_for_line("... | ERROR   | boom") == "bold red"
    assert _style_for_line("... | WARNING | careful") == "yellow"
    assert _style_for_line("... | INFO    | (!) heads up") == "yellow"
    assert _style_for_line("... | INFO    | all good") is None


def test_format_log_line_preserves_text_and_adds_color():
    line = "2026-01-01 00:00:00 | INFO    | Converting 3 file(s)"
    text = format_log_line(line)
    # Plain text is byte-faithful (selection/copy + verbatim replay rely on this).
    assert text.plain == line
    # Styling is applied as spans (timestamp, level, number, keyword), not one blanket style.
    assert len(text.spans) > 1
    styles = " ".join(str(span.style) for span in text.spans)
    assert "cyan" in styles  # the INFO level / number / keyword colouring


def test_format_log_line_colors_error_red():
    text = format_log_line("2026-01-01 00:00:00 | ERROR   | boom")
    styles = " ".join(str(span.style) for span in text.spans)
    assert "red" in styles
