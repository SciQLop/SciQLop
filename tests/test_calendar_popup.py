"""The calendar of a date field follows the theme: no red weekends, no week numbers, no grid."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCalendarWidget

from .fixtures import *  # noqa: F401,F403


def _weekend_colours(calendar) -> set:
    return {calendar.weekdayTextFormat(day).foreground().style()
            for day in (Qt.DayOfWeek.Saturday, Qt.DayOfWeek.Sunday)}


def test_a_plain_calendar_has_no_coloured_weekend_week_numbers_or_grid(qapp, qtbot):
    from SciQLop.core.ui.calendar import plain_calendar
    calendar = QCalendarWidget()
    qtbot.addWidget(calendar)
    assert _weekend_colours(calendar) != {Qt.BrushStyle.NoBrush}

    plain_calendar(calendar)

    assert _weekend_colours(calendar) == {Qt.BrushStyle.NoBrush}
    assert calendar.verticalHeaderFormat() == QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader
    assert not calendar.isGridVisible()


def test_the_time_bar_and_the_catalog_date_editor_use_it(qapp, qtbot):
    from SciQLop.components.catalogs.ui.event_table_delegate import _utc_datetime_edit
    from SciQLop.components.plotting.ui.time_range_bar import _make_start_picker
    for make in (_make_start_picker, _utc_datetime_edit):
        edit = make(None)
        qtbot.addWidget(edit)
        assert _weekend_colours(edit.calendarWidget()) == {Qt.BrushStyle.NoBrush}
