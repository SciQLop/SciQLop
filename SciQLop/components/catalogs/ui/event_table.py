from __future__ import annotations

import itertools
import operator
from numbers import Real
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QTimer, Qt

from ..backend.event_text import _format_meta_value, format_event_time  # noqa: F401  (re-exported)
from ..backend.provider import Capability, CatalogEvent


_FIXED_COLUMN_TITLES = ("Start (UTC)", "Stop (UTC)")


def _sort_value(value) -> tuple:
    """Numbers before text, each in its own order: one column may hold both."""
    if isinstance(value, Real) and not isinstance(value, bool):
        return 0, float(value)
    return 1, str(value)


def _meta_keys(events) -> list[str]:
    keys: set[str] = set()
    for e in events:
        keys.update(e.meta.keys())
    return sorted(keys)


class EventTableModel(QAbstractTableModel):
    """Table model for catalog events: start, stop, then dynamic meta columns.

    It sorts and filters itself, once per request: rows are the events the filter keeps (set_kept),
    in the table's order (sort). A QSortFilterProxyModel asked data() for every comparison and
    filterAcceptsRow() for every row, from Python: seconds on 100,000 events."""

    _FIXED_COLUMNS = ("start", "stop")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all: list[CatalogEvent] = []      # the catalogue's events (or a preview), in the table's order
        self._uuids: list[str] = []             # theirs, read once: a list pass in C, not a property per row
        self._events: list[CatalogEvent] = []   # the rows: those of _all the filter keeps
        self._row_uuids: list[str] = []
        self._kept: set[str] | None = None
        self._rows: dict[str, int] | None = None  # uuid -> row, built when first asked
        self._sort_column: int | None = None
        self._sort_order = Qt.SortOrder.AscendingOrder
        self._resort = QTimer(self)  # one re-sort after a burst of edits (a bulk edit of many rows)
        self._resort.setSingleShot(True)
        self._resort.setInterval(0)
        self._resort.timeout.connect(self._sort_again)
        self._meta_keys: list[str] = []
        self._provider = None
        self._catalog = None
        self._signals_provider = None
        self._editable = False
        self._read_only = False

    def set_context(self, provider, catalog) -> None:
        """Bind the model to a provider/catalog so setData can route through them."""
        self.beginResetModel()
        self._provider = provider
        self._catalog = catalog
        self._kept = None  # another catalogue: its own filter decides
        self._editable = self._can_edit()
        self._connect_provider_signals()
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
        """The catalogue's events (all of them: the kept set, if any, still applies)."""
        self.beginResetModel()
        self._meta_keys = _meta_keys(events)
        self._arrange(self._sorted(events))
        self._keep()
        self.endResetModel()

    def set_kept(self, kept: set[str] | None) -> None:
        """The uuids the filter keeps; None keeps every event."""
        self._kept = kept
        self._relayout(self._keep)

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        self._sort_column, self._sort_order = column, order
        self._sort_again()

    def _sort_again(self) -> None:
        self._relayout(lambda: (self._arrange(self._sorted(self._all)), self._keep()))

    def _sorted(self, events) -> list[CatalogEvent]:
        if self._sort_column is None or not 0 <= self._sort_column < self.columnCount():
            return list(events)
        return sorted(events, key=self._sort_key(self._sort_column),
                      reverse=self._sort_order == Qt.SortOrder.DescendingOrder)

    def _sort_key(self, column: int):
        if column < len(self._FIXED_COLUMNS):
            return operator.attrgetter(self._FIXED_COLUMNS[column])
        key = self._meta_keys[column - len(self._FIXED_COLUMNS)]
        return lambda event: _sort_value(event.meta.get(key, ""))

    def _arrange(self, ordered: list[CatalogEvent]) -> None:
        self._all, self._uuids = ordered, [e.uuid for e in ordered]

    def _keep(self) -> None:
        if self._kept is None:
            self._events, self._row_uuids = self._all, self._uuids
        else:
            kept = list(map(self._kept.__contains__, self._uuids))
            self._events = list(itertools.compress(self._all, kept))
            self._row_uuids = list(itertools.compress(self._uuids, kept))
        self._rows = None

    def _relayout(self, change) -> None:
        """New rows without a reset: the selection and the current row follow their events."""
        self.layoutAboutToBeChanged.emit()
        old = self.persistentIndexList()
        held = [(self._row_uuids[i.row()], i.column()) for i in old]
        change()
        self.changePersistentIndexList(old, [self._index_of(uuid, column) for uuid, column in held])
        self.layoutChanged.emit()

    def _index_of(self, uuid: str, column: int) -> QModelIndex:
        row = self.row_for_uuid(uuid)
        return self.index(row, column) if row >= 0 else QModelIndex()

    def total_count(self) -> int:
        """The catalogue's events, kept or not."""
        return len(self._all)

    def all_events(self) -> list[CatalogEvent]:
        return list(self._all)

    def _connect_provider_signals(self) -> None:
        """The provider's signals tell which event moved or changed: connecting to each event took
        about 0.3 s for a catalogue of 100,000."""
        self._disconnect_provider_signals()
        if self._provider is not None:
            self._provider.event_meta_changed.connect(self._on_event_meta_changed)
            self._provider.event_range_changed.connect(self._on_event_range_changed)
            self._signals_provider = self._provider

    def _disconnect_provider_signals(self) -> None:
        if self._signals_provider is None:
            return
        for signal, slot in ((self._signals_provider.event_meta_changed, self._on_event_meta_changed),
                             (self._signals_provider.event_range_changed, self._on_event_range_changed)):
            try:
                signal.disconnect(slot)
            except RuntimeError:
                pass
        self._signals_provider = None

    def _on_event_range_changed(self, catalog, event) -> None:
        if self._catalog is None or catalog.uuid != self._catalog.uuid:
            return
        row = self.row_for_event(event)
        if row >= 0:
            self.dataChanged.emit(self.index(row, 0), self.index(row, 1), [int(Qt.ItemDataRole.DisplayRole)])
        if self._sort_column in (0, 1):
            self._resort.start()

    def _on_event_meta_changed(self, catalog, event, key: str) -> None:
        if self._catalog is None or catalog.uuid != self._catalog.uuid:
            return
        if self._sort_column is not None and self._column_key(self._sort_column) == key:
            self._resort.start()  # kept or not: a filter change shows it in its place
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

    def _column_key(self, column: int) -> str | None:
        meta = column - len(self._FIXED_COLUMNS)
        return self._meta_keys[meta] if 0 <= meta < len(self._meta_keys) else None

    def clear(self) -> None:
        self.beginResetModel()
        self._disconnect_provider_signals()
        self._all, self._uuids, self._events, self._row_uuids, self._rows = [], [], [], [], None
        self._meta_keys = []
        self.endResetModel()

    def event_at(self, row: int) -> CatalogEvent | None:
        if 0 <= row < len(self._events):
            return self._events[row]
        return None

    def row_for_event(self, event) -> int:
        """Return the row index of the event matching by uuid, or -1 if not found."""
        return self.row_for_uuid(event.uuid)

    def row_for_uuid(self, uuid: str) -> int:
        if self._rows is None:
            self._rows = dict(zip(self._row_uuids, itertools.count()))
        return self._rows.get(uuid, -1)

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
