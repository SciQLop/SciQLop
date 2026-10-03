"""Tests for the user_api interval timeline (panel.add_timeline / plot.add_timeline)."""
from datetime import datetime, timezone

import numpy as np
import pytest

from .fixtures import *  # qapp_cls, sciqlop_resources, main_window, plot_panel

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()


@pytest.fixture
def timeline(plot_panel):
    _plot, tl = plot_panel.add_timeline(lane_height=10)
    tl.set_intervals([T0, T0 + 600, T0 + 1200], [T0 + 300, T0 + 900, T0 + 1200],
                     lane=["MSA", "MGF", "MSA"], category=["LM", "survey", "LM"],
                     label=["low mass", "survey", "instant"], ids=["on-3", "on-7", "on-9"])
    return tl


def test_panel_add_timeline_returns_a_time_series_plot_and_timeline(plot_panel):
    from SciQLop.user_api.plot import TimeSeriesPlot, Timeline
    plot, tl = plot_panel.add_timeline()
    assert isinstance(plot, TimeSeriesPlot)
    assert isinstance(tl, Timeline)


def test_strip_over_an_existing_time_series_plot(plot_panel):
    from SciQLop.user_api.plot import Timeline
    plot, _ = plot_panel.plot_data(np.array([T0, T0 + 3600.0]), np.array([0.0, 1.0]), labels=["x"])
    assert isinstance(plot.add_timeline(lane_height=8), Timeline)


@pytest.mark.parametrize("starts", [
    [T0, T0 + 60],
    np.array(["2026-01-01T00:00:00", "2026-01-01T00:01:00"], dtype="datetime64[s]"),
    [datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc)],
    ["2026-01-01T00:00", "2026-01-01T00:01"],
])
def test_times_accept_epoch_datetime64_and_datetime(plot_panel, starts):
    _plot, tl = plot_panel.add_timeline()
    tl.set_intervals(starts, lane=["A", "A"], ids=[1, 2])
    assert tl.interval(2).start == pytest.approx(T0 + 60)
    assert tl.interval(2).duration == 0.0


def test_lanes_keep_first_seen_order_and_can_be_reordered(timeline):
    assert timeline.lanes == ["MSA", "MGF"]
    timeline.lanes = ["MGF", "MSA"]
    assert timeline.lanes == ["MGF", "MSA"]


def test_lane_order_survives_new_intervals(timeline):
    timeline.lanes = ["MGF", "MSA"]
    timeline.set_intervals([T0, T0 + 600], [T0 + 300, T0 + 900], lane=["MSA", "MGF"])
    assert timeline.lanes == ["MGF", "MSA"]


def test_ids_can_be_any_hashable(timeline):
    timeline.select_ids(["on-7"])
    assert timeline.selected_ids == ["on-7"]


def test_duplicate_ids_are_rejected(plot_panel):
    _plot, tl = plot_panel.add_timeline()
    with pytest.raises(ValueError, match="unique"):
        tl.set_intervals([T0, T0 + 1], lane=["A", "A"], ids=["x", "x"])


def test_interval_lookup(timeline):
    iv = timeline.interval("on-7")
    assert (iv.id, iv.lane, iv.category, iv.label) == ("on-7", "MGF", "survey", "survey")
    assert (iv.start, iv.stop, iv.duration) == (T0 + 600, T0 + 900, 300)


def test_on_edit_reports_one_batch_with_user_ids(timeline, qtbot):
    edits = []
    timeline.on_edit(edits.append)
    timeline._impl.intervals_changed.emit([[0, T0 + 60, T0 + 360, "MSA"], [2, T0 + 1260, T0 + 1260, "MSA"]])
    assert len(edits) == 1
    assert [(e.id, e.start, e.stop, e.lane) for e in edits[0]] == [
        ("on-3", T0 + 60, T0 + 360, "MSA"), ("on-9", T0 + 1260, T0 + 1260, "MSA")]


def test_edits_are_proposals(timeline, qtbot):
    timeline.on_edit(lambda edits: None)
    timeline._impl.intervals_changed.emit([[0, T0 + 60, T0 + 360, "MSA"]])
    assert timeline.interval("on-3").start == T0


def test_on_hover_gives_the_interval_or_none(timeline, qtbot):
    hovered = []
    timeline.on_hover(hovered.append)
    timeline._impl.hovered.emit(1)
    timeline._impl.hovered.emit(-1)
    assert hovered[0].id == "on-7" and hovered[0].duration == 300
    assert hovered[1] is None


def test_on_selection_create_and_delete(timeline, qtbot):
    selected, created, deleted = [], [], []
    timeline.on_selection(selected.append)
    timeline.on_create(lambda start, stop, lane: created.append((start, stop, lane)))
    timeline.on_delete(deleted.append)
    timeline._impl.selected_intervals_changed.emit([0, 2])
    timeline._impl.interval_created.emit(T0 + 5, T0 + 50, "MGF")
    timeline._impl.delete_requested.emit([1])
    assert selected == [["on-3", "on-9"]]
    assert created == [(T0 + 5, T0 + 50, "MGF")]
    assert deleted == [["on-7"]]


def test_editing_options(timeline):
    timeline.editable = True
    timeline.edit_modes = {"move", "resize"}
    timeline.snap_to = 60
    assert timeline.editable and timeline.edit_modes == {"move", "resize"} and timeline.snap_to == 60


def test_category_colours_accept_css_names(timeline):
    timeline.set_category_colors({"LM": "#f59e0b"})
    assert timeline.category_color("LM") == "#f59e0b"


def test_legend_can_be_hidden(plot_panel):
    plot, _ = plot_panel.add_timeline()
    plot.legend_visible = False
    assert plot.legend_visible is False
