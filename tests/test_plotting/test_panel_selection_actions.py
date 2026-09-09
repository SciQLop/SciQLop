"""'Toggle log scale' (selected axis) / 'Hide'/'Show' (selected graph)
context-menu actions, grouped under one 'Selection' submenu that only
appears when something is actually selected in the right-clicked plot.
Mirrors SciQLopPlots' existing per-plot L/H QShortcuts
(SciQLopPlotInterface.hpp). See TimeSyncPanel._add_selection_actions."""
import numpy as np

from tests.test_plotting._menu_test_helpers import (
    submenu, submenu_titles, leaf_labels, find_action, mnemonic_letter,
)

SUBMENU_TITLE = "Selection"


def _panel_with_plot(qtbot):
    from SciQLop.components.plotting.ui.time_sync_panel import (
        TimeSyncPanel, plot_static_data,
    )
    panel = TimeSyncPanel("selection-test", show_search_overlay=False)
    qtbot.addWidget(panel)
    plot, graph = plot_static_data(
        panel, np.array([0.0, 1.0, 2.0]), np.array([0.0, 1.0, 0.0]))
    return panel, plot, graph


def test_no_selection_submenu_without_source(qtbot):
    panel, _plot, _graph = _panel_with_plot(qtbot)
    menu = panel._build_context_menu()
    assert SUBMENU_TITLE not in submenu_titles(menu)


def test_no_selection_submenu_when_nothing_selected(qtbot):
    panel, plot, _graph = _panel_with_plot(qtbot)
    menu = panel._build_context_menu(source=plot)
    assert SUBMENU_TITLE not in submenu_titles(menu)


def test_log_toggle_shown_when_an_axis_is_selected(qtbot):
    panel, plot, _graph = _panel_with_plot(qtbot)
    plot.y_axis().set_selected(True)
    menu = panel._build_context_menu(source=plot)
    sub = submenu(menu, SUBMENU_TITLE)
    assert sub is not None
    assert "Toggle log scale" in leaf_labels(sub)
    assert "Hide" not in leaf_labels(sub) and "Show" not in leaf_labels(sub)


def test_log_toggle_is_checkable_and_reflects_state(qtbot):
    panel, plot, _graph = _panel_with_plot(qtbot)
    axis = plot.y_axis()
    axis.set_selected(True)
    menu = panel._build_context_menu(source=plot)
    action = find_action(submenu(menu, SUBMENU_TITLE), "Toggle log scale")
    assert action.isCheckable()
    assert action.isChecked() == axis.log()


def test_log_toggle_action_flips_axis_log_scale(qtbot):
    panel, plot, _graph = _panel_with_plot(qtbot)
    axis = plot.y_axis()
    axis.set_selected(True)
    assert axis.log() is False

    menu = panel._build_context_menu(source=plot)
    action = find_action(submenu(menu, SUBMENU_TITLE), "Toggle log scale")
    action.trigger()
    assert axis.log() is True

    menu2 = panel._build_context_menu(source=plot)
    action2 = find_action(submenu(menu2, SUBMENU_TITLE), "Toggle log scale")
    action2.trigger()
    assert axis.log() is False


def test_hide_show_shown_when_a_graph_is_selected(qtbot):
    panel, plot, graph = _panel_with_plot(qtbot)
    graph.components()[0].set_selected(True)
    menu = panel._build_context_menu(source=plot)
    sub = submenu(menu, SUBMENU_TITLE)
    assert sub is not None
    assert "Hide" in leaf_labels(sub)
    assert "Toggle log scale" not in leaf_labels(sub)


def test_hide_show_toggles_visibility_and_relabels(qtbot):
    panel, plot, graph = _panel_with_plot(qtbot)
    graph.components()[0].set_selected(True)
    assert graph.visible() is True

    menu = panel._build_context_menu(source=plot)
    action = find_action(submenu(menu, SUBMENU_TITLE), "Hide")
    action.trigger()
    assert graph.visible() is False

    menu2 = panel._build_context_menu(source=plot)
    assert find_action(submenu(menu2, SUBMENU_TITLE), "Show") is not None
    assert find_action(submenu(menu2, SUBMENU_TITLE), "Hide") is None


def test_hide_show_forces_a_replot(qtbot):
    """set_visible() alone doesn't repaint the canvas (matches
    SciQLopPlot::toggle_selected_objects_visibility()'s explicit replot() in
    the C++ H shortcut) -- without it the change is invisible until
    something else (e.g. panning) forces a redraw."""
    panel, plot, graph = _panel_with_plot(qtbot)
    graph.components()[0].set_selected(True)
    calls = []
    plot.replot = lambda *a, **kw: calls.append(True)

    menu = panel._build_context_menu(source=plot)
    action = find_action(submenu(menu, SUBMENU_TITLE), "Hide")
    action.trigger()

    assert calls, "expected plot.replot() to be called after toggling visibility"


def test_both_shown_when_axis_and_graph_both_selected(qtbot):
    panel, plot, graph = _panel_with_plot(qtbot)
    plot.y_axis().set_selected(True)
    graph.components()[0].set_selected(True)
    menu = panel._build_context_menu(source=plot)
    labels = leaf_labels(submenu(menu, SUBMENU_TITLE))
    assert "Toggle log scale" in labels
    assert "Hide" in labels


def test_selection_actions_show_shortcut_hints(qtbot):
    panel, plot, graph = _panel_with_plot(qtbot)
    plot.y_axis().set_selected(True)
    graph.components()[0].set_selected(True)
    menu = panel._build_context_menu(source=plot)
    sub = submenu(menu, SUBMENU_TITLE)
    log_action = find_action(sub, "Toggle log scale")
    hide_action = find_action(sub, "Hide")
    assert log_action.text().endswith("\tL")
    assert hide_action.text().endswith("\tH")


def test_selection_actions_have_distinct_mnemonics(qtbot):
    panel, plot, graph = _panel_with_plot(qtbot)
    plot.y_axis().set_selected(True)
    graph.components()[0].set_selected(True)
    menu = panel._build_context_menu(source=plot)
    sub = submenu(menu, SUBMENU_TITLE)
    leaves = [a for a in sub.actions() if a.menu() is None and not a.isSeparator()]
    mnemonics = [mnemonic_letter(a.text()) for a in leaves]
    assert None not in mnemonics, f"missing explicit mnemonic in {mnemonics}"
    assert len(mnemonics) == len(set(mnemonics)), f"duplicate mnemonics: {mnemonics}"
