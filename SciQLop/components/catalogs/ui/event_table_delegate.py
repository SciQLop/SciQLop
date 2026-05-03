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
    ComboDelegate,
    TagListDelegate,
)
from SciQLop.core.knobs import (
    KnobSpec, IntKnob, FloatKnob, BoolKnob, ChoiceKnob, StringKnob,
    StringListKnob, DatetimeKnob,
)


def _qdatetime_from_iso(value: Any) -> QDateTime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    qdt = QDateTime.fromSecsSinceEpoch(int(dt.timestamp()))
    qdt.setTimeSpec(Qt.TimeSpec.UTC)
    return qdt


def _iso_from_qdatetime(qdt: QDateTime) -> str:
    secs = qdt.toSecsSinceEpoch()
    return datetime.fromtimestamp(secs, tz=timezone.utc).isoformat()


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
    if types <= {list, tuple, set}:
        return list
    return str


_DELEGATE_FOR_TYPE = {
    bool: BoolDelegate,
    int: IntDelegate,
    float: FloatDelegate,
    str: StrDelegate,
    list: TagListDelegate,
}


def _editor_from_spec(spec: KnobSpec, parent: QWidget) -> QWidget | None:
    """Build an editor honoring the constraints in *spec*. Return None
    if the spec is not directly mappable (caller falls back to inference).

    DatetimeKnob returns a plain QDateTimeEdit (handled out-of-band by the
    delegate's spec-aware setEditorData/setModelData branches); all other
    specs return SettingDelegate subclasses."""
    if isinstance(spec, DatetimeKnob):
        edit = QDateTimeEdit(parent)
        edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        edit.setCalendarPopup(True)
        return edit
    if isinstance(spec, BoolKnob):
        return BoolDelegate(parent)
    if isinstance(spec, IntKnob):
        delegate = IntDelegate(parent)
        delegate.set_range(spec.min, spec.max, spec.step)
        return delegate
    if isinstance(spec, FloatKnob):
        delegate = FloatDelegate(parent)
        delegate.set_range(spec.min, spec.max, spec.step)
        return delegate
    if isinstance(spec, ChoiceKnob):
        delegate = ComboDelegate(parent=parent)
        delegate.populate(spec.choices)
        delegate._choice_values = [v for _, v in spec.choices]  # for unknown-value path
        return delegate
    if isinstance(spec, StringKnob):
        delegate = StrDelegate(parent)
        if spec.pattern:
            from PySide6.QtCore import QRegularExpression
            from PySide6.QtGui import QRegularExpressionValidator
            delegate._edit.setValidator(QRegularExpressionValidator(QRegularExpression(spec.pattern)))
        return delegate
    if isinstance(spec, StringListKnob):
        return TagListDelegate(suggestions=spec.suggestions, parent=parent)
    return None


class EventTableDelegate(QStyledItemDelegate):
    """Pick an editor per cell, preferring provider.attribute_spec over inference."""

    _DATETIME_FORMAT = "yyyy-MM-dd HH:mm:ss"

    def __init__(self, source_model, parent=None):
        super().__init__(parent)
        self._source_model = source_model
        self._column_types: dict[int, type] = {}
        self._column_specs: dict[int, KnobSpec | None] = {}
        source_model.modelReset.connect(self._invalidate_caches)
        source_model.columnsInserted.connect(lambda *_: self._invalidate_caches())

    def _invalidate_caches(self) -> None:
        self._column_types.clear()
        self._column_specs.clear()

    def _meta_offset(self) -> int:
        return len(self._source_model._FIXED_COLUMNS)

    def _column_spec(self, source_col: int) -> KnobSpec | None:
        if source_col in self._column_specs:
            return self._column_specs[source_col]
        meta_offset = self._meta_offset()
        if source_col < meta_offset:
            spec = None
        else:
            provider = self._source_model._provider
            catalog = self._source_model._catalog
            if provider is None or catalog is None:
                spec = None
            else:
                key = self._source_model._meta_keys[source_col - meta_offset]
                spec = provider.attribute_spec(catalog, key)
        self._column_specs[source_col] = spec
        return spec

    def _column_type(self, source_col: int) -> type:
        if source_col in self._column_types:
            return self._column_types[source_col]
        meta_offset = self._meta_offset()
        if source_col < meta_offset:
            t: type = datetime
        else:
            key = self._source_model._meta_keys[source_col - meta_offset]
            sample = self._source_model._events[:100]
            values = [e.meta.get(key) for e in sample]
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
        col = source_index.column()

        if col < self._meta_offset():
            edit = QDateTimeEdit(parent)
            edit.setDisplayFormat(self._DATETIME_FORMAT)
            edit.setCalendarPopup(True)
            return edit

        spec = self._column_spec(col)
        if spec is not None:
            editor = _editor_from_spec(spec, parent)
            if editor is not None:
                return editor

        col_type = self._column_type(col)
        delegate_cls = _DELEGATE_FOR_TYPE.get(col_type, StrDelegate)
        return delegate_cls(parent)

    def setEditorData(self, editor: QWidget, index: QModelIndex) -> None:
        source_index = self._to_source(index)
        col = source_index.column()
        if col < self._meta_offset():
            event = self._source_model._events[source_index.row()]
            value = event.start if col == 0 else event.stop
            editor.setDateTime(QDateTime.fromSecsSinceEpoch(int(value.timestamp())))
            return
        spec = self._column_spec(col)
        if isinstance(spec, DatetimeKnob):
            event = self._source_model._events[source_index.row()]
            key = self._source_model._meta_keys[col - self._meta_offset()]
            value = event.meta.get(key)
            qdt = _qdatetime_from_iso(value) or QDateTime.currentDateTimeUtc()
            editor.setDateTime(qdt)
            return
        if isinstance(editor, SettingDelegate):
            event = self._source_model._events[source_index.row()]
            key = self._source_model._meta_keys[col - self._meta_offset()]
            value = event.meta.get(key)
            if value is None or value == "":
                value = self._fallback_for(col)
            choice_values = getattr(editor, "_choice_values", None)
            if choice_values is not None and value not in choice_values:
                from PySide6.QtCore import Qt as _Qt
                combo = editor._combo
                combo.addItem(f"(unknown: {value})", value)
                idx_unknown = combo.count() - 1
                combo.model().item(idx_unknown).setFlags(_Qt.ItemFlag.NoItemFlags)
                combo.setCurrentIndex(idx_unknown)
                return
            editor.set_value(value)

    def _fallback_for(self, source_col: int):
        """Pick a safe initial value when the cell is empty / None."""
        spec = self._column_spec(source_col)
        if spec is not None and hasattr(spec, "default"):
            default = getattr(spec, "default")
            if default is not None:
                return list(default) if isinstance(spec, StringListKnob) else default
        col_type = self._column_type(source_col)
        if col_type is bool:
            return False
        if col_type is int:
            return 0
        if col_type is float:
            return 0.0
        if col_type is list:
            return []
        return ""

    def setModelData(self, editor: QWidget, model, index: QModelIndex) -> None:
        source_index = self._to_source(index)
        col = source_index.column()
        if col < self._meta_offset():
            qdt = editor.dateTime()
            value = datetime.fromtimestamp(qdt.toSecsSinceEpoch(), tz=timezone.utc)
            model.setData(index, value, Qt.ItemDataRole.EditRole)
            return
        spec = self._column_spec(col)
        if isinstance(spec, DatetimeKnob):
            qdt = editor.dateTime()
            value = _iso_from_qdatetime(qdt)
            model.setData(index, value, Qt.ItemDataRole.EditRole)
            return
        if isinstance(editor, SettingDelegate):
            model.setData(index, editor.get_value(), Qt.ItemDataRole.EditRole)
