"""Parallel runs show one progress line per in-progress file.

The live status area keeps a line per file currently converting (several run at
once across worker processes) and drops a file's line when it finishes. Driven
through a headless Textual app.
"""
import asyncio

from textual.widgets import Static

from bico.tui.app import BicoApp


def _run(coro):
    return asyncio.run(coro)


def _scenario():
    async def go():
        app = BicoApp()
        async with app.run_test(size=(120, 40)) as pilot:
            status = app.query_one('#run-status', Static)
            # Three files converting concurrently.
            app._update_file_status(1, 5, 'a.X00', 'Converting', 0.30)
            app._update_file_status(2, 5, 'b.X00', 'Converting', 0.55)
            app._update_file_status(3, 5, 'c.X00', 'Saving CSV', 0.90)
            await pilot.pause()
            three = status.render().plain
            # One file finishes -> its line is removed.
            app._update_file_status(2, 5, 'b.X00', 'Done', 1.0)
            await pilot.pause()
            two = status.render().plain
            return three, two, sorted(app._file_status)

    return _run(go())


def test_one_line_per_inprogress_file():
    three, two, remaining = _scenario()
    lines3 = three.splitlines()
    assert len(lines3) == 3
    assert any('a.X00' in l and '30%' in l for l in lines3)
    assert any('b.X00' in l and '55%' in l for l in lines3)
    assert any('c.X00' in l and 'Saving CSV' in l for l in lines3)
    # After b finishes, only a and c remain, on their own lines.
    assert len(two.splitlines()) == 2
    assert 'b.X00' not in two
    assert remaining == [1, 3]
