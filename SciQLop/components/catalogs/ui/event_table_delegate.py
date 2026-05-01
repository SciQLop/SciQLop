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
)
from SciQLop.core.knobs import (
    KnobSpec, IntKnob, FloatKnob, BoolKnob, ChoiceKnob, StringKnob,
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


def _editor_from_spec(spec: KnobSpec, parent: QWidget) -> SettingDelegate | None:
    """Build a SettingDelegate honoring the constraints in *spec*. Return None
    if the spec is not directly mappable (caller falls back to inference)."""
    # Reaches into private ._spin / ._combo on settings delegates: these are
    # stable intra-package handles used by the existing settings UI.
    if isinstance(spec, BoolKnob):
        return BoolDelegate(parent)
    if isinstance(spec, IntKnob):
        delegate = IntDelegate(parent)
        spin = delegate._spin
        if spec.min is not None:
            spin.setMinimum(spec.min)
        if spec.max is not None:
            spin.setMaximum(spec.max)
        if spec.step:
            spin.setSingleStep(spec.step)
        return delegate
    if isinstance(spec, FloatKnob):
        delegate = FloatDelegate(parent)
        spin = delegate._spin
        if spec.min is not None:
            spin.setMinimum(spec.min)
        if spec.max is not None:
            spin.setMaximum(spec.max)
        if spec.step:
            spin.setSingleStep(spec.step)
        return delegate
    if isinstance(spec, ChoiceKnob):
        delegate = ComboDelegate(parent=parent)
        combo = delegate._combo
        for label, value in spec.choices:
            combo.addItem(str(label), value)
        return delegate
    if isinstance(spec, StringKnob):
        return StrDelegate(parent)
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
        if isinstance(editor, SettingDelegate):
            event = self._source_model._events[source_index.row()]
            key = self._source_model._meta_keys[col - self._meta_offset()]
            editor.set_value(event.meta.get(key))

    def setModelData(self, editor: QWidget, model, index: QModelIndex) -> None:
        source_index = self._to_source(index)
        col = source_index.column()
        if col < self._meta_offset():
            qdt = editor.dateTime()
            value = datetime.fromtimestamp(qdt.toSecsSinceEpoch(), tz=timezone.utc)
            model.setData(index, value, Qt.ItemDataRole.EditRole)
            return
        if isinstance(editor, SettingDelegate):
            model.setData(index, editor.get_value(), Qt.ItemDataRole.EditRole)
