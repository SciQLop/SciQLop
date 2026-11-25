from __future__ import annotations

from numbers import Real
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt

from ..backend.event_text import _format_meta_value, format_event_time  # noqa: F401  (re-exported)
from ..backend.provider import Capability, CatalogEvent


_FIXED_COLUMN_TITLES = ("Start (UTC)", "Stop (UTC)")


class EventTableModel(QAbstractTableModel):
    """Table model for catalog events: start, stop, then dynamic meta columns."""

    SortRole = Qt.ItemDataRole.UserRole + 1
    _FIXED_COLUMNS = ("start", "stop")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._events: list[CatalogEvent] = []
        self._meta_keys: list[str] = []
        self._provider = None
        self._catalog = None
        self._meta_signal_provider = None
        self._followed_events: list[CatalogEvent] = []
        self._editable = False
        self._read_only = False

    def set_context(self, provider, catalog) -> None:
        """Bind the model to a provider/catalog so setData can route through them."""
        self.beginResetModel()
        self._provider = provider
        self._catalog = catalog
        self._editable = self._can_edit()
        self._connect_provider_meta_signal()
        self.endResetModel()

    def set_read_only(self, read_only: bool) -> None:
        """Shown but not the catalogue's own (a preview): nothing to edit."""
        self._read_only = read_only
        self.refresh_editable()

    def _can_edit(self) -> bool:
        return (not self._read_only and self._provider is not None and self._catalog is not None
                and Capability.EDIT_EVENTS in self._provider.capabilities(self._catalog))

    def refresh_editable(self) -> None:
        """Re-read EDIT_EVENTS without a reset, so the view keeps its rows and selection."""
        editable = self._can_edit()
        changed, self._editable = editable != self._editable, editable
        if changed and self.rowCount() and self.columnCount():
            self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount() - 1, self.columnCount() - 1))

    def set_events(self, events: list[CatalogEvent]) -> None:
        self.beginResetModel()
        self._disconnect_events()
        self._events = list(events)
        keys: set[str] = set()
        for e in self._events:
            keys.update(e.meta.keys())
        self._meta_keys = sorted(keys)
        self._connect_events()
        self.endResetModel()

    def _connect_events(self) -> None:
        # A method slot and sender(), not a closure per event: PySide scans every connection to a
        # closure each time a sender dies, which made closing a big catalog quadratic.
        self._followed_events = list(self._events)
        for e in self._followed_events:
            e.range_changed.connect(self._on_shown_event_range_changed)

    def _disconnect_events(self) -> None:
        for e in self._followed_events:
            try:
                e.range_changed.disconnect(self._on_shown_event_range_changed)
            except RuntimeError:
                pass
        self._followed_events = []

    def _on_shown_event_range_changed(self) -> None:
        self._on_event_range_changed(self.row_for_event(self.sender()))

    def _connect_provider_meta_signal(self) -> None:
        if self._meta_signal_provider is not None:
            try:
                self._meta_signal_provider.event_meta_changed.disconnect(self._on_event_meta_changed)
            except RuntimeError:
                pass
            self._meta_signal_provider = None
        if self._provider is not None:
            self._provider.event_meta_changed.connect(self._on_event_meta_changed)
            self._meta_signal_provider = self._provider

    def _on_event_range_changed(self, row: int) -> None:
        if row < 0:
            return
        left = self.index(row, 0)
        right = self.index(row, 1)
        self.dataChanged.emit(left, right, [int(Qt.ItemDataRole.DisplayRole)])

    def _on_event_meta_changed(self, catalog, event, key: str) -> None:
        if self._catalog is None or catalog.uuid != self._catalog.uuid:
            return
        row = self.row_for_event(event)
        if row < 0:
            return
        if key not in self._meta_keys:
            new_keys = sorted(set(self._meta_keys) | {key})
            insert_idx = new_keys.index(key)
            col = len(self._FIXED_COLUMNS) + insert_idx
            self.beginInsertColumns(QModelIndex(), col, col)
            self._meta_keys = new_keys
            self.endInsertColumns()
            return
        col = len(self._FIXED_COLUMNS) + self._meta_keys.index(key)
        idx = self.index(row, col)
        self.dataChanged.emit(idx, idx, [int(Qt.ItemDataRole.DisplayRole)])

    def clear(self) -> None:
        self.beginResetModel()
        self._disconnect_events()
        if self._meta_signal_provider is not None:
            try:
                self._meta_signal_provider.event_meta_changed.disconnect(self._on_event_meta_changed)
            except RuntimeError:
                pass
            self._meta_signal_provider = None
        self._events = []
        self._meta_keys = []
        self.endResetModel()

    def event_at(self, row: int) -> CatalogEvent | None:
        if 0 <= row < len(self._events):
            return self._events[row]
        return None

    def row_for_event(self, event) -> int:
        """Return the row index of the event matching by uuid, or -1 if not found."""
        for i, e in enumerate(self._events):
            if e.uuid == event.uuid:
                return i
        return -1

    # ---- QAbstractTableModel interface ----

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._events)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._FIXED_COLUMNS) + len(self._meta_keys)

    def _format_dt(self, dt) -> str:
        return format_event_time(dt)

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        base = super().flags(index)
        if not index.isValid():
            return base
        if self._editable:
            base |= Qt.ItemFlag.ItemIsEditable
        base |= Qt.ItemFlag.ItemIsDragEnabled
        return base

    def mimeTypes(self):
        from SciQLop.core.mime.types import EVENT_LIST_MIME_TYPE, TIME_RANGE_MIME_TYPE
        return [EVENT_LIST_MIME_TYPE, TIME_RANGE_MIME_TYPE]

    def supportedDragActions(self) -> Qt.DropAction:
        # Default is CopyAction only, which would cap the tree's DnD
        # semantics (link/move/duplicate) to "copy" regardless of what
        # CatalogTreeModel.supportedDropActions declares -- Qt only offers
        # an action present on *both* sides.
        return Qt.DropAction.LinkAction | Qt.DropAction.MoveAction | Qt.DropAction.CopyAction

    def mimeData(self, indexes):
        from SciQLop.components.catalogs.backend.event_mime import encode_event_list
        if self._catalog is None:
            return None
        seen: set[str] = set()
        events = []
        for idx in indexes:
            if not idx.isValid():
                continue
            row = idx.row()
            if 0 <= row < len(self._events):
                ev = self._events[row]
                if ev.uuid not in seen:
                    seen.add(ev.uuid)
                    events.append(ev)
        if not events:
            return None
        provider_name = self._catalog.provider.name if self._catalog.provider else ""
        md = encode_event_list(provider_name, self._catalog.uuid, events)
        # Also tag the drag with a time range covering the selection, so
        # dropping event(s) on a plot panel (which already accepts
        # TIME_RANGE_MIME_TYPE) jumps there -- free of any plot-side change.
        import json
        from SciQLop.core.mime.types import TIME_RANGE_MIME_TYPE
        start = min(e.start for e in events).timestamp()
        stop = max(e.stop for e in events).timestamp()
        md.setData(TIME_RANGE_MIME_TYPE, json.dumps({"start": start, "stop": stop}).encode("utf-8"))
        return md

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        event = self._events[index.row()]
        col = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return self._format_dt(event.start)
            elif col == 1:
                return self._format_dt(event.stop)
            else:
                key = self._meta_keys[col - len(self._FIXED_COLUMNS)]
                return _format_meta_value(event.meta.get(key, ""))
        elif role == self.SortRole:
            if col == 0:
                return event.start.timestamp()
            elif col == 1:
                return event.stop.timestamp()
            else:
                key = self._meta_keys[col - len(self._FIXED_COLUMNS)]
                value = event.meta.get(key, "")
                if isinstance(value, Real) and not isinstance(value, bool):
                    return float(value)
                return str(value)
        return None

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if role != Qt.ItemDataRole.EditRole or not index.isValid():
            return False
        if self._provider is None or self._catalog is None:
            return False
        event = self._events[index.row()]
        col = index.column()
        if col == 0:
            try:
                event.start = value
            except (TypeError, ValueError):
                return False
            return True
        if col == 1:
            try:
                event.stop = value
            except (TypeError, ValueError):
                return False
            return True
        key = self._meta_keys[col - len(self._FIXED_COLUMNS)]
        self._provider.set_event_meta(self._catalog, event, key, value)
        return True

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            if section < len(self._FIXED_COLUMNS):
                return _FIXED_COLUMN_TITLES[section]
            return self._meta_keys[section - len(self._FIXED_COLUMNS)]
        return str(section + 1)


class EventSortProxy(QSortFilterProxyModel):
    """Sorts by numeric timestamps for start/stop columns; keeps the rows the event filter accepts
    (the hosted delegate's accepts: one cheap call per row, the matching done beforehand)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSortRole(EventTableModel.SortRole)
        self._accepts = None

    def set_accepts(self, accepts) -> None:
        """``accepts(event) -> bool``, or None to keep every row."""
        self._accepts = accepts
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if self._accepts is None:
            return True
        event = self.sourceModel().event_at(source_row)
        return event is None or self._accepts(event)
