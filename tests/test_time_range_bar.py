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
    assert items == ["1m", "1h", "12h", "1d", "7d", "1M"]


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


@pytest.mark.parametrize("pulse, target", [
    ("pulse", "_start_picker"), ("pulse_limit", "_zoom_limit_combo")])
def test_pulse_does_not_restyle_target_per_frame(bar, qtbot, pulse, target):
    """Restyling on every frame re-entered Python and re-polished the widget
    60 times per second (GH #143)."""
    bar.show()
    getattr(bar, pulse)()
    qtbot.wait(100)
    assert getattr(bar, target).styleSheet() == ""


# --- The duration box follows the real window (a mouse zoom rarely lands on a preset) ---

DAY = 86400.0


def test_a_zoomed_window_shows_its_real_length(bar):
    bar.set_range(TimeRange(1_000_000.0, 1_000_000.0 + 3 * DAY))
    assert bar.duration_text == "3d"
    assert bar.time_range.stop() - bar.time_range.start() == pytest.approx(3 * DAY)


def test_stepping_keeps_the_zoomed_window_length(bar, qtbot):
    start = 1_000_000.0
    bar.set_range(TimeRange(start, start + 3 * DAY))
    with qtbot.waitSignal(bar.range_changed, timeout=1000) as blocker:
        bar._forward_btn.click()
    moved = blocker.args[0]
    assert moved.start() == pytest.approx(start + 3 * DAY, abs=1)
    assert moved.stop() - moved.start() == pytest.approx(3 * DAY)


def test_a_length_that_is_not_round_steps_by_the_exact_length(bar, qtbot):
    start, length = 1_000_000.0, 9123.0
    bar.set_range(TimeRange(start, start + length))
    assert bar.duration_text == "2.53h"
    with qtbot.waitSignal(bar.range_changed, timeout=1000) as blocker:
        bar._forward_btn.click()
    assert blocker.args[0].stop() - blocker.args[0].start() == pytest.approx(length)


@pytest.mark.parametrize("typed, seconds", [("3d", 3 * DAY), ("90m", 5400.0), ("45s", 45.0)])
def test_a_typed_duration_resizes_the_window(bar, qtbot, typed, seconds):
    bar.set_range(TimeRange(1_000_000.0, 1_000_000.0 + 3600))
    bar._duration_combo.lineEdit().selectAll()
    with qtbot.waitSignal(bar.range_changed, timeout=1000):
        qtbot.keyClicks(bar._duration_combo.lineEdit(), typed)
    assert bar.time_range.stop() - bar.time_range.start() == pytest.approx(seconds)


def test_typing_does_not_jump_to_a_preset_halfway(bar, qtbot):
    """ "12h" starts like "1m" and "1h": no completion may apply those on the way."""
    bar.set_range(TimeRange(1_000_000.0, 1_000_000.0 + 3 * DAY))
    lengths = []
    bar.range_changed.connect(lambda tr: lengths.append(tr.stop() - tr.start()))
    bar._duration_combo.lineEdit().selectAll()
    qtbot.keyClicks(bar._duration_combo.lineEdit(), "12h")
    assert lengths == [43200.0]


def test_text_that_is_not_a_duration_is_put_back(bar, qtbot):
    bar.set_range(TimeRange(1_000_000.0, 1_000_000.0 + 3 * DAY))
    signals = []
    bar.range_changed.connect(signals.append)
    bar._duration_combo.lineEdit().selectAll()
    qtbot.keyClicks(bar._duration_combo.lineEdit(), "soon")
    qtbot.keyClick(bar._duration_combo.lineEdit(), Qt.Key.Key_Return)
    assert bar.duration_text == "3d" and signals == []


# --- The start box applies a typed date once, when editing ends ---

def test_typing_a_start_date_moves_the_window_once(bar, qtbot):
    """Each digit used to move the window, so one date cost several downloads."""
    bar.set_range(TimeRange(1_000_000.0, 1_000_000.0 + 3600))
    moves = []
    bar.range_changed.connect(moves.append)
    bar.show()
    qtbot.waitExposed(bar)
    picker = bar._start_picker
    picker.setFocus()
    picker.setSelectedSection(picker.Section.YearSection)
    qtbot.keyClicks(picker, "2019")
    assert moves == []
    qtbot.keyClick(picker, Qt.Key.Key_Return)
    assert len(moves) == 1
    assert datetime.fromtimestamp(moves[0].start(), timezone.utc).year == 2019


def test_the_start_arrows_still_apply_at_once(bar, qtbot):
    bar.set_range(TimeRange(1_000_000.0, 1_000_000.0 + 3600))
    with qtbot.waitSignal(bar.range_changed, timeout=1000):
        bar._start_picker.stepBy(1)


def test_the_start_box_says_utc(bar):
    assert bar._start_picker.text().endswith("UTC")


def test_the_new_panel_pulse_is_not_error_red(bar):
    assert "palette(highlight)" in bar._start_pulse.styleSheet()
