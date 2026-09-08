from .fixtures import *


def test_panel_created_returns_panel_added_signal(main_window):
    from SciQLop.components.onboarding.backend.completions import panel_created
    assert panel_created(main_window, {}) is main_window.panel_added


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
