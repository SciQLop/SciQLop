"""Reproduces a real startup bug: sciqlop_app.py used to construct the qasync
event loop, then build the whole MainWindow (pumping Qt events with several
app.processEvents() calls) *before* ever calling sciqlop_event_loop().exec().
qasync only calls asyncio.events._set_running_loop() inside its own
run_forever()/run_until_complete() -- i.e. once exec() actually runs. Any
asyncio Task created before that point (e.g. an agent-backend plugin's load()
eagerly binding a chat session -- chat_dock.py's AgentChatDock.__init__ ->
refresh_backends() -> _bind_to_session() -> _spawn(_prepare_session)) got its
first step dispatched by one of those processEvents() calls while the loop's
own "is this the running loop" bookkeeping still said no -- surfacing as
"RuntimeError: <loop> is not the running loop" (silently tolerated on Python
3.13, a hard error on 3.14; a real ordering bug either way, reproduced live
against the actual AppImage on both versions).

Fix: sciqlop_app.py's main() now defers the whole startup sequence (building
MainWindow, loading plugins, ...) to run via QTimer.singleShot(0, ...)
scheduled *before* calling loop.exec() -- so it executes as the first thing
Qt dispatches once the loop is genuinely marked running by qasync's own
run_forever()/run_until_complete(), instead of manually pumping Qt events
ahead of exec() ever being entered.

This test pins the underlying invariant that fix relies on directly, without
going through Qt's quit()/aboutToQuit lifecycle at all (which has its own,
separate, pre-existing shutdown-timing quirk around app_close_event.wait() --
unrelated to this bug and not exercised here): once the loop is genuinely
marked as the running loop, scheduling and stepping a Task through it must
not raise, regardless of Python version.
"""
import asyncio


def test_task_step_succeeds_once_loop_is_marked_running(qapp):
    from SciQLop.core.sciqlop_application import sciqlop_event_loop

    loop = sciqlop_event_loop()
    errors = []
    # loop is the process-lifetime singleton (module-level cache in
    # sciqlop_application.py) shared with every other GUI test in this
    # session — restore its exception handler afterward so a later test
    # doesn't silently lose its own exceptions into this one's now-gone
    # `errors` list.
    previous_handler = loop.get_exception_handler()
    loop.set_exception_handler(lambda loop, context: errors.append(context))

    async def _noop():
        return None

    try:
        # Mirrors what qasync's own run_forever()/run_until_complete() does
        # before handing control to Qt's real event loop.
        asyncio.events._set_running_loop(loop)
        try:
            asyncio.ensure_future(_noop(), loop=loop)
            qapp.processEvents()
            qapp.processEvents()
        finally:
            asyncio.events._set_running_loop(None)
    finally:
        loop.set_exception_handler(previous_handler)

    assert not errors, errors
