import tscat
from PySide6.QtCore import Signal, QObject
from PySide6.QtGui import QColor

from SciQLop.backend import TimeRange


class Event(QObject):
    range_changed = Signal(object)
    color_changed = Signal(QColor)

    def __init__(self, event: tscat._Event, catalog_uid: str):
        QObject.__init__(self)
        self._event = event
        self._catalog_uid = catalog_uid

    @property
    def range(self):
        return TimeRange(self._event.start.timestamp(), self._event.stop.timestamp())

    @property
    def start(self):
        return self._event.start.timestamp()

    @property
    def stop(self):
        return self._event.stop.timestamp()

    @property
    def catalog_uid(self):
        return self._catalog_uid

    @property
    def uuid(self):
        return self._event.uuid

    def set_range(self, time_range: TimeRange):
        self._event.start = time_range.datetime_start
        self._event.stop = time_range.datetime_stop
        self.range_changed.emit(self.range)
