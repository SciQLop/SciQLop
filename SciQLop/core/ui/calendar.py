from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCharFormat
from PySide6.QtWidgets import QCalendarWidget


def plain_calendar(calendar: QCalendarWidget) -> QCalendarWidget:
    """Drop what Qt adds by default and no theme can restyle: red weekends, week numbers, a grid."""
    calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
    calendar.setGridVisible(False)
    for day in (Qt.DayOfWeek.Saturday, Qt.DayOfWeek.Sunday):
        calendar.setWeekdayTextFormat(day, QTextCharFormat())
    return calendar
