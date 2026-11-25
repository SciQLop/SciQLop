"""SCIQLOP_STARTUP_TIMINGS=1 prints how long each startup phase took and every stall of the GUI thread
after the window shows, with where it was: what to ask for when startup feels slow on someone's machine."""
import time

from SciQLop.core import startup_timing


def test_nothing_is_printed_without_the_variable(monkeypatch, capsys):
    monkeypatch.delenv(startup_timing.ENV, raising=False)
    with startup_timing.phase("plugins"):
        pass
    assert capsys.readouterr().err == ""


def test_a_phase_says_how_long_it_took(monkeypatch, capsys):
    monkeypatch.setenv(startup_timing.ENV, "1")
    with startup_timing.phase("plugins"):
        time.sleep(0.05)
    [line] = capsys.readouterr().err.splitlines()
    assert line.startswith("[startup] plugins: 0.0") and line.endswith("s from start)")


def test_a_gui_stall_after_show_is_reported_with_where_it_was(monkeypatch, capsys, qtbot, qapp):
    from PySide6.QtCore import QTimer
    monkeypatch.setenv(startup_timing.ENV, "1")
    watch = startup_timing.watch_gui(seconds=2)

    def stall_the_gui_thread():
        time.sleep(0.3)

    QTimer.singleShot(100, stall_the_gui_thread)
    qtbot.waitUntil(lambda: bool(watch.stalls), timeout=3000)
    watch.stop()
    err = capsys.readouterr().err
    assert "[startup] GUI blocked" in err and "stall_the_gui_thread" in err
