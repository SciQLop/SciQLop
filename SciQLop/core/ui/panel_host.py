"""One docking path for every panel kind: dock a panel in a main window, find the docked panels."""
from typing import List, Optional, Tuple

import PySide6QtAds as QtAds
import shiboken6
from PySide6.QtWidgets import QWidget

from SciQLop.components.plotting.ui.panel_container import PanelContainer
from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
from SciQLop.core.panel_kinds import KIND_PROPERTY, panel_kind_of


def panel_of(dock_widget) -> Optional[QWidget]:
    from SciQLop.core.ui.mainwindow import _extract_panel
    panel = _extract_panel(dock_widget)
    if panel is not None or dock_widget is None or not shiboken6.isValid(dock_widget):
        return panel
    widget = dock_widget.widget()
    if widget is None or not shiboken6.isValid(widget) or panel_kind_of(widget) is None:
        return None
    return widget


def panel_docks(main_window) -> List[Tuple[QtAds.CDockWidget, QWidget]]:
    # dockWidgetsMap(), not dockWidgets(): the latter skips floating docks.
    pairs = ((dw, panel_of(dw)) for dw in main_window.dock_manager.dockWidgetsMap().values())
    return [(dw, p) for dw, p in pairs if p is not None]


def _dock_content(panel: QWidget) -> QWidget:
    return PanelContainer(panel) if isinstance(panel, TimeSyncPanel) else panel


def _dock_holding(main_window, content: QWidget) -> Optional[QtAds.CDockWidget]:
    return next((dw for dw in main_window.dock_manager.dockWidgetsMap().values()
                 if shiboken6.isValid(dw) and dw.widget() is content), None)


def _wire_dock(main_window, panel: QWidget, dock_widget: QtAds.CDockWidget) -> None:
    from SciQLop.core.ui.mainwindow import _follow_panel_renames
    # addWidgetIntoDock may have tabbed this panel into an existing area (e.g. the welcome page's)
    # rather than creating a fresh one: dockAreaCreated only fires for the latter.
    main_window._ensure_add_panel_button(dock_widget.dockAreaWidget())
    _follow_panel_renames(panel, dock_widget)
    dock_widget.closed.connect(lambda: main_window._on_panel_dock_closed(dock_widget))


def _wire_panel(main_window, panel: QWidget) -> None:
    if hasattr(panel, "delete_me"):
        panel.delete_me.connect(lambda: main_window.remove_panel(panel))
    main_window.panel_added.emit(panel)
    main_window._notify_panels_list_changed()
    panel.destroyed.connect(main_window._notify_panels_list_changed)
    panel_name = panel.objectName()
    panel.destroyed.connect(lambda *_: main_window._schedule_dead_panel_drop(panel_name))


def dock_panel(main_window, panel: QWidget, kind_id: str, area=None) -> Optional[QtAds.CDockWidget]:
    """Dock delete-on-close; the X goes through remove_panel, renames follow, panel_added is emitted."""
    panel.setProperty(KIND_PROPERTY, kind_id)
    content = _dock_content(panel)
    main_window.addWidgetIntoDock(QtAds.DockWidgetArea.TopDockWidgetArea, content, area=area,
                                  delete_on_close=True,
                                  custom_close_callback=lambda: main_window.remove_panel(panel))
    dock_widget = _dock_holding(main_window, content)
    if dock_widget is not None:
        _wire_dock(main_window, panel, dock_widget)
    _wire_panel(main_window, panel)
    return dock_widget
