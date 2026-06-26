"""The log console must support mouse text selection and copy.

Plain ``RichLog`` does not implement Textual's selection hooks, so dragging over
it selects nothing. ``SelectableRichLog`` adds offset stamping, highlight
rendering, and text extraction. These checks drive that logic through a headless
Textual app (no real terminal / mouse needed).
"""
import asyncio

from textual.geometry import Offset
from textual.selection import Selection

from bico.tui.app import BicoApp, SelectableRichLog


def _run(coro):
    return asyncio.run(coro)


def _exercise():
    async def scenario():
        app = BicoApp()
        async with app.run_test(size=(100, 30)) as pilot:
            log = app.query_one('#console', SelectableRichLog)
            log.clear()
            for line in ('line one', 'line two', 'line three'):
                log.write(line)
            await pilot.pause()

            # Multi-line selection: from start of line 0 to column 4 of line 2.
            sel = Selection(Offset(0, 0), Offset(4, 2))
            extracted, ending = log.get_selection(sel)

            # With the selection active, render the lines to ensure the highlight
            # path runs without error and emits strips of the expected width.
            app.screen.selections = {log: sel}
            await pilot.pause()
            strips = [log.render_line(y) for y in range(3)]
            widths = [s.cell_length for s in strips]

            # Selected cells must keep a visible foreground AND gain a background
            # (regression guard: the theme's selection fg is "transparent", which
            # as a base style would make plain text invisible).
            seg = next(s for s in strips[0]._segments if s.text.strip())
            fg_ok = seg.style is not None and seg.style.color is not None
            bg_ok = seg.style is not None and seg.style.bgcolor is not None

            # And copy via the screen plumbing returns the same text.
            copied = app.screen.get_selected_text()
            return extracted, ending, widths, copied, fg_ok, bg_ok

    return _run(scenario())


def test_log_selection_extract_render_and_copy():
    extracted, ending, widths, copied, fg_ok, bg_ok = _exercise()
    assert extracted == 'line one\nline two\nline'
    assert ending == '\n'
    assert copied == 'line one\nline two\nline'
    # Every rendered line spans the full content width (highlight didn't truncate).
    assert all(w == widths[0] for w in widths) and widths[0] > 0
    # Selected text stays visible (foreground kept) and is highlighted (background set).
    assert fg_ok, 'selected text lost its foreground colour (would be invisible)'
    assert bg_ok, 'selected text has no highlight background'


def test_ctrl_c_copies_console_selection():
    async def scenario():
        app = BicoApp()
        async with app.run_test(size=(120, 30)) as pilot:
            log = app.query_one('#console', SelectableRichLog)
            log.focus()
            log.clear()
            for line in ('alpha beta', 'gamma delta'):
                log.write(line)
            await pilot.pause()
            app.screen.selections = {log: Selection(Offset(0, 0), Offset(5, 1))}
            await pilot.pause()
            await pilot.press('ctrl+c')   # must copy, not show the quit hint
            await pilot.pause()
            return app.clipboard

    assert _run(scenario()) == 'alpha beta\ngamma'
