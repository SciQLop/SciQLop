"""SciQLop#146: step line shapes, line-graph gap detection and text tick labels in user_api.

Timeline-like plots (on/off lanes, instrument modes) need exact steps, no line
breaks at long flat stretches, and names instead of numbers on the y axis.
"""
import numpy as np
import pytest
import SciQLopPlots as _sqp

from SciQLop.user_api.plot import LineShape

from .fixtures import *  # noqa: F401, F403

X = np.array([0.0, 10.0, 10.0, 500.0, 500.0, 510.0])
Y = np.array([0.0, 0.0, 1.0, 1.0, 0.0, 0.0])


def _shapes(graph):
    return {c.line_style() for c in graph._get_impl_or_raise().components()}


def test_plot_data_takes_a_line_shape(plot_panel):
    _, graph = plot_panel.plot_data(X, Y, line_shape=LineShape.StepLeft)
    assert _shapes(graph) == {_sqp.GraphLineStyle.StepLeft}
    assert graph.line_shape is LineShape.StepLeft


def test_a_graph_line_shape_can_be_changed(plot_panel):
    _, graph = plot_panel.plot_data(X, Y)
    graph.line_shape = LineShape.StepRight
    assert _shapes(graph) == {_sqp.GraphLineStyle.StepRight}


def test_line_shape_rejects_a_line_style(plot_panel):
    from SciQLop.user_api.plot.enums import GraphLineStyle
    with pytest.raises(TypeError, match="LineShape"):
        plot_panel.plot_data(X, Y, line_shape=GraphLineStyle.Dash)


def test_gap_detection_can_be_turned_off(plot_panel):
    _, graph = plot_panel.plot_data(X, Y, gap_threshold=0)
    assert graph._get_impl_or_raise().gap_threshold() == 0
    assert graph.gap_threshold == 0
    graph.gap_threshold = 3.0
    assert graph._get_impl_or_raise().gap_threshold() == 3.0


def test_gap_threshold_rejects_a_negative_value(plot_panel):
    with pytest.raises(ValueError, match="gap_threshold"):
        plot_panel.plot_data(X, Y, gap_threshold=-1)


def test_gap_threshold_only_applies_to_line_graphs(plot_panel):
    from SciQLop.user_api.plot import PlotType
    xy_plot, _ = plot_panel.plot_data(X, Y, plot_type=PlotType.XY)
    with pytest.raises(ValueError, match="line graphs"):
        xy_plot.plot(X, Y, gap_threshold=0)


def test_a_plot_takes_line_shape_and_gap_threshold_too(plot_panel):
    plot, _ = plot_panel.plot_data(X, Y)
    graph = plot.plot(X, Y + 2, line_shape=LineShape.StepCenter, gap_threshold=0)
    assert graph.line_shape is LineShape.StepCenter
    assert graph.gap_threshold == 0


def test_axis_tick_labels_replace_numbers(plot_panel):
    plot, _ = plot_panel.plot_data(X, Y)
    plot.set_axis_tick_labels("y", {0: "MAG", -1: "SWA"})
    assert plot._resolve_axis("y").tick_labels() == {0.0: "MAG", -1.0: "SWA"}
    plot.set_axis_tick_labels("y", None)
    assert plot._resolve_axis("y").tick_labels() == {}


def test_axis_tick_labels_reject_non_numeric_positions(plot_panel):
    plot, _ = plot_panel.plot_data(X, Y)
    with pytest.raises(ValueError, match="tick"):
        plot.set_axis_tick_labels("y", {"top": "MAG"})
