"""Time-range presets are contributions to sciqlop.time_presets (Tier 3 spec §4.2)."""
import pytest

from SciQLop.core.extensions import owned_by
from SciQLop.core.time_presets import TIME_PRESETS, TimePreset, duration_presets, parse_duration, preset_seconds


@pytest.fixture
def three_days(qapp):
    with owned_by("tp_demo"):
        TIME_PRESETS.contribute(TimePreset("3d", "3d", 3 * 86400))
    yield
    TIME_PRESETS.remove_owner("tp_demo")


@pytest.fixture
def bar(qtbot):
    from SciQLop.components.plotting.ui.time_range_bar import TimeRangeBar
    w = TimeRangeBar()
    qtbot.addWidget(w)
    return w


def _items(bar):
    return [bar._duration_combo.itemText(i) for i in range(bar._duration_combo.count())]


def test_the_core_presets_merge_the_bar_and_the_palette():
    assert [p.id for p in duration_presets()] == ["1m", "1h", "12h", "1d", "7d", "1M"]
    assert preset_seconds("7d") == 604800
    assert preset_seconds("no such preset") == 86400


def test_a_plugin_preset_shows_in_an_open_bar_sorted_by_length(bar, three_days):
    assert _items(bar) == ["1m", "1h", "12h", "1d", "3d", "7d", "1M"]


def test_an_open_bar_keeps_its_selection_when_presets_change(bar, qtbot):
    bar.duration_text = "1d"
    try:
        with qtbot.assertNotEmitted(bar.range_changed):
            with owned_by("tp_demo"):
                TIME_PRESETS.contribute(TimePreset("3d", "3d", 3 * 86400))
            TIME_PRESETS.remove_owner("tp_demo")
    finally:
        TIME_PRESETS.remove_owner("tp_demo")
    assert bar.duration_text == "1d"
    assert "3d" not in _items(bar)


def test_a_deleted_bar_ignores_later_preset_changes(qtbot, qapp):
    from SciQLop.components.plotting.ui.time_range_bar import TimeRangeBar
    w = TimeRangeBar()
    w.deleteLater()
    qapp.sendPostedEvents(None, 16)
    with owned_by("tp_demo"):
        TIME_PRESETS.contribute(TimePreset("3d", "3d", 3 * 86400))
    TIME_PRESETS.remove_owner("tp_demo")


def test_panel_duration_7d_still_selects_a_week(bar):
    bar.duration_text = "7d"
    assert bar.time_range.stop() - bar.time_range.start() == pytest.approx(604800)


def test_the_palette_offers_every_preset(three_days):
    from SciQLop.components.command_palette.arg_types import TimeRangeArg
    completions = TimeRangeArg().completions({})
    assert [c.value for c in completions] == ["1m", "1h", "12h", "1d", "3d", "7d", "1M"]
    assert "Last hour" in [c.display for c in completions]
    assert "Last 3d" in [c.display for c in completions]


@pytest.mark.parametrize("text, seconds", [
    ("1w", 604800), ("2d", 2 * 86400), ("90m", 5400), ("1.5h", 5400), (" 3 d ", 3 * 86400),
    ("1M", 30 * 86400), ("1y", 365.25 * 86400), ("7d", 604800), ("12h", 43200)])
def test_a_typed_duration_is_read_as_a_number_and_a_unit(text, seconds):
    assert parse_duration(text) == pytest.approx(seconds)


@pytest.mark.parametrize("text", ["", "week", "1x", "-1d", "0h", "d1", "1 w w"])
def test_text_that_is_not_a_duration_is_refused(text):
    assert parse_duration(text) is None


def test_a_plugin_preset_is_read_by_its_id_and_label(three_days):
    assert parse_duration("3d") == 3 * 86400


class _Window:
    def __init__(self):
        from PySide6.QtWidgets import QStatusBar
        self._default_time_range = None
        self._bar = QStatusBar()

    def statusBar(self):
        return self._bar


@pytest.fixture
def window(qapp, monkeypatch):
    from SciQLop.components.command_palette import commands
    w = _Window()
    monkeypatch.setattr(commands, "_get_win", lambda: w)
    return w


def test_set_time_range_from_the_palette_takes_a_week(window):
    from SciQLop.components.command_palette.commands import _do_set_time_range
    _do_set_time_range("1w")
    tr = window._default_time_range
    assert tr.stop() - tr.start() == pytest.approx(604800)


def test_set_time_range_refuses_unreadable_text_and_keeps_the_range(window):
    from SciQLop.components.command_palette.commands import _do_set_time_range
    _do_set_time_range("sometime")
    assert window._default_time_range is None
    assert "sometime" in window.statusBar().currentMessage()
