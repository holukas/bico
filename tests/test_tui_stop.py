"""The Stop button wiring.

Stop is disabled until a conversion is running; pressing it sets the engine's
stop flag and disables itself again. The engine then winds the run down between
files (covered by the engine-level behaviour, not here). Driven through a
headless Textual app, so no real conversion runs.
"""
import asyncio

from textual.widgets import Button

from bico.tui.app import BicoApp


def _run(coro):
    return asyncio.run(coro)


def _stop_flow():
    async def scenario():
        app = BicoApp()
        async with app.run_test() as pilot:
            stop = app.query_one('#btn-stop', Button)
            initial_disabled = stop.disabled

            # Simulate an in-progress run (without launching the real engine).
            app._busy = True
            app._stop_event.clear()
            stop.disabled = False

            app.action_stop_conversion()
            await pilot.pause()
            return initial_disabled, app._stop_event.is_set(), stop.disabled

    return _run(scenario())


def test_stop_button_disabled_until_running_then_signals_engine():
    initial_disabled, event_set_after_stop, disabled_after_stop = _stop_flow()
    assert initial_disabled is True          # nothing to stop before a run
    assert event_set_after_stop is True      # pressing Stop signals the engine
    assert disabled_after_stop is True       # and re-disables itself (one shot)


def test_stop_is_noop_when_not_running():
    async def scenario():
        app = BicoApp()
        async with app.run_test() as pilot:
            app._busy = False
            app.action_stop_conversion()
            await pilot.pause()
            return app._stop_event.is_set()

    assert _run(scenario()) is False
