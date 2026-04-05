from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from ..backend.provider import CatalogEvent


class EventTableModel(QAbstractTableModel):
    """Table model for catalog events: start, stop, then dynamic meta columns."""

    _FIXED_COLUMNS = ("start", "stop")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._events: list[CatalogEvent] = []
        self._meta_keys: list[str] = []

    def set_events(self, events: list[CatalogEvent]) -> None:
        self.beginResetModel()
        self._disconnect_events()
        self._events = list(events)
        # Collect all meta keys across events, sorted for stable column order
        keys: set[str] = set()
        for e in self._events:
            keys.update(e.meta.keys())
        self._meta_keys = sorted(keys)
        self._connect_events()
        self.endResetModel()

    def _connect_events(self) -> None:
        self._event_connections = []
        for i, e in enumerate(self._events):
            fn = lambda row=i: self._on_event_range_changed(row)
            e.range_changed.connect(fn)
            self._event_connections.append((e, fn))

    def _disconnect_events(self) -> None:
        for e, fn in getattr(self, '_event_connections', []):
            try:
                e.range_changed.disconnect(fn)
            except RuntimeError:
                pass
        self._event_connections = []

    def _on_event_range_changed(self, row: int) -> None:
        left = self.index(row, 0)
        right = self.index(row, 1)
        self.dataChanged.emit(left, right, [int(Qt.ItemDataRole.DisplayRole)])

    def clear(self) -> None:
        self.beginResetModel()
        self._disconnect_events()
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

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        event = self._events[index.row()]
        col = index.column()
        if col == 0:
            return str(event.start)
        elif col == 1:
            return str(event.stop)
        else:
            key = self._meta_keys[col - len(self._FIXED_COLUMNS)]
            return str(event.meta.get(key, ""))

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            if section < len(self._FIXED_COLUMNS):
                return self._FIXED_COLUMNS[section]
            return self._meta_keys[section - len(self._FIXED_COLUMNS)]
        return str(section + 1)
