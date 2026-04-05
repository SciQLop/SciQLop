import pytest
from datetime import datetime, timezone
from PySide6.QtCore import QDateTime, Qt

from SciQLop.core import TimeRange


@pytest.fixture
def bar(qtbot):
    from SciQLop.components.plotting.ui.time_range_bar import TimeRangeBar
    w = TimeRangeBar()
    qtbot.addWidget(w)
    return w



def test_initial_state(bar):
    """Bar should have a valid range on construction."""
    tr = bar.time_range
    assert tr.stop() - tr.start() > 0


def test_duration_presets_available(bar):
    """All expected durations should be in the combo box."""
    items = [bar._duration_combo.itemText(i) for i in range(bar._duration_combo.count())]
    assert items == ["1m", "1h", "12h", "1d", "7d"]


def test_set_range_updates_widgets(bar):
    """set_range should update the start picker and keep closest duration."""
    start = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc).timestamp()
    bar.set_range(TimeRange(start, start + 3600))
    assert abs(bar.time_range.start() - start) < 1
    assert abs(bar.time_range.stop() - bar.time_range.start() - 3600) < 1


def test_set_range_selects_closest_duration(bar):
    """set_range with exact duration match should select that preset."""
    start = 1_000_000.0
    bar.set_range(TimeRange(start, start + 86400))
    assert bar._duration_combo.currentText() == "1d"


def test_step_forward(bar, qtbot):
    """Clicking forward should shift start by one duration."""
    start = 1_000_000.0
    bar.set_range(TimeRange(start, start + 3600))
    with qtbot.waitSignal(bar.range_changed, timeout=1000):
        bar._forward_btn.click()
    assert abs(bar.time_range.start() - (start + 3600)) < 1


def test_step_backward(bar, qtbot):
    """Clicking backward should shift start by minus one duration."""
    start = 1_000_000.0
    bar.set_range(TimeRange(start, start + 3600))
    with qtbot.waitSignal(bar.range_changed, timeout=1000):
        bar._backward_btn.click()
    assert abs(bar.time_range.start() - (start - 3600)) < 1


def test_fast_forward(bar, qtbot):
    """Fast forward shifts by 5 durations."""
    start = 1_000_000.0
    bar.set_range(TimeRange(start, start + 3600))
    with qtbot.waitSignal(bar.range_changed, timeout=1000):
        bar._fast_forward_btn.click()
    assert abs(bar.time_range.start() - (start + 5 * 3600)) < 1


def test_fast_backward(bar, qtbot):
    """Fast backward shifts by -5 durations."""
    start = 1_000_000.0
    bar.set_range(TimeRange(start, start + 3600))
    with qtbot.waitSignal(bar.range_changed, timeout=1000):
        bar._fast_backward_btn.click()
    assert abs(bar.time_range.start() - (start - 5 * 3600)) < 1


def test_changing_duration_updates_range(bar, qtbot):
    """Changing duration combo should emit range_changed with new stop."""
    start = 1_000_000.0
    bar.set_range(TimeRange(start, start + 3600))
    with qtbot.waitSignal(bar.range_changed, timeout=1000):
        bar._duration_combo.setCurrentText("1d")
    assert abs(bar.time_range.stop() - bar.time_range.start() - 86400) < 1


def test_no_signal_during_set_range(bar, qtbot):
    """set_range should not emit range_changed (avoids feedback loops)."""
    signals = []
    bar.range_changed.connect(lambda tr: signals.append(tr))
    bar.set_range(TimeRange(1_000_000.0, 1_000_000.0 + 3600))
    assert len(signals) == 0


def test_catalog_combo_hidden_by_default(bar):
    assert bar._catalog_combo.isHidden() is True


def test_set_catalog_choices_shows_combo(bar):
    bar.set_catalog_choices([("MyCatalog", "uuid-1")])
    assert bar._catalog_combo.isHidden() is False
    assert bar._catalog_combo.count() == 1
    assert bar._catalog_combo.currentText() == "MyCatalog"


def test_set_catalog_choices_auto_selects_first(bar):
    bar.set_catalog_choices([("Cat-A", "uuid-a"), ("Cat-B", "uuid-b")])
    assert bar.selected_catalog_uuid() == "uuid-a"


def test_selected_catalog_uuid_returns_item_data(bar):
    bar.set_catalog_choices([("Cat-A", "uuid-a"), ("Cat-B", "uuid-b")])
    bar._catalog_combo.setCurrentIndex(1)
    assert bar.selected_catalog_uuid() == "uuid-b"


def test_selected_catalog_uuid_none_when_empty(bar):
    assert bar.selected_catalog_uuid() is None


def test_clear_catalog_choices_hides_combo(bar):
    bar.set_catalog_choices([("MyCatalog", "uuid-1")])
    bar.clear_catalog_choices()
    assert bar._catalog_combo.isHidden() is True
    assert bar._catalog_combo.count() == 0
    assert bar.selected_catalog_uuid() is None


def test_catalog_choice_changed_signal(bar, qtbot):
    bar.set_catalog_choices([("Cat-A", "uuid-a"), ("Cat-B", "uuid-b")])
    with qtbot.waitSignal(bar.catalog_choice_changed, timeout=1000) as blocker:
        bar._catalog_combo.setCurrentIndex(1)
    assert blocker.args == ["uuid-b"]


# --- Zoom limit combo tests ---

ZOOM_LIMIT_PRESETS = [("1h", 3600), ("1d", 86400), ("1w", 604800), ("1y", 365.25 * 86400), ("Unlimited", 0)]


def test_zoom_limit_combo_presets(bar):
    items = [bar._zoom_limit_combo.itemText(i) for i in range(bar._zoom_limit_combo.count())]
    assert items == [label for label, _ in ZOOM_LIMIT_PRESETS]


def test_zoom_limit_default_is_one_day(bar):
    assert bar._zoom_limit_combo.currentText() == "1d"
    assert bar.max_range_seconds == 86400


def test_zoom_limit_changed_signal(bar, qtbot):
    with qtbot.waitSignal(bar.limit_changed, timeout=1000) as blocker:
        bar._zoom_limit_combo.setCurrentText("1w")
    assert blocker.args == [604800.0]


def test_zoom_limit_unlimited_emits_zero(bar, qtbot):
    with qtbot.waitSignal(bar.limit_changed, timeout=1000) as blocker:
        bar._zoom_limit_combo.setCurrentText("Unlimited")
    assert blocker.args == [0.0]


def test_set_max_range_seconds_updates_combo(bar):
    bar.max_range_seconds = 604800
    assert bar._zoom_limit_combo.currentText() == "1w"


def test_set_max_range_seconds_zero_selects_unlimited(bar):
    bar.max_range_seconds = 0
    assert bar._zoom_limit_combo.currentText() == "Unlimited"


def test_pulse_limit_runs_without_error(bar):
    bar.pulse_limit()
