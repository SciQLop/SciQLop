from .fixtures import *


def test_panel_created_waits_for_a_time_panel_on_panel_added(main_window):
    from PySide6.QtWidgets import QLabel
    from SciQLop.components.onboarding.backend.completions import panel_created
    signal, predicate = panel_created(main_window, {})
    assert signal is main_window.panel_added
    assert predicate(QLabel()) is False


def test_a_plugin_panel_does_not_complete_the_create_panel_step(main_window, qtbot):
    """The later tour steps call plots() and plot_list_changed on the stored panel: a plugin panel has neither."""
    from PySide6.QtWidgets import QLabel
    from SciQLop.components.onboarding.backend.completions import panel_created
    from SciQLop.components.onboarding.backend.tour import Tour, TourStep
    from SciQLop.components.onboarding.ui.tour_controller import TourController
    from SciQLop.core.extensions import owned_by
    from SciQLop.core.panel_kinds import PANEL_KINDS, PanelKind

    def _side_tab(mw, ctx):
        return mw.dock_manager.findDockWidget("Products").sideTabWidget()

    tour = Tour(id="t_pk", title="t_pk", description="test tour", steps=[
        TourStep(step_id="create_panel", title="t", body="b", resolver=_side_tab, completion=panel_created),
        TourStep(step_id="after", title="t", body="b", resolver=_side_tab)])
    with owned_by("pk_tour"):
        PANEL_KINDS.contribute(PanelKind("pk_tour.label", "Label", create=lambda name, config: QLabel()))
    controller = TourController(main_window, tour)
    controller.start()
    opened = []
    try:
        qtbot.waitUntil(lambda: controller._coach_mark.isVisible(), timeout=1000)
        opened.append(main_window.open_panel("pk_tour.label"))
        opened.append(main_window.new_plot_panel())
        qtbot.waitUntil(lambda: controller._current_step().step_id == "after", timeout=1000)
        assert controller._context["create_panel"] is opened[1]
    finally:
        controller.abort()
        PANEL_KINDS.remove_owner("pk_tour")
        for panel in opened:
            main_window.remove_panel(panel)
        qtbot.waitUntil(lambda: not set(opened) & set(main_window.panels()))


def test_dock_visible_returns_none_when_dock_missing(main_window):
    from SciQLop.components.onboarding.backend.completions import dock_visible
    result = dock_visible("No Such Dock")(main_window, {})
    assert result is None


def test_dock_visible_predicate_filters_on_true(main_window):
    from SciQLop.components.onboarding.backend.completions import dock_visible
    signal, predicate = dock_visible("Products")(main_window, {})
    assert signal is main_window.dock_manager.findDockWidget("Products").visibilityChanged
    assert predicate(True) is True
    assert predicate(False) is False


def test_plot_settled_in_returns_none_when_context_key_missing():
    from SciQLop.components.onboarding.backend.completions import plot_settled_in
    assert plot_settled_in("create_panel")(None, {}) is None


def test_plot_settled_in_waits_for_the_list_to_stop_churning(qtbot):
    """Drag-and-drop keeps churning the panel's plot list (placeholder
    waves, a re-created plot) after the first real plot shows up, so the
    step must complete only once the list has stopped changing, with the
    last real plot. The settle timer is fired by hand: real waits are
    unreliable under a loaded event loop."""
    from PySide6.QtCore import QObject, Signal
    from SciQLop.components.onboarding.backend.completions import plot_settled_in, _PlotListSettled

    class _FakePlot(QObject):
        def __init__(self, name):
            super().__init__()
            self.setObjectName(name)

    class _FakePanel(QObject):
        plot_list_changed = Signal(list)

        def __init__(self):
            super().__init__()
            self._current_plots = []

        def plots(self):
            return self._current_plots

        def change(self, plots):
            self._current_plots = plots
            self.plot_list_changed.emit(plots)

    panel = _FakePanel()
    signal = plot_settled_in("create_panel")(None, {"create_panel": panel})
    waiter = panel.findChild(_PlotListSettled)
    received = []
    signal.connect(received.append)

    panel.change([_FakePlot("PlaceHolder")])
    assert not waiter._timer.isActive(), "placeholder alone must never arm the settle timer"

    real_plot = _FakePlot("Plot")
    panel.change([real_plot])
    assert waiter._timer.isActive()
    qtbot.wait(20)
    assert received == [], "must not complete on the first sighting"

    panel.change([real_plot, _FakePlot("PlaceHolder")])
    assert waiter._timer.isActive(), "more churn keeps the wait going"
    assert received == []

    waiter._timer.timeout.emit()
    assert received == [real_plot], "settled: the last real plot completes the step"
