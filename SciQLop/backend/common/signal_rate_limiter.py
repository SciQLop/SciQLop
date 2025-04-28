from PySide6.QtCore import QTimer


class SignalRateLimiter:

    def __init__(self, signal, delay, callback, max_delay=None):
        self.signal = signal
        self.delay = delay
        self.callback = callback
        self.max_delay = max_delay
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.setInterval(self.delay)
        self.timer.timeout.connect(self._timeout)
        if max_delay is not None:
            self.max_delay_timer = QTimer()
            self.max_delay_timer.setSingleShot(True)
            self.max_delay_timer.setInterval(self.max_delay)
            self.max_delay_timer.timeout.connect(self._timeout)
        self.signal.connect(self._trigger)
        self._args = []
        self._kwargs = {}

    def _trigger(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs
        self.timer.start()
        if self.max_delay is not None and not self.max_delay_timer.isActive():
            self.max_delay_timer.start()

    def _timeout(self):
        if self.max_delay is not None and not self.max_delay_timer.isActive():
            self.timer.stop()
        self.callback(*self._args, **self._kwargs)
