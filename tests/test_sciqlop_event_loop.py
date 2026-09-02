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


def test_main_exits_with_code_1_when_startup_raises(qapp, monkeypatch):
    """C4 reproducer: sciqlop_app.main() defers the whole startup sequence via
    QTimer.singleShot(0, ...); if start_sciqlop() raises there, the exception
    used to be printed by PySide6's default hook and the qasync loop kept
    spinning forever (no window, no ready file -- the launcher's splash would
    wait forever). main() must instead record exit code 1 and quit, exactly
    like the existing (non-fatal) main_windows.start() failure path is
    expected to keep working.

    Reuses the module-level event loop singleton from
    SciQLop.core.sciqlop_application (the same one the test above operates
    on), rewiring aboutToQuit to a fresh asyncio.Event for the duration of
    the test so this is the first thing to ever drive it through a real
    exec() -- and restoring the original wiring afterward so a later test in
    the same process isn't left with a loop whose app_close_event is
    permanently set.
    """
    from PySide6.QtCore import QTimer
    import SciQLop.sciqlop_app as sciqlop_app_module
    from SciQLop.core.sciqlop_application import sciqlop_event_loop

    def _boom():
        raise RuntimeError("startup exploded")

    monkeypatch.setattr(sciqlop_app_module, "start_sciqlop", _boom)

    loop = sciqlop_event_loop()
    # _SciQLopEventLoop.exec() runs `with self: ...`, and qasync's
    # QEventLoop.__exit__ unconditionally closes the loop -- fine for the real
    # app (one exec() call, then the process exits), fatal for this
    # process-lifetime test singleton (a later test's sciqlop_event_loop()
    # would get back a loop with `_closed=True`). Keep close() a no-op for the
    # duration of this test so the singleton survives for whatever runs next.
    monkeypatch.setattr(loop, "close", lambda: None)
    original_event = loop.app_close_event
    qapp.aboutToQuit.disconnect(original_event.set)
    fresh_event = asyncio.Event()
    loop.app_close_event = fresh_event
    qapp.aboutToQuit.connect(fresh_event.set)
    # Without the fix, an exception raised inside the QTimer.singleShot(0, ...)
    # callback is swallowed by PySide6's default hook and nothing ever calls
    # quit() -- loop.exec() below would hang forever instead of failing fast.
    # This watchdog turns that hang into a bounded, readable test failure.
    watchdog = QTimer()
    watchdog.setSingleShot(True)
    watchdog.timeout.connect(fresh_event.set)
    watchdog.start(5000)
    try:
        sciqlop_app_module.main()
        assert watchdog.isActive(), "main() did not return before the watchdog fired (loop hung)"
        assert getattr(qapp, "_sciqlop_exit_code", None) == 1
    finally:
        watchdog.stop()
        qapp.aboutToQuit.disconnect(fresh_event.set)
        loop.app_close_event = original_event
        qapp.aboutToQuit.connect(original_event.set)


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
