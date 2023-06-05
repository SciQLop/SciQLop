import tscat
from PySide6.QtCore import Signal, QObject
from SciQLop.backend import TimeRange


class Event(QObject):
    range_changed = Signal(object)

    def __init__(self, event: tscat._Event):
        QObject.__init__(self)
        self._event = event

    @property
    def range(self):
        return TimeRange(self._event.start.timestamp(), self._event.stop.timestamp())

    @property
    def start(self):
        return self._event.start.timestamp()

    @property
    def stop(self):
        return self._event.stop.timestamp()

    def set_range(self, time_range: TimeRange):
        self._event.start = time_range.datetime_start
        self._event.stop = time_range.datetime_stop
        self.range_changed.emit(self.range)
