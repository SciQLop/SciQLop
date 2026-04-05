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
