"""Everything the Properties panel edits can be changed from user_api too, so
notebooks and agents are not stuck where a user clicking around is not."""
import numpy as np
import pytest
from PySide6.QtGui import QColor, QFont

from SciQLop.user_api.plot import GraphLineStyle, MarkerShape, HistogramNormalization, PlotType

from .fixtures import *  # noqa: F401, F403

X = np.linspace(0.0, 10.0, 50)


def _two_line_graph(plot_panel):
    return plot_panel.plot_data(X, np.column_stack([np.sin(X), np.cos(X)]), labels=["sin", "cos"])


def _components(graph):
    return graph._get_impl_or_raise().components()


def test_each_line_of_a_graph_is_editable(plot_panel):
    _, graph = _two_line_graph(plot_panel)
    first, second = graph.lines
    first.color = "red"
    first.line_width = 3
    first.line_style = GraphLineStyle.Dash
    first.marker = MarkerShape.Circle
    first.marker_size = 9
    first.marker_color = "blue"
    second.visible = False
    a, b = _components(graph)
    assert a.color() == QColor("red") and a.line_width() == 3
    assert (first.line_style, first.marker, first.marker_size) == (GraphLineStyle.Dash, MarkerShape.Circle, 9)
    assert a.marker_pen().color() == QColor("blue")
    assert (a.visible(), b.visible()) == (True, False)
    assert b.line_width() != 3


def test_a_graph_sets_all_its_lines_and_reads_none_when_they_differ(plot_panel):
    _, graph = _two_line_graph(plot_panel)
    graph.line_width = 4
    assert [c.line_width() for c in _components(graph)] == [4, 4] and graph.line_width == 4
    graph.lines[0].line_width = 1
    assert graph.line_width is None


@pytest.mark.parametrize("plot_type", [PlotType.TimeSeries, PlotType.XY])
def test_an_unlabelled_graph_has_its_lines_as_soon_as_it_is_plotted(plot_panel, plot_type):
    """Unlabelled graphs got their lines when the resampled data came back, so
    styling right after plotting (or line_style=) silently did nothing."""
    _, graph = plot_panel.plot_data(X, np.column_stack([np.sin(X), np.cos(X)]), plot_type=plot_type,
                                    line_style=GraphLineStyle.Dash)
    assert len(graph.lines) == 2
    assert graph.line_style is GraphLineStyle.Dash


def test_line_properties_reject_wrong_types(plot_panel):
    _, graph = _two_line_graph(plot_panel)
    with pytest.raises(TypeError, match="MarkerShape"):
        graph.marker = "circle"
    with pytest.raises(TypeError, match="GraphLineStyle"):
        graph.line_style = 1
    with pytest.raises(ValueError, match="colour"):
        graph.color = "not-a-colour"


def test_plot_properties(plot_panel):
    plot, _ = _two_line_graph(plot_panel)
    plot.name = "overview"
    plot.crosshair = True
    plot.equal_aspect_ratio = True
    plot.scroll_factor = 2.5
    plot.auto_scale = True
    plot.legend_color = "green"
    plot.legend_font = QFont("Monospace", 14)
    impl = plot._get_impl_or_raise()
    assert impl.objectName() == "overview" and plot.name == "overview"
    assert impl.crosshair_enabled() and impl.equal_aspect_ratio() and impl.auto_scale()
    assert impl.scroll_factor() == 2.5
    assert impl.legend().color() == QColor("green") and impl.legend().font().pointSize() == 14


def test_axis_properties(plot_panel):
    plot, _ = _two_line_graph(plot_panel)
    y = plot.axis("y")
    y.label = "B"
    y.label_color = "red"
    y.label_font = QFont("Monospace", 13)
    y.tick_labels_visible = False
    y.tick_label_color = "blue"
    y.tick_label_font = QFont("Monospace", 7)
    y.autoscale_margin = 0.1
    y.autoscale_percentile = (2.0, 98.0)
    impl = plot._get_impl_or_raise().y_axis()
    assert impl.label() == "B" and impl.label_color() == QColor("red")
    assert impl.label_font().pointSize() == 13 and impl.tick_label_font().pointSize() == 7
    assert not impl.tick_labels_visible() and impl.tick_label_color() == QColor("blue")
    assert impl.autoscale_margin() == pytest.approx(0.1)
    assert y.autoscale_percentile == (2.0, 98.0)


def test_an_unknown_axis_is_refused(plot_panel):
    plot, _ = _two_line_graph(plot_panel)
    with pytest.raises(ValueError, match="axis 'w'"):
        plot.axis("w")


def test_colormap_properties(plot_panel):
    y = np.logspace(1, 3, 16)
    plot, cmap = plot_panel.plot_data(X, y, np.random.rand(len(X), len(y)), plot_type=PlotType.XY)
    cmap.gradient = "Jet"
    cmap.z_log_scale = True
    cmap.auto_scale_y = True
    cmap.contour_levels = 5
    cmap.contour_color = "white"
    cmap.autoscale_percentile = (1.0, 99.0)
    impl = cmap._get_impl_or_raise()
    assert cmap.gradient.name == "Jet" and impl.z_log_scale() and impl.auto_scale_y()
    assert impl.auto_contour_level_count() == 5 and impl.contour_color() == QColor("white")
    assert cmap.autoscale_percentile == (1.0, 99.0)


def test_histogram2d_properties(plot_panel):
    plot, _ = _two_line_graph(plot_panel)
    hist = plot.histogram2d(np.random.rand(500), np.random.rand(500))
    hist.bins = (20, 30)
    hist.x_bins_log = True
    hist.y_bins_log = True
    hist.normalization = HistogramNormalization.PerColumn
    hist.autoscale_percentile = (5.0, 95.0)
    impl = hist._get_impl_or_raise()
    assert (impl.x_bins(), impl.y_bins()) == (20, 30) and hist.bins == (20, 30)
    assert impl.x_bins_log() and impl.y_bins_log()
    assert impl.normalization() == 1 and hist.normalization is HistogramNormalization.PerColumn
    assert hist.autoscale_percentile == (5.0, 95.0)


def test_a_panel_can_be_renamed(plot_panel):
    plot_panel.name = "renamed panel"
    assert plot_panel._get_impl_or_raise().objectName() == "renamed panel"
    assert plot_panel.name == "renamed panel"
