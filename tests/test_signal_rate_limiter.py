from .fixtures import *
import pytest
from pytestqt import qt_compat
from pytestqt.qt_compat import qt_api
from SciQLop.backend.common import SignalRateLimiter

values = []


def test_signal_rate_limiter(qtbot, qapp):
    from PySide6.QtCore import Signal, QObject

    class TestObject(QObject):
        test_signal = Signal(int)

    obj = TestObject()

    def callback(value):
        global values
        print(value)
        values.append(value)

    rate_limiter = SignalRateLimiter(obj.test_signal, 10, callback)
    for i in range(1000):
        obj.test_signal.emit(i)
        qapp.processEvents()
    for i in range(100):
        qtbot.wait(1)
        qapp.processEvents()
    global values
    assert len(values) > 0  # at least one value should be emitted
    assert len(values) < 1000  # only a few values should be emitted
    assert values[-1] == 999  # the last value should not be discarded
