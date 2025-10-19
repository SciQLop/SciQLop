from PySide6.QtCore import Signal, QObject, QTimer, Slot
from PySide6.QtGui import QColor
from humanize.time import precisedelta

from SciQLop.backend import TimeRange

from tscat_gui.tscat_driver.model import tscat_model
from tscat_gui.tscat_driver.actions import SetAttributeAction


class Event(QObject):
    range_changed = Signal(object)
    color_changed = Signal(QColor)
    selection_changed = Signal(bool)

    def __init__(self, uuid: str, catalog_uid: str):
        QObject.__init__(self)
        self._uuid = uuid
        self._catalog_uid = catalog_uid
        self._current_range = self.range
        self._range_to_apply = self._current_range
        self._deferred_apply = QTimer(self)
        self._deferred_apply.setSingleShot(True)
        self._deferred_apply.timeout.connect(self._apply_changes)

    def _apply_start(self):
        tscat_model.do(SetAttributeAction(user_callback=None, uuids=[self.uuid], name="start",
                                          values=[self._range_to_apply.datetime_start()]))
        self._current_range[0] = self._range_to_apply.start()

    def _apply_stop(self):
        tscat_model.do(SetAttributeAction(user_callback=None, uuids=[self.uuid], name="stop",
                                          values=[self._range_to_apply.datetime_stop()]))
        self._current_range[1] = self._range_to_apply.stop()

    @Slot()
    def _apply_changes(self):
        if self._current_range.start() != self._range_to_apply.start():
            if self._range_to_apply.start() > self._current_range.stop():
                self._apply_stop()
                self._apply_start()
            else:
                self._apply_start()
        if self._current_range.stop() != self._range_to_apply.stop():
            self._apply_stop()

    @property
    def _event(self):
        return tscat_model.entities_from_uuids([self._uuid])[0]

    @property
    def range(self):
        return TimeRange(self._event.start.timestamp(), self._event.stop.timestamp())

    @property
    def start(self):
        return self._event.start()

    @property
    def stop(self):
        return self._event.stop()

    @property
    def catalog_uid(self):
        return self._catalog_uid

    @property
    def uuid(self):
        return self._uuid

    @property
    def tooltip(self):
        return f"""<b>Author: </b>{self._event.author} <br><hr>
<b>Tags: </b>{' '.join(self._event.tags)} <br><hr>
<b>Duration: </b>{precisedelta(self._event.stop - self._event.start)} <br><hr>
<b>Rating: </b>{self._event.rating} <br><hr>
<b>Attributes:</b>
<table>
    {''.join([f'<tr><td>{key}</td><td>{value}</td></tr>' for key, value in self._event.variable_attributes().items()])}
</table>
        """

    def set_range(self, time_range: TimeRange):
        if self._range_to_apply != time_range:
            self._range_to_apply = time_range
            self._deferred_apply.start(10)
            self.range_changed.emit(time_range)
