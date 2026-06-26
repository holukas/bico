"""Layout regression: the lower settings fields must stay reachable.

The action bar (Save/Validate/Test/Run) is docked to the bottom of the settings
pane so it reserves its own row instead of overlapping the scrollable fields. It
previously overlapped them on short terminals, which hid the lowest fields (e.g.
the output folder) behind the Validate button — they could not be focused, so
drag-and-drop (which targets the focused field) silently failed for them.
"""
import asyncio

from bico.tui.app import BicoApp, PathDropInput, _field_id


def _run(coro):
    return asyncio.run(coro)


def _click_output_focuses_it(size):
    async def scenario():
        app = BicoApp()
        async with app.run_test(size=size) as pilot:
            out = app.query_one(f'#{_field_id("dir_out")}', PathDropInput)
            out.scroll_visible(animate=False)
            await pilot.pause()
            await pilot.pause()  # let the scroll settle before clicking
            await pilot.click(f'#{_field_id("dir_out")}')
            await pilot.pause()
            return getattr(app.focused, 'id', None)

    return _run(scenario())


def test_output_field_focusable_on_short_terminal():
    # On a short terminal the output field used to be hidden behind the action
    # bar, so clicking it focused the Validate button instead.
    focused = _click_output_focuses_it((80, 24))
    assert focused == _field_id("dir_out"), f"clicking output focused {focused!r}"
