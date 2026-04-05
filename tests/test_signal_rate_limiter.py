from SciQLop.core.common import SignalRateLimiter

values = []


def test_signal_rate_limiter(qtbot, qapp):
    from PySide6.QtCore import Signal, QObject

    class TestObject(QObject):
        test_signal = Signal(int)

    obj = TestObject()

    def callback(value):
        global values # noqa: F824
        print(value)
        values.append(value)

    rate_limiter = SignalRateLimiter(obj.test_signal, 10, callback)
    for i in range(1000):
        obj.test_signal.emit(i)
        qapp.processEvents()
    for i in range(100):
        qtbot.wait(1)
        qapp.processEvents()
    assert len(values) > 0  # at least one value should be emitted
    assert len(values) < 1000  # only a few values should be emitted
    assert values[-1] == 999  # the last value should not be discarded


def test_signal_rate_limiter_max_delay_no_double_callback(qtbot, qapp):
    """Reproducer for double-callback bug: when max_delay is set, both timers
    could fire _timeout independently, invoking the callback twice for a single
    logical event burst."""
    from PySide6.QtCore import Signal, QObject

    class TestObject(QObject):
        test_signal = Signal(int)

    obj = TestObject()
    calls = []

    def callback(value):
        calls.append(value)

    # delay=10ms, max_delay=50ms — a single emission should produce exactly one callback
    limiter = SignalRateLimiter(obj.test_signal, 10, callback, max_delay=50)

    obj.test_signal.emit(42)
    qapp.processEvents()

    # Wait long enough for both timers to have fired (>50ms)
    qtbot.wait(200)
    qapp.processEvents()

    assert calls == [42], f"Expected exactly one callback, got {len(calls)}: {calls}"


def test_signal_rate_limiter_max_delay_fires_before_regular(qtbot, qapp):
    """When signals keep retriggering the short timer, max_delay timer should
    fire once and the short timer should not fire again afterward."""
    from PySide6.QtCore import Signal, QObject

    class TestObject(QObject):
        test_signal = Signal(int)

    obj = TestObject()
    calls = []

    def callback(value):
        calls.append(value)

    # Short delay=30ms, max_delay=80ms
    # Emit every 20ms for 150ms — the short timer keeps restarting,
    # so max_delay fires first at ~80ms. After that, no double fire.
    limiter = SignalRateLimiter(obj.test_signal, 30, callback, max_delay=80)

    for i in range(8):
        obj.test_signal.emit(i)
        qtbot.wait(20)
        qapp.processEvents()

    # Wait for all timers to settle
    qtbot.wait(200)
    qapp.processEvents()

    # max_delay should have fired at ~80ms, then short timer at ~last_emit+30ms
    # but each should fire at most once — no double callback for the same burst
    assert len(calls) >= 1, "Should have at least one callback"
    # The key invariant: no two consecutive calls with the same value
    for i in range(1, len(calls)):
        assert calls[i] != calls[i - 1], f"Double callback detected: {calls}"
