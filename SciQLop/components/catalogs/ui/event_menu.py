"""The event section of a panel's right-click menu, for the catalog event under the cursor, and the
popup that edits that event's attributes exactly like a row of the catalog browser's event table."""
from __future__ import annotations

from datetime import timezone

from PySide6.QtCore import Qt, QTransposeProxyModel
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QAbstractItemView, QDialog, QHeaderView, QMenu, QTableView, QVBoxLayout

from SciQLop.components.command_palette.arg_types import catalog_arg_value
from SciQLop.components.command_palette.menu_entries import add_menu_entries
from SciQLop.core import TimeRange
from SciQLop.core.menus import CATALOG_EVENTS
from SciQLop.core.ui.tooltips import rich_tooltip

from SciQLop.components.catalogs.backend.panel_manager import ZERO_LENGTH_EVENT_MARGIN_S
from .event_table import EventTableModel, format_event_time
from .event_table_delegate import EventTableDelegate

_ZOOM_PADDING = 0.1  # of the event's duration, each side, so its edges stay visible and draggable


def add_event_section(menu: QMenu, panel, overlay, event) -> None:
    """Entries for *event* (drawn by *overlay* on *panel*), then the plugins' catalog.events entries,
    then a separator before the panel's own entries."""
    catalog = overlay.catalog
    title = menu.addAction(f"Event: {_title(event)}")
    title.setEnabled(False)
    editing = not overlay.read_only
    if editing:
        _add(menu, "Edit attributes…", "Edit this event's attributes, like a row of the catalog's event table.",
             lambda: _open_popup(panel, catalog, event, editable=True))
    else:
        _add(menu, "Show attributes…", "Show this event's attributes. Switch the panel to Edit mode to change them.",
             lambda: _open_popup(panel, catalog, event, editable=False))
    _add(menu, "Show in Catalogs", "Open this event's catalog in the Catalogs pane and select the event.",
         lambda: _show_in_browser(panel, catalog, event))
    _add(menu, "Zoom to event", "Show this event, with a margin on each side.", lambda: _zoom(panel, event))
    _add(menu, "Copy start and stop", "Copy the start and stop times (UTC), as two spreadsheet cells.",
         lambda: QGuiApplication.clipboard().setText(_range_text(event)))
    delete = _add(menu, "Delete", "Delete this event from its catalog.", lambda: overlay.delete_event(event))
    if not overlay.can_delete_events:
        delete.setEnabled(False)
        delete.setToolTip(rich_tooltip("Delete", "Switch the panel to edit mode to delete events; "
                                                 "some catalogs don't allow it at all."))
    add_menu_entries(menu, CATALOG_EVENTS, _menu_context(catalog, event))
    menu.addSeparator()


def _add(menu: QMenu, text: str, tooltip: str, slot):
    action = menu.addAction(text)
    action.setToolTip(rich_tooltip(text, tooltip))
    action.triggered.connect(lambda _checked=False: slot())
    return action


def _title(event) -> str:
    label = event.meta.get("label")
    return str(label) if label else f"{format_event_time(event.start)} UTC"


def _iso_utc(when) -> str:
    return when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _range_text(event) -> str:
    return f"{_iso_utc(event.start)}\t{_iso_utc(event.stop)}"


def _zoom(panel, event) -> None:
    start, stop = event.start.timestamp(), event.stop.timestamp()
    pad = (stop - start) * _ZOOM_PADDING if stop > start else ZERO_LENGTH_EVENT_MARGIN_S
    panel.time_range = TimeRange(start - pad, stop + pad)


def _show_in_browser(panel, catalog, event) -> None:
    panel.catalog_manager.catalog_event_clicked.emit(catalog, event)
    window = panel.window()
    if hasattr(window, "catalogs_browser"):
        window.reveal(window.catalogs_browser)


def _menu_context(catalog, event) -> dict:
    """The same context as the event table's menu, so a plugin entry shows in both."""
    name = catalog.provider.name
    return {"provider": name, "catalog": catalog_arg_value(name, catalog.uuid), "events": event.uuid}


def _open_popup(panel, catalog, event, editable: bool) -> None:
    popup = EventAttributesPopup(catalog, event, parent=panel, editable=editable)
    popup.show()


class EventAttributesPopup(QDialog):
    """One event of the event table, turned on its side: one row per attribute. Same model, same
    delegate and attribute specs, so it edits exactly like the table, writing through the provider,
    and is read-only where the table is. Opened from a panel that is not in Edit mode it only shows
    (editable=False): the same rule as dragging or deleting the event there."""

    def __init__(self, catalog, event, parent=None, editable: bool = True):
        super().__init__(parent, Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle(f"{catalog.name}: {_title(event)}")
        self.source_model = EventTableModel(self)
        self.source_model.set_context(catalog.provider, catalog)
        self.source_model.set_events([event])
        # The model listens to the event's signals through closures: let go of them on close.
        self.finished.connect(self.source_model.clear)
        self.view = _attribute_view(self.source_model, self)
        if not editable:
            self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self.view)


def _attribute_view(source_model: EventTableModel, parent) -> QTableView:
    transposed = QTransposeProxyModel(parent)
    transposed.setSourceModel(source_model)
    view = QTableView(parent)
    view.setModel(transposed)
    view.setItemDelegate(EventTableDelegate(source_model, view))
    view.horizontalHeader().hide()
    view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    view.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed
                         | QAbstractItemView.EditTrigger.SelectedClicked)
    return view
