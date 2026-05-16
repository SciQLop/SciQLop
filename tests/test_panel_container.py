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
