from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from PySide6.QtCore import QDateTime, QModelIndex, Qt
from PySide6.QtWidgets import QStyledItemDelegate, QWidget, QDateTimeEdit

from SciQLop.components.settings.ui.settings_delegates import (
    SettingDelegate,
    BoolDelegate,
    IntDelegate,
    FloatDelegate,
    StrDelegate,
)


def _infer_column_type(values: list[Any]) -> type:
    """Most-specific type covering all non-empty values; default str."""
    types = {type(v) for v in values if v is not None and v != ""}
    if not types:
        return str
    if types == {bool}:
        return bool
    if types <= {bool, int}:
        return int
    if types <= {bool, int, float}:
        return float
    return str


_DELEGATE_FOR_TYPE = {
    bool: BoolDelegate,
    int: IntDelegate,
    float: FloatDelegate,
    str: StrDelegate,
}


class EventTableDelegate(QStyledItemDelegate):
    """Picks an editor widget per column by inferring the value type."""

    _DATETIME_FORMAT = "yyyy-MM-dd HH:mm:ss"

    def __init__(self, source_model, parent=None):
        super().__init__(parent)
        self._source_model = source_model
        self._column_types: dict[int, type] = {}
        source_model.modelReset.connect(self._column_types.clear)
        source_model.columnsInserted.connect(lambda *_: self._column_types.clear())

    def _column_type(self, source_col: int) -> type:
        if source_col in self._column_types:
            return self._column_types[source_col]
        meta_offset = len(self._source_model._FIXED_COLUMNS)
        if source_col < meta_offset:
            t: type = datetime
        else:
            key = self._source_model._meta_keys[source_col - meta_offset]
            values = [e.meta.get(key) for e in self._source_model._events]
            t = _infer_column_type(values)
        self._column_types[source_col] = t
        return t

    def _to_source(self, index: QModelIndex) -> QModelIndex:
        m = index.model()
        if hasattr(m, "mapToSource"):
            return m.mapToSource(index)
        return index

    def createEditor(self, parent: QWidget, option, index: QModelIndex) -> QWidget:
        source_index = self._to_source(index)
        col_type = self._column_type(source_index.column())
        if col_type is datetime:
            edit = QDateTimeEdit(parent)
            edit.setDisplayFormat(self._DATETIME_FORMAT)
            edit.setCalendarPopup(True)
            return edit
        delegate_cls = _DELEGATE_FOR_TYPE.get(col_type, StrDelegate)
        return delegate_cls(parent)

    def setEditorData(self, editor: QWidget, index: QModelIndex) -> None:
        source_index = self._to_source(index)
        col_type = self._column_type(source_index.column())
        if col_type is datetime:
            event = self._source_model._events[source_index.row()]
            value = event.start if source_index.column() == 0 else event.stop
            editor.setDateTime(QDateTime.fromSecsSinceEpoch(int(value.timestamp())))
            return
        if isinstance(editor, SettingDelegate):
            event = self._source_model._events[source_index.row()]
            key = self._source_model._meta_keys[source_index.column() - len(self._source_model._FIXED_COLUMNS)]
            editor.set_value(event.meta.get(key))

    def setModelData(self, editor: QWidget, model, index: QModelIndex) -> None:
        source_index = self._to_source(index)
        col_type = self._column_type(source_index.column())
        if col_type is datetime:
            qdt = editor.dateTime()
            value = datetime.fromtimestamp(qdt.toSecsSinceEpoch(), tz=timezone.utc)
            model.setData(index, value, Qt.ItemDataRole.EditRole)
            return
        if isinstance(editor, SettingDelegate):
            model.setData(index, editor.get_value(), Qt.ItemDataRole.EditRole)
