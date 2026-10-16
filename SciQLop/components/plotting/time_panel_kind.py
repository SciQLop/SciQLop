"""The core panel kind: the time-synchronised plot panel."""
from SciQLop.core.panel_kinds import KIND_PROPERTY, PANEL_KINDS, PanelKind
from SciQLop.core.plot_kinds import TIME_PANEL


def _create_time_panel(name: str, config: dict):
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    panel = TimeSyncPanel(parent=None, name=name, time_range=config.get("time_range"))
    panel.setProperty(KIND_PROPERTY, TIME_PANEL)
    return panel


PANEL_KINDS.contribute(PanelKind(TIME_PANEL, "Panel", create=_create_time_panel, to_config=None),
                       owner="sciqlop")
