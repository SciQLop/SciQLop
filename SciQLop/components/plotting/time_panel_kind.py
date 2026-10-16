"""The core panel kind: the time-synchronised plot panel."""
from SciQLop.core.panel_kinds import KIND_PROPERTY, PANEL_KINDS, PanelKind
from SciQLop.core.plot_kinds import TIME_PANEL


def _create_time_panel(name: str, config: dict):
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    panel = TimeSyncPanel(parent=None, name=name, time_range=config.get("time_range"))
    panel.setProperty(KIND_PROPERTY, TIME_PANEL)
    return panel


def _time_panel_config(panel) -> dict:
    # Only {"time_range": ...}: the plots live in the tree's slots, so save a time panel through panel_tree.
    from SciQLop.components.plotting.panel_template import panel_tree
    return panel_tree(panel)["config"]


PANEL_KINDS.contribute(PanelKind(TIME_PANEL, "Panel", create=_create_time_panel, to_config=_time_panel_config),
                       owner="sciqlop")
