"""Panel-wide 'Autoscale this plot' / 'Autoscale all plots' / 'Equalize plot
heights' context-menu actions, grouped under one 'Autoscale & Layout'
submenu to keep the top level light. See TimeSyncPanel._add_layout_actions."""
import numpy as np

SUBMENU_TITLE = "Autoscale & Layout"


def _submenu(menu, title):
    for a in menu.actions():
        sub = a.menu()
        if sub is not None and a.text().replace("&&", "&") == title:
            return sub
    return None


def _submenu_titles(menu):
    return [a.text().replace("&&", "&") for a in menu.actions() if a.menu() is not None]


def _leaf_labels(menu):
    return [a.text().split("\t", 1)[0] for a in menu.actions()
            if a.menu() is None and not a.isSeparator()]


def _find_action(menu, text):
    for a in menu.actions():
        if a.text().split("\t", 1)[0] == text:
            return a
    return None


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


def test_no_layout_submenu_with_no_plots(qtbot):
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    panel = TimeSyncPanel("empty-layout-test")
    qtbot.addWidget(panel)
    menu = panel._build_context_menu()
    assert SUBMENU_TITLE not in _submenu_titles(menu)


def test_layout_actions_grouped_under_one_submenu(qtbot):
    panel, _plots = _panel_with_plots(qtbot, 2)
    menu = panel._build_context_menu()
    assert SUBMENU_TITLE in _submenu_titles(menu)
    # nothing loose at the top level besides Crosshair/Catalogs/Export/Templates
    assert _leaf_labels(menu) == []


def test_single_plot_shows_autoscale_all_without_equalize(qtbot):
    panel, _plots = _panel_with_plots(qtbot, 1)
    menu = panel._build_context_menu()
    sub = _submenu(menu, SUBMENU_TITLE)
    assert sub is not None
    labels = _leaf_labels(sub)
    assert "Autoscale all plots" in labels
    # only one plot -> nothing to equalize
    assert "Equalize plot heights" not in labels


def test_autoscale_this_plot_only_shown_when_source_is_a_plot(qtbot):
    panel, plots = _panel_with_plots(qtbot, 2)
    _plot_a, plot_b = plots

    menu_no_source = panel._build_context_menu()
    assert "Autoscale this plot" not in _leaf_labels(_submenu(menu_no_source, SUBMENU_TITLE))

    menu_on_panel = panel._build_context_menu(source=panel)
    assert "Autoscale this plot" not in _leaf_labels(_submenu(menu_on_panel, SUBMENU_TITLE))

    menu_on_plot = panel._build_context_menu(source=plot_b)
    labels = _leaf_labels(_submenu(menu_on_plot, SUBMENU_TITLE))
    assert "Autoscale this plot" in labels
    assert "Autoscale all plots" in labels
    assert "Equalize plot heights" in labels


def test_autoscale_all_and_equalize_show_shortcut_hints(qtbot):
    panel, _plots = _panel_with_plots(qtbot, 2)
    menu = panel._build_context_menu()
    sub = _submenu(menu, SUBMENU_TITLE)
    autoscale_all = _find_action(sub, "Autoscale all plots")
    equalize = _find_action(sub, "Equalize plot heights")
    assert "\t" in autoscale_all.text()
    assert "\t" in equalize.text()
    # "Autoscale this plot" has no fixed keyboard shortcut (it depends on
    # where the cursor was) so it shouldn't claim to have one.
    this_plot = _find_action(_submenu(panel._build_context_menu(source=panel.plots()[0]),
                                       SUBMENU_TITLE), "Autoscale this plot")
    assert "\t" not in this_plot.text()


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
    action = _find_action(_submenu(menu, SUBMENU_TITLE), "Autoscale this plot")
    action.trigger()

    assert calls == ["b"]


def test_autoscale_all_plots_action_hits_every_plot(qtbot):
    panel, plots = _panel_with_plots(qtbot, 3)
    calls = []
    for i, plot in enumerate(plots):
        plot.rescale_axes = (lambda i=i: calls.append(i))

    menu = panel._build_context_menu()
    action = _find_action(_submenu(menu, SUBMENU_TITLE), "Autoscale all plots")
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
    action = _find_action(_submenu(menu, SUBMENU_TITLE), "Equalize plot heights")
    action.trigger()

    sizes = splitter.sizes()
    assert max(sizes) - min(sizes) <= 2
