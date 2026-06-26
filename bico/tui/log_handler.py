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

Lines arrive already formatted as ``"<ts> | <LEVEL> | <message>"`` (see
``bico.ops.logger``). ``format_log_line`` turns each into a richly styled
``rich.text.Text`` for the console. The saved log file stays plain text — only
the on-screen console is colored.
"""
import logging
import re

from rich.text import Text

from bico.ops.logger import get_formatter

# Colour per log level (applied to the level column).
LEVEL_STYLES = {
    'DEBUG': 'grey50',
    'INFO': 'cyan',
    'WARNING': 'bold yellow',
    'ERROR': 'bold red',
    'CRITICAL': 'bold white on red',
}
_TS_STYLE = 'grey42'
_SEP_STYLE = 'grey30'

# Message highlighting (order matters: later rules win on overlap).
_BRACKET_RE = re.compile(r'\[[^\]]*\]')          # [units] / [datablock] / [FILE]
_NUMBER_RE = re.compile(r'(?<![\w.])-?\d[\d_,]*(?:\.\d+)?')
_FILE_BANNER_RE = re.compile(r'^\s*\[[^\]]+\]\s*$')   # a whole-line [filename] banner
_PATH_RE = re.compile(r'(?:[A-Za-z]:\\|\.{0,2}/)[^\s]+')
_VAR_LINE_RE = re.compile(r'^\s*#\d+\s+(\S+)')        # "    #25    STATUS_WORD ..."

# Words that signal success / progress, coloured where they appear.
_KEYWORD_STYLES = (
    ('FINISHED', 'bold green'),
    ('finished', 'green'),
    ('Finished', 'green'),
    ('Saving', 'green'),
    ('Saved', 'green'),
    ('converted', 'green'),
    ('Done', 'green'),
    ('Converting', 'bold cyan'),
    ('Processing', 'bold cyan'),
    ('Found', 'bold cyan'),
    ('Run ID', 'bold cyan'),
    ('BICO Version', 'bold cyan'),
    ('ERROR', 'bold red'),
    ('skipped', 'yellow'),
    ('DUPLICATE', 'yellow'),
)


def _style_for_line(line: str):
    """Pick a single Rich style for a whole line (kept for simple callers/tests)."""
    if '| ERROR' in line or '| CRITICAL' in line:
        return 'bold red'
    if '| WARNING' in line:
        return 'yellow'
    if '(!)' in line:
        return 'yellow'
    return None


def _format_message(msg: str, level: str) -> Text:
    """Style the message part of a log line, returning Text with msg unchanged."""
    text = Text(msg)
    stripped = msg.strip()

    # Horizontal rule banners (==== / ---- / ____): one calm accent colour.
    if stripped and set(stripped) <= set('=-_'):
        text.stylize('blue')
        return text

    # Errors/warnings: colour the whole message, no further highlighting needed.
    if level in ('ERROR', 'CRITICAL'):
        text.stylize('bold red')
        return text
    if level == 'WARNING':
        text.stylize('yellow')

    # A line that is just a file banner, e.g. "[2023101101.Y00]".
    if _FILE_BANNER_RE.match(msg):
        text.stylize('bold magenta')
        return text

    # Variable header lines ("    #25    STATUS_WORD [units] [datablock]"): make
    # the variable name stand out.
    var_line = _VAR_LINE_RE.match(msg)
    if var_line:
        text.stylize('bold', var_line.start(1), var_line.end(1))

    # Bracketed tokens and paths first (muted), then numbers (bright), then
    # keywords on top, so the eye lands on counts and status words.
    text.highlight_regex(_BRACKET_RE, 'grey58')
    text.highlight_regex(_PATH_RE, 'cyan')
    text.highlight_regex(_NUMBER_RE, 'bright_cyan')
    for word, style in _KEYWORD_STYLES:
        if word in msg:
            text.highlight_words([word], style)
    if '(!)' in msg:
        text.highlight_words(['(!)'], 'bold yellow')
    return text


def format_log_line(line: str) -> Text:
    """Turn a formatted log line into a richly coloured Text.

    The plain text is preserved exactly (so selection/copy and the verbatim
    replay stay byte-faithful); only styles are added.
    """
    parts = line.split(' | ', 2)
    if len(parts) != 3:
        # Not the expected "ts | LEVEL | msg" shape: colour as a bare message.
        return _format_message(line, 'INFO')
    ts, level, msg = parts
    text = Text()
    text.append(ts, style=_TS_STYLE)
    text.append(' | ', style=_SEP_STYLE)
    text.append(level, style=LEVEL_STYLES.get(level.strip(), 'white'))
    text.append(' | ', style=_SEP_STYLE)
    text.append_text(_format_message(msg, level.strip()))
    return text


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
        renderable = format_log_line(line)
        # The engine runs in a worker thread; hop onto the UI thread to write.
        self._app.call_from_thread(self._richlog.write, renderable)


def make_tui_handler(app, richlog) -> logging.Handler:
    """A logging handler that writes formatted, styled lines to a RichLog."""
    handler = logging.StreamHandler(_WidgetStream(app, richlog))
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(get_formatter())
    return handler
