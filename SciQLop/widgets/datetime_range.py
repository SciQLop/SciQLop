from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QDateTimeEdit, QWidgetAction
from PySide6.QtGui import QMouseEvent, QDrag, QPixmap
from PySide6.QtCore import Qt, QMimeData, Signal
from ..mime import register_mime, encode_mime
from ..mime.types import TIME_RANGE_MIME_TYPE
from ..backend import TimeRange
import pickle


def _QDateTimeEdit(parent):
    widget = QDateTimeEdit(parent)
    widget.setDisplayFormat("dd/MM/yyyy HH:mm:ss:zzz")
    widget.setCalendarPopup(True)
    widget.setTimeSpec(Qt.TimeSpec.UTC)
    return widget


class DateTimeRangeWidget(QWidget):
    range_changed = Signal(TimeRange)

    def __init__(self, parent=None, default_time_range: TimeRange = None):
        QWidget.__init__(self, parent)
        self.setLayout(QHBoxLayout())
        self._start_date = _QDateTimeEdit(self)
        self._stop_date = _QDateTimeEdit(self)
        self.layout().addWidget(QLabel("TStart:"))
        self.layout().addWidget(self._start_date)
        self.layout().addWidget(QLabel("TStop:"))
        self.layout().addWidget(self._stop_date)
        if default_time_range is not None:
            self._start_date.setDateTime(default_time_range.start)
            self._stop_date.setDateTime(default_time_range.stop)
        self._start_date.dateTimeChanged.connect(lambda dtr: self.range_changed.emit(
            TimeRange(self._start_date.dateTime().toPython(), self._stop_date.dateTime().toPython())))
        self._stop_date.dateTimeChanged.connect(lambda dtr: self.range_changed.emit(
            TimeRange(self._start_date.dateTime().toPython(), self._stop_date.dateTime().toPython())))

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            drag = QDrag(self)
            drag.setMimeData(
                encode_mime(TimeRange(self._start_date.dateTime().toPython(), self._stop_date.dateTime().toPython())))
            drag.setPixmap(QPixmap("://icons/time.png").scaledToHeight(32))
            drag.exec()

    """
    void TimeWidget::mousePressEvent(QMouseEvent *event)
{
  if (event->button() == Qt::LeftButton) {

    QDrag *drag = new QDrag(this);
    drag->setMimeData(MIME::mimeData(timeRange()));
    drag->setPixmap(QPixmap{"://icons/time.png"}.scaledToHeight(32));

    Qt::DropAction dropAction = drag->exec();

  }
}
    """


class DateTimeRangeWidgetAction(QWidgetAction):
    range_changed = Signal(TimeRange)

    def __init__(self, parent=None, default_time_range: TimeRange = None):
        QWidgetAction.__init__(self, parent)
        self._widget = DateTimeRangeWidget(default_time_range=default_time_range)
        self.setDefaultWidget(self._widget)
        self._widget.range_changed.connect(self.range_changed)


def _mime_encode_time_range(time_range: TimeRange) -> QMimeData:
    mdata = QMimeData()
    mdata.setData(TIME_RANGE_MIME_TYPE, pickle.dumps(time_range))
    mdata.setText(f"{time_range.start}\t{time_range.stop}")
    return mdata


def _mime_decode_time_range(mime_data: QMimeData) -> TimeRange or None:
    if TIME_RANGE_MIME_TYPE in mime_data.formats():
        return pickle.loads(mime_data.data(TIME_RANGE_MIME_TYPE))
    return None


register_mime(obj_type=TimeRange, mime_type=TIME_RANGE_MIME_TYPE,
              encoder=_mime_encode_time_range,
              decoder=_mime_decode_time_range)
