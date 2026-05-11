from __future__ import annotations

from numbers import Real
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt

from ..backend.provider import Capability, CatalogEvent


_SCI_LOWER = 1e-3
_SCI_UPPER = 1e6


def _format_float(value: float) -> str:
    """Format a float for display: scientific when very small or very large,
    general otherwise. Default precision is 6 significant digits."""
    if value == 0.0:
        return "0"
    abs_v = abs(value)
    if abs_v < _SCI_LOWER or abs_v >= _SCI_UPPER:
        return f"{value:.6e}"
    return f"{value:.6g}"


def _format_meta_value(value: Any) -> str:
    if isinstance(value, bool) or value is None:
        return str(value) if value is not None else ""
    if isinstance(value, Real) and not isinstance(value, int):
        return _format_float(float(value))
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(v) for v in value)
    if isinstance(value, str):
        from datetime import datetime as _dt
        try:
            parsed = _dt.fromisoformat(value)
            return parsed.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    return str(value)


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
        self._event_connections: list = []
        self._editable = False

    def set_context(self, provider, catalog) -> None:
        """Bind the model to a provider/catalog so setData can route through them."""
        self.beginResetModel()
        self._provider = provider
        self._catalog = catalog
        self._editable = (provider is not None and catalog is not None
                          and Capability.EDIT_EVENTS in provider.capabilities(catalog))
        self._connect_provider_meta_signal()
        self.endResetModel()

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
        self._event_connections = []
        for e in self._events:
            fn = lambda ev=e: self._on_event_range_changed(self.row_for_event(ev))
            e.range_changed.connect(fn)
            self._event_connections.append((e, fn))

    def _disconnect_events(self) -> None:
        for e, fn in self._event_connections:
            try:
                e.range_changed.disconnect(fn)
            except RuntimeError:
                pass
        self._event_connections = []

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
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        base = super().flags(index)
        if not index.isValid():
            return base
        if self._editable:
            base |= Qt.ItemFlag.ItemIsEditable
        base |= Qt.ItemFlag.ItemIsDragEnabled
        return base

    def mimeTypes(self):
        from SciQLop.core.mime.types import EVENT_LIST_MIME_TYPE
        return [EVENT_LIST_MIME_TYPE]

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
        return encode_event_list(provider_name, self._catalog.uuid, events)

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
                return self._FIXED_COLUMNS[section]
            return self._meta_keys[section - len(self._FIXED_COLUMNS)]
        return str(section + 1)


class EventSortProxy(QSortFilterProxyModel):
    """Sorts by numeric timestamps for start/stop columns."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSortRole(EventTableModel.SortRole)
