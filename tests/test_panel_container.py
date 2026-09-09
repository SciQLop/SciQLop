import pytest
from SciQLop.core import TimeRange


@pytest.fixture
def container(qtbot):
    from SciQLop.components.plotting.ui.panel_container import PanelContainer
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    panel = TimeSyncPanel(name="TestPanel", time_range=TimeRange(1_000_000.0, 1_086_400.0))
    c = PanelContainer(panel)
    qtbot.addWidget(c)
    return c


def test_container_has_panel(container):
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    assert isinstance(container.panel, TimeSyncPanel)


def test_bar_reflects_panel_range(container):
    """Bar should be initialized with the panel's current time range."""
    tr = container.panel.time_range
    bar_tr = container.time_range_bar.time_range
    assert abs(bar_tr.start() - tr.start()) < 1
    assert abs(bar_tr.stop() - tr.stop()) < 2


def test_window_title_delegates_to_panel(container):
    """Container should use the panel's window title (for dock tab label)."""
    assert container.windowTitle() == container.panel.windowTitle()


def test_bar_change_updates_panel(container):
    """Changing the bar should propagate to the panel's time range."""
    start = 2_000_000.0
    container.time_range_bar.range_changed.emit(TimeRange(start, start + 3600))
    tr = container.panel.time_range
    assert abs(tr.start() - start) < 1


def test_panel_change_updates_bar(container):
    """Changing the panel's time range should update the bar (no signal loop)."""
    start = 3_000_000.0
    container.panel.time_range = TimeRange(start, start + 86400)
    bar_tr = container.time_range_bar.time_range
    assert abs(bar_tr.start() - start) < 1


def test_crosshair_toggle_propagates_to_existing_plots(container):
    """Toggling the crosshair button should disable/enable crosshair on all plots."""
    from SciQLopPlots import PlotType
    panel = container.panel
    panel.create_plot(0, PlotType.TimeSeries)
    panel.create_plot(1, PlotType.TimeSeries)
    plots = panel.plots()
    assert len(plots) == 2
    assert all(p.crosshair_enabled() for p in plots)

    container.crosshair_toggle.toggle()
    assert container.crosshair_toggle.isChecked() is False
    assert not any(p.crosshair_enabled() for p in panel.plots())

    container.crosshair_toggle.toggle()
    assert all(p.crosshair_enabled() for p in panel.plots())


def test_large_time_range_clamped_by_default_zoom_limit(container):
    """Default Max=1d clamps multi-day spans pushed by plugins (CDF, radio…)."""
    from SciQLopPlots import PlotType
    container.time_range_bar.max_range_seconds = 86400.0
    container.panel.create_plot(0, PlotType.TimeSeries)
    container.panel.time_range = TimeRange(0.0, 5 * 86400.0)
    span = container.panel.time_range.stop() - container.panel.time_range.start()
    assert abs(span - 86400.0) < 1.0, f"expected clamp to 86400s, got {span}"


def test_zoom_limit_setter_unblocks_large_time_range(container):
    """Setting bar.max_range_seconds to 0 (Unlimited) lets large spans through."""
    from SciQLopPlots import PlotType
    container.panel.create_plot(0, PlotType.TimeSeries)
    container.time_range_bar.max_range_seconds = 0.0
    container.panel.time_range = TimeRange(0.0, 5 * 86400.0)
    span = container.panel.time_range.stop() - container.panel.time_range.start()
    assert abs(span - 5 * 86400.0) < 1.0


def test_zoom_limit_setter_snaps_up_to_preset(container):
    """Non-preset values should snap to smallest preset >= value, not 'Unlimited'."""
    bar = container.time_range_bar
    bar.max_range_seconds = 7200.0
    assert bar.max_range_seconds == 86400.0  # next preset >= 7200 is 1d
    bar.max_range_seconds = 3600.0
    assert bar.max_range_seconds == 3600.0  # exact match
    bar.max_range_seconds = 10 * 365.25 * 86400.0
    assert bar.max_range_seconds == 0.0  # nothing fits → Unlimited


def test_crosshair_state_applied_to_new_plots(container):
    """Plots added after toggling should inherit the current crosshair state."""
    from SciQLopPlots import PlotType
    container.crosshair_toggle.toggle()
    assert container.crosshair_toggle.isChecked() is False
    container.panel.create_plot(0, PlotType.TimeSeries)
    plots = container.panel.plots()
    assert len(plots) == 1
    assert plots[0].crosshair_enabled() is False


def test_mode_shortcut_is_ctrl_shift_m_scoped_to_container(container):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeySequence
    assert container._mode_shortcut.key() == QKeySequence("Ctrl+Shift+M")
    assert container._mode_shortcut.context() == Qt.ShortcutContext.WidgetWithChildrenShortcut


def test_mode_shortcut_cycles_catalog_mode(container):
    assert container.catalog_chrome.mode == "view"
    container._mode_shortcut.activated.emit()
    assert container.catalog_chrome.mode == "jump"
    container._mode_shortcut.activated.emit()
    assert container.catalog_chrome.mode == "edit"
    container._mode_shortcut.activated.emit()
    assert container.catalog_chrome.mode == "view"


def test_autoscale_shortcut_is_ctrl_shift_a_scoped_to_container(container):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeySequence
    assert container._autoscale_shortcut.key() == QKeySequence("Ctrl+Shift+A")
    assert container._autoscale_shortcut.context() == Qt.ShortcutContext.WidgetWithChildrenShortcut


def test_autoscale_shortcut_triggers_autoscale_all_plots(container, monkeypatch):
    calls = []
    monkeypatch.setattr(container.panel, "_autoscale_all_plots", lambda: calls.append(True))
    container._autoscale_shortcut.activated.emit()
    assert calls == [True]


def test_equalize_shortcut_is_ctrl_shift_e_scoped_to_container(container):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeySequence
    assert container._equalize_shortcut.key() == QKeySequence("Ctrl+Shift+E")
    assert container._equalize_shortcut.context() == Qt.ShortcutContext.WidgetWithChildrenShortcut


def test_equalize_shortcut_triggers_equalize_plot_heights(container, monkeypatch):
    calls = []
    monkeypatch.setattr(container.panel, "_equalize_plot_heights", lambda: calls.append(True))
    container._equalize_shortcut.activated.emit()
    assert calls == [True]


def _find_action(menu, text):
    for action in menu.actions():
        if action.text().split("\t", 1)[0] == text:
            return action
    return None


def test_context_menu_has_checked_crosshair_action(container):
    menu = container.panel._build_context_menu()
    action = _find_action(menu, "Crosshair")
    assert action is not None
    assert action.isCheckable()
    assert action.isChecked()


def test_context_menu_crosshair_action_drives_toggle(container):
    menu = container.panel._build_context_menu()
    _find_action(menu, "Crosshair").trigger()
    assert container.crosshair_toggle.isChecked() is False


def test_bare_panel_context_menu_has_no_crosshair_action(qtbot):
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    panel = TimeSyncPanel(name="Bare", time_range=TimeRange(1_000_000.0, 1_086_400.0))
    qtbot.addWidget(panel)
    menu = panel._build_context_menu()
    assert _find_action(menu, "Crosshair") is None


def test_template_range_beyond_zoom_limit_raises_the_limit(container, monkeypatch):
    """A template/proxy link with no zoom limit of its own must restore its
    full range: the limit is raised to fit instead of clamping the range."""
    from SciQLopPlots import PlotType
    from SciQLop.components.plotting.panel_template import (
        PanelTemplate, PlotModel, ProductModel, TimeRangeModel,
    )
    from SciQLop.components.plotting.ui import time_sync_panel

    def fake_plot_product(panel, path, **kwargs):
        panel.create_plot(len(panel.plots()), PlotType.TimeSeries)
        return (panel.plots()[-1], "graph")

    monkeypatch.setattr(time_sync_panel, "plot_product", fake_plot_product)
    container.time_range_bar.max_range_seconds = 86400.0
    template = PanelTemplate(
        name="wide",
        time_range=TimeRangeModel(start="2025-04-12T00:00:00Z", stop="2025-04-19T00:00:00Z"),
        plots=[PlotModel(products=[ProductModel(path="speasy//amda//imf", kind="speasy")])],
    )
    template.apply(container.panel)
    span = container.panel.time_range.stop() - container.panel.time_range.start()
    assert abs(span - 7 * 86400.0) < 1.0, f"range clamped to {span / 86400:.1f} days"
    assert container.time_range_bar.max_range_seconds >= 7 * 86400.0 or \
        container.time_range_bar.max_range_seconds == 0.0
