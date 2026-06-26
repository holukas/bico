"""Bridge the engine's stdlib logging into the TUI's on-screen console.

``BicoEngine`` logs in two ways:

* the main process calls ``logger.info(...)`` directly, and
* per-file worker logs are captured in subprocesses and later *replayed* by
  writing their already-formatted text verbatim into each handler's ``.stream``
  (see ``BicoEngine._replay_log``).

To capture both, the TUI handler is an ordinary ``logging.StreamHandler`` whose
stream is a small adapter that forwards written text — line by line — to a
Textual ``RichLog`` widget. Writes are marshalled onto the UI thread with
``app.call_from_thread`` because the engine runs in a worker thread.
"""
import logging

from rich.text import Text

from bico.ops.logger import get_formatter


def _style_for_line(line: str):
    """Pick a Rich style from an already-formatted log line."""
    if '| ERROR' in line or '| CRITICAL' in line:
        return 'bold red'
    if '| WARNING' in line:
        return 'yellow'
    if '(!)' in line:
        return 'yellow'
    return None


class _WidgetStream:
    """File-like object that forwards written text to a RichLog widget.

    Buffers partial writes and emits one widget line per newline, so both
    ``StreamHandler`` emits (one record per write) and verbatim multi-line
    replays render as clean, individually styled lines.
    """

    def __init__(self, app, richlog):
        self._app = app
        self._richlog = richlog
        self._buffer = ''

    def write(self, text: str):
        self._buffer += text
        while '\n' in self._buffer:
            line, self._buffer = self._buffer.split('\n', 1)
            self._emit(line)

    def flush(self):
        if self._buffer:
            self._emit(self._buffer)
            self._buffer = ''

    def _emit(self, line: str):
        renderable = Text(line, style=_style_for_line(line))
        # The engine runs in a worker thread; hop onto the UI thread to write.
        self._app.call_from_thread(self._richlog.write, renderable)


def make_tui_handler(app, richlog) -> logging.Handler:
    """A logging handler that writes formatted, styled lines to a RichLog."""
    handler = logging.StreamHandler(_WidgetStream(app, richlog))
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(get_formatter())
    return handler
