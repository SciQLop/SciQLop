"""Panel-wide 'Autoscale this plot' / 'Autoscale all plots' / 'Equalize plot
heights' context-menu actions. See TimeSyncPanel._add_layout_actions."""
import numpy as np


def _leaf_labels(menu):
    return [a.text() for a in menu.actions() if a.menu() is None and not a.isSeparator()]


def _panel_with_plots(qtbot, n):
    from SciQLop.components.plotting.ui.time_sync_panel import (
        TimeSyncPanel, plot_static_data,
    )
    panel = TimeSyncPanel("layout-test", show_search_overlay=False)
    qtbot.addWidget(panel)
    plots = []
    for i in range(n):
        plot, _graph = plot_static_data(
            panel, np.array([0.0, 1.0, 2.0]), np.array([0.0, float(i + 1), 0.0]))
        plots.append(plot)
    return panel, plots


def test_no_layout_actions_with_no_plots(qtbot):
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    panel = TimeSyncPanel("empty-layout-test")
    qtbot.addWidget(panel)
    menu = panel._build_context_menu()
    labels = _leaf_labels(menu)
    assert "Autoscale all plots" not in labels
    assert "Equalize plot heights" not in labels


def test_autoscale_all_present_without_equalize_for_single_plot(qtbot):
    panel, plots = _panel_with_plots(qtbot, 1)
    menu = panel._build_context_menu()
    labels = _leaf_labels(menu)
    assert "Autoscale all plots" in labels
    # only one plot -> nothing to equalize
    assert "Equalize plot heights" not in labels


def test_autoscale_this_plot_only_shown_when_source_is_a_plot(qtbot):
    panel, plots = _panel_with_plots(qtbot, 2)
    _plot_a, plot_b = plots

    menu_no_source = panel._build_context_menu()
    assert "Autoscale this plot" not in _leaf_labels(menu_no_source)

    menu_on_panel = panel._build_context_menu(source=panel)
    assert "Autoscale this plot" not in _leaf_labels(menu_on_panel)

    menu_on_plot = panel._build_context_menu(source=plot_b)
    labels = _leaf_labels(menu_on_plot)
    assert "Autoscale this plot" in labels
    assert "Autoscale all plots" in labels
    assert "Equalize plot heights" in labels


def test_plot_containing_resolves_descendants(qtbot):
    from PySide6.QtWidgets import QWidget
    panel, plots = _panel_with_plots(qtbot, 2)
    plot_a, plot_b = plots

    assert panel._plot_containing(plot_a) is plot_a
    assert panel._plot_containing(panel) is None

    children = plot_b.findChildren(QWidget)
    assert children, "expected the plot to have at least one child widget"
    assert panel._plot_containing(children[0]) is plot_b


def test_autoscale_this_plot_action_targets_the_right_plot(qtbot):
    panel, plots = _panel_with_plots(qtbot, 2)
    plot_a, plot_b = plots
    calls = []
    plot_a.rescale_axes = lambda: calls.append("a")
    plot_b.rescale_axes = lambda: calls.append("b")

    menu = panel._build_context_menu(source=plot_b)
    action = next(a for a in menu.actions() if a.text() == "Autoscale this plot")
    action.trigger()

    assert calls == ["b"]


def test_autoscale_all_plots_action_hits_every_plot(qtbot):
    panel, plots = _panel_with_plots(qtbot, 3)
    calls = []
    for i, plot in enumerate(plots):
        plot.rescale_axes = (lambda i=i: calls.append(i))

    menu = panel._build_context_menu()
    action = next(a for a in menu.actions() if a.text() == "Autoscale all plots")
    action.trigger()

    assert sorted(calls) == [0, 1, 2]


def test_equalize_plot_heights_action_evens_out_sizes(qtbot):
    panel, _plots = _panel_with_plots(qtbot, 3)
    panel.resize(400, 900)
    panel.show()
    qtbot.waitExposed(panel)

    splitter = panel.widget()
    splitter.setSizes([10, 500, 10])
    assert max(splitter.sizes()) - min(splitter.sizes()) > 50

    menu = panel._build_context_menu()
    action = next(a for a in menu.actions() if a.text() == "Equalize plot heights")
    action.trigger()

    sizes = splitter.sizes()
    assert max(sizes) - min(sizes) <= 2
