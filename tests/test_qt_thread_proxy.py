"""Kernel-thread code must not reach raw Qt widgets through `sciqlop_app()`.

Agent tools and notebook cells both run on the jupyqt kernel thread. A direct
Qt call from there is undefined behaviour — `main_window.resize(...)` aborts the
process inside `QQuickWidget::createFramebufferObject` (the WebEngine dock's GL
context is main-thread affine). `sciqlop_app()` used to hand out the raw
QApplication to any caller, so `sciqlop_app().topLevelWidgets()[0].resize(...)`
was a two-line crash from the kernel.
"""
import threading

import pytest
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QWidget

from SciQLop.core.sciqlop_application import SciQLopApp, sciqlop_app
from SciQLop.user_api.threading import init_invoker


class _Probe(QWidget):
    """Top-level widget recording the thread each call lands on."""

    ping = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("ThreadProbeWidget")
        self.called_on: str | None = None

    def record(self) -> str:
        self.called_on = threading.current_thread().name
        return self.called_on


@pytest.fixture
def invoker():
    """Install the same main-thread invoker KernelManager installs at runtime."""
    from jupyqt.qt.proxy import MainThreadInvoker
    init_invoker(MainThreadInvoker())
    yield
    init_invoker(None)


@pytest.fixture
def probe(qapp, qtbot):
    w = _Probe()
    qtbot.addWidget(w)
    yield w


def _in_worker(fn):
    """Run fn on a worker thread, return (result, exception) once it finishes."""
    box: dict = {}

    def run():
        try:
            box["result"] = fn()
        except BaseException as e:  # noqa: BLE001 — reported to the test
            box["error"] = e

    t = threading.Thread(target=run, name="fake-kernel-thread")
    t.start()
    return t, box


def test_sciqlop_app_on_main_thread_is_the_real_app(qapp):
    assert sciqlop_app() is qapp
    assert isinstance(sciqlop_app(), SciQLopApp)


def test_sciqlop_app_off_main_thread_marshals_calls(qapp, qtbot, invoker, probe):
    t, box = _in_worker(lambda: sciqlop_app().applicationName())

    qtbot.waitUntil(lambda: not t.is_alive(), timeout=5000)
    assert "error" not in box, box.get("error")
    assert box["result"] == qapp.applicationName()


def test_widgets_reached_from_a_worker_thread_run_on_the_gui_thread(
    qapp, qtbot, invoker, probe
):
    """The exact crash path: app → topLevelWidgets() list → widget call."""
    def work():
        app = sciqlop_app()
        w = [w for w in app.topLevelWidgets()
             if w.objectName() == "ThreadProbeWidget"][0]
        return w.record()

    t, box = _in_worker(work)

    qtbot.waitUntil(lambda: not t.is_alive(), timeout=5000)
    assert "error" not in box, box.get("error")
    assert box["result"] == threading.main_thread().name
    assert probe.called_on == threading.main_thread().name


def test_signals_survive_the_proxy(qapp, qtbot, invoker, probe):
    """A proxied QObject must still expose connectable signals, not a callable."""
    seen = []
    probe.ping.connect(lambda: seen.append(1), Qt.ConnectionType.DirectConnection)

    def work():
        app = sciqlop_app()
        w = [w for w in app.topLevelWidgets()
             if w.objectName() == "ThreadProbeWidget"][0]
        w.ping.connect(lambda: seen.append(2))
        return "connected"

    t, box = _in_worker(work)

    qtbot.waitUntil(lambda: not t.is_alive(), timeout=5000)
    assert "error" not in box, box.get("error")
    assert box["result"] == "connected"


def test_non_qobject_attributes_pass_through(qapp, qtbot, invoker):
    def work():
        return isinstance(sciqlop_app().applicationName(), str)

    t, box = _in_worker(work)
    qtbot.waitUntil(lambda: not t.is_alive(), timeout=5000)
    assert "error" not in box, box.get("error")
    assert box["result"] is True


def test_qobject_identity_is_reachable_through_the_proxy(qapp, qtbot, invoker, probe):
    """`unwrap` gives GUI-thread code the raw object back (no double wrapping)."""
    from SciQLop.user_api.threading import unwrap

    def work():
        return unwrap(sciqlop_app()) is qapp

    t, box = _in_worker(work)
    qtbot.waitUntil(lambda: not t.is_alive(), timeout=5000)
    assert "error" not in box, box.get("error")
    assert box["result"] is True
    assert unwrap(qapp) is qapp
    assert unwrap(probe) is probe
    assert isinstance(unwrap(QObject()), QObject)
