"""Build a self-contained HTML viewer for a run's log file.

A run logs to a plain ``{run_id}.log`` file as before. When the run finishes,
``write_log_html`` renders a single self-contained HTML page next to it
(``{run_id}.log.html``) with the log embedded, so it opens straight into the
searchable, colour-coded viewer — no server, no internet, nothing uploaded.

The viewer markup lives in ``log_viewer_template.html`` (which also works as a
standalone drag-and-drop viewer). Building a per-run page just injects the log as
a JavaScript string at the ``/*BICO_EMBED*/`` marker; the page's own JS does the
parsing and rendering in the browser, so this stays fast even for large logs.
"""
import json
from pathlib import Path

TEMPLATE_PATH = Path(__file__).resolve().parent / 'log_viewer_template.html'
_EMBED_MARKER = '/*BICO_EMBED*/'


def _js_string(s: str) -> str:
    """JSON-encode a string for safe embedding inside a <script> tag.

    Escaping every ``<`` as ``\\u003c`` ensures the embedded text can never form a
    closing ``</script>`` (or ``<!--``) that would terminate the script block.
    """
    return json.dumps(s).replace('<', '\\u003c')


def build_log_html(log_text: str, source_name: str) -> str:
    """Return the viewer HTML with ``log_text`` embedded for auto-loading."""
    template = TEMPLATE_PATH.read_text(encoding='utf-8')
    payload = (f"window.__BICO_LOG__={_js_string(log_text)};"
               f"window.__BICO_NAME__={_js_string(source_name)};")
    if _EMBED_MARKER in template:
        return template.replace(_EMBED_MARKER, payload, 1)
    # Marker missing (edited template): fall back to injecting before </head>.
    return template.replace('</head>', f'<script>{payload}</script></head>', 1)


def write_log_html(logfile_path, html_path=None):
    """Render an HTML viewer for ``logfile_path`` and write it alongside the log.

    Returns the written HTML path (default: ``<logfile>.html``).
    """
    logfile_path = Path(logfile_path)
    log_text = logfile_path.read_text(encoding='utf-8')
    if html_path is None:
        html_path = logfile_path.parent / (logfile_path.name + '.html')
    html_path = Path(html_path)
    html_path.write_text(build_log_html(log_text, logfile_path.name), encoding='utf-8')
    return html_path
