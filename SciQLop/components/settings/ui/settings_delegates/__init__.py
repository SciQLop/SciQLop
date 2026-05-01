from typing import Any, List, Type, Mapping, Callable, get_origin, get_args
import typing
from enum import Enum
from pydantic.fields import FieldInfo
from PySide6.QtCore import Signal
from PySide6.QtGui import QPalette
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QWidget, QLabel, QCheckBox, QLineEdit, QFrame,
    QSpinBox, QDoubleSpinBox, QComboBox, QCompleter,
    QHBoxLayout, QVBoxLayout,
    QToolButton, QFileDialog, QListWidget,
    QPushButton, QInputDialog,
)
from SciQLop.core.ui import Metrics, fit_combo_to_content

# ---------------------------------------------------------------------------
# Registry: maps type names to delegate classes
# ---------------------------------------------------------------------------

_type_delegates: dict[str, Type["SettingDelegate"]] = {}


def register_delegate(cls: type):
    """Register a delegate class for a Python type (keyed by type.__name__)."""
    def decorator(delegate: Type["SettingDelegate"]):
        _type_delegates[cls.__name__] = delegate
        return delegate
    return decorator


# ---------------------------------------------------------------------------
# Widget registry: maps widget hint strings to factory callables
# ---------------------------------------------------------------------------

_widget_factories: dict[str, Callable[..., "SettingDelegate"]] = {}


def register_widget(name: str):
    """Register a delegate factory under a widget hint name."""
    def decorator(factory: Callable[..., "SettingDelegate"]):
        _widget_factories[name] = factory
        return factory
    return decorator


# ---------------------------------------------------------------------------
# Base delegate
# ---------------------------------------------------------------------------

class SettingDelegate(QWidget):
    value_changed = Signal(object)

    def get_value(self) -> Any:
        raise NotImplementedError

    def set_value(self, value: Any) -> None:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Concrete delegates
# ---------------------------------------------------------------------------

@register_delegate(bool)
@register_widget("bool")
class BoolDelegate(SettingDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._cb = QCheckBox()
        layout.addWidget(self._cb)
        layout.addStretch()
        self._cb.toggled.connect(lambda v: self.value_changed.emit(v))

    def get_value(self) -> bool:
        return self._cb.isChecked()

    def set_value(self, value: Any) -> None:
        self._cb.blockSignals(True)
        self._cb.setChecked(bool(value))
        self._cb.blockSignals(False)


@register_delegate(str)
@register_widget("str")
class StrDelegate(SettingDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._edit = QLineEdit()
        layout.addWidget(self._edit)
        self._edit.textChanged.connect(lambda v: self.value_changed.emit(v))

    def get_value(self) -> str:
        return self._edit.text()

    def set_value(self, value: Any) -> None:
        self._edit.blockSignals(True)
        self._edit.setText(str(value) if value is not None else "")
        self._edit.blockSignals(False)


@register_widget("password")
class PasswordDelegate(SettingDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._edit = QLineEdit()
        self._edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self._edit)
        self._edit.textChanged.connect(lambda v: self.value_changed.emit(v))

    def get_value(self) -> str:
        return self._edit.text()

    def set_value(self, value: Any) -> None:
        self._edit.blockSignals(True)
        self._edit.setText(str(value) if value is not None else "")
        self._edit.blockSignals(False)


@register_delegate(int)
@register_widget("int")
class IntDelegate(SettingDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._spin = QSpinBox()
        self._spin.setRange(-(2 ** 31), 2 ** 31 - 1)
        self._spin.setMinimumWidth(Metrics.em(10))
        layout.addWidget(self._spin)
        layout.addStretch()
        self._spin.valueChanged.connect(lambda v: self.value_changed.emit(v))

    def get_value(self) -> int:
        return self._spin.value()

    def set_value(self, value: Any) -> None:
        self._spin.blockSignals(True)
        self._spin.setValue(int(value))
        self._spin.blockSignals(False)

    def set_range(self, minimum: int | None = None, maximum: int | None = None,
                  step: int | None = None) -> None:
        if minimum is not None:
            self._spin.setMinimum(minimum)
        if maximum is not None:
            self._spin.setMaximum(maximum)
        if step:
            self._spin.setSingleStep(step)


@register_delegate(float)
@register_widget("float")
class FloatDelegate(SettingDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._spin = QDoubleSpinBox()
        self._spin.setDecimals(6)
        self._spin.setRange(-1e18, 1e18)
        self._spin.setMinimumWidth(Metrics.em(14))
        layout.addWidget(self._spin)
        layout.addStretch()
        self._spin.valueChanged.connect(lambda v: self.value_changed.emit(v))

    def get_value(self) -> float:
        return self._spin.value()

    def set_value(self, value: Any) -> None:
        self._spin.blockSignals(True)
        self._spin.setValue(float(value))
        self._spin.blockSignals(False)

    def set_range(self, minimum: float | None = None, maximum: float | None = None,
                  step: float | None = None) -> None:
        if minimum is not None:
            self._spin.setMinimum(minimum)
        if maximum is not None:
            self._spin.setMaximum(maximum)
        if step:
            self._spin.setSingleStep(step)


@register_widget("combo")
class ComboDelegate(SettingDelegate):
    def __init__(self, choices: list = None, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._combo = QComboBox()
        for choice in (choices or []):
            self._combo.addItem(str(choice), choice)
        fit_combo_to_content(self._combo)
        layout.addWidget(self._combo)
        layout.addStretch()
        self._combo.currentIndexChanged.connect(
            lambda i: self.value_changed.emit(self._combo.itemData(i))
        )

    def get_value(self) -> Any:
        return self._combo.currentData()

    def set_value(self, value: Any) -> None:
        self._combo.blockSignals(True)
        for i in range(self._combo.count()):
            if self._combo.itemData(i) == value:
                self._combo.setCurrentIndex(i)
                break
        self._combo.blockSignals(False)

    def populate(self, choices) -> None:
        """Replace the combo's items. choices: iterable of (label, value)."""
        self._combo.blockSignals(True)
        try:
            self._combo.clear()
            for label, value in choices:
                self._combo.addItem(str(label), value)
        finally:
            self._combo.blockSignals(False)


@register_widget("path_dir")
class _PathDirFactory:
    """Convenience: returns a PathDelegate in 'dir' mode."""
    def __new__(cls, **_):
        return PathDelegate("dir")


@register_widget("path_file")
class _PathFileFactory:
    """Convenience: returns a PathDelegate in 'file' mode."""
    def __new__(cls, **_):
        return PathDelegate("file")


class PathDelegate(SettingDelegate):
    def __init__(self, mode: str = "dir", parent=None):
        super().__init__(parent)
        self._mode = mode
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._edit = QLineEdit()
        layout.addWidget(self._edit)
        self._btn = QToolButton()
        self._btn.setText("...")
        layout.addWidget(self._btn)
        self._edit.textChanged.connect(lambda v: self.value_changed.emit(v))
        self._btn.clicked.connect(self._browse)

    def _browse(self):
        current = self._edit.text()
        if self._mode == "dir":
            path = QFileDialog.getExistingDirectory(self, "Select Directory", current)
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Select File", current)
        if path:
            self._edit.setText(path)

    def get_value(self) -> str:
        return self._edit.text()

    def set_value(self, value: Any) -> None:
        self._edit.blockSignals(True)
        self._edit.setText(str(value) if value is not None else "")
        self._edit.blockSignals(False)


@register_widget("list_path")
class _ListPathFactory:
    """Convenience: returns a ListStrDelegate with browse_dirs=True."""
    def __new__(cls, **_):
        return ListStrDelegate(browse_dirs=True)


@register_widget("list_str")
class ListStrDelegate(SettingDelegate):
    def __init__(self, browse_dirs: bool = False, parent=None):
        super().__init__(parent)
        self._browse_dirs = browse_dirs
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self._list = QListWidget()
        self._list.setMinimumHeight(Metrics.ex(5))
        self._list.setMaximumHeight(Metrics.ex(10))
        layout.addWidget(self._list)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        self._add_btn = QPushButton("Add")
        self._remove_btn = QPushButton("Remove")
        btn_row.addWidget(self._add_btn)
        btn_row.addWidget(self._remove_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._add_btn.clicked.connect(self._add_item)
        self._remove_btn.clicked.connect(self._remove_item)

    def _add_item(self):
        if self._browse_dirs:
            path = QFileDialog.getExistingDirectory(self, "Select Directory")
            if path:
                self._list.addItem(path)
                self.value_changed.emit(self.get_value())
        else:
            text, ok = QInputDialog.getText(self, "Add Item", "Value:")
            if ok and text:
                self._list.addItem(text)
                self.value_changed.emit(self.get_value())

    def _remove_item(self):
        items = self._list.selectedItems()
        for item in items:
            self._list.takeItem(self._list.row(item))
        if items:
            self.value_changed.emit(self.get_value())

    def get_value(self) -> List[str]:
        return [self._list.item(i).text() for i in range(self._list.count())]

    def set_value(self, value: Any) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        if value:
            for item in value:
                self._list.addItem(str(item))
        self._list.blockSignals(False)


_TAG_CHIP_QSS = """
QFrame#TagChip {
    background-color: palette(alternate-base);
    border: 1px solid palette(mid);
    border-radius: 0.6ex;
}
QFrame#TagChip > QLabel {
    background: transparent;
    padding-left: 0.4ex;
}
QFrame#TagChip > QToolButton {
    background: transparent;
    border: none;
    color: palette(text);
    padding: 0 0.3ex;
}
QFrame#TagChip > QToolButton:hover {
    color: palette(highlight);
}
"""


class _TagChip(QFrame):
    """A single tag chip: label + close button."""
    removed = Signal(str)

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setObjectName("TagChip")
        # No StyledPanel frame — adjacent chips otherwise paint a doubled border.
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet(_TAG_CHIP_QSS)
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(),
                           self.sizePolicy().Policy.Maximum)
        self._text = text
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(QLabel(text))
        close_btn = QToolButton()
        close_btn.setText("×")
        close_btn.setAutoRaise(True)
        close_btn.clicked.connect(lambda: self.removed.emit(self._text))
        layout.addWidget(close_btn)


@register_widget("tag_list")
class TagListDelegate(SettingDelegate):
    """Inline chip/token editor for a list of short strings (tags).

    Type a tag and press Enter or comma to add it as a chip; click ✕ on a
    chip to remove it; Backspace on empty input removes the last chip.
    Suggestions (if provided) drive a QCompleter on the input.
    """

    def __init__(self, suggestions: list[str] | tuple[str, ...] | None = None,
                 parent=None):
        super().__init__(parent)
        self._tags: list[str] = []
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self._chips_layout = QHBoxLayout()
        self._chips_layout.setContentsMargins(0, 0, 0, 0)
        self._chips_layout.setSpacing(4)
        layout.addLayout(self._chips_layout)
        self._input = QLineEdit()
        self._input.setPlaceholderText("Add tag…")
        layout.addWidget(self._input, 1)
        if suggestions:
            self._input.setCompleter(QCompleter(list(suggestions), self._input))
        self._input.textChanged.connect(self._on_text_changed)
        self._input.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self._input and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                # Enter on non-empty input: commit the tag and stay in edit mode.
                # Enter on empty input: let the event propagate so Qt's editor
                # framework closes the cell editor (the user's "I'm done" signal).
                if self._input.text().strip():
                    self._commit_input()
                    return True
                return False
            if event.key() == Qt.Key.Key_Backspace and not self._input.text() and self._tags:
                self._remove_tag(self._tags[-1])
                return True
        return super().eventFilter(obj, event)

    def _on_text_changed(self, text: str) -> None:
        if text.endswith(","):
            self._input.blockSignals(True)
            self._input.setText(text[:-1])
            self._input.blockSignals(False)
            self._commit_input()

    def _commit_input(self) -> None:
        text = self._input.text().strip()
        if not text or text in self._tags:
            self._input.clear()
            return
        self._tags.append(text)
        self._add_chip(text)
        self._input.clear()
        self.value_changed.emit(self.get_value())

    def _add_chip(self, text: str) -> None:
        chip = _TagChip(text, self)
        chip.removed.connect(self._remove_tag)
        self._chips_layout.addWidget(chip)

    def _remove_tag(self, text: str) -> None:
        if text in self._tags:
            self._tags.remove(text)
        for i in range(self._chips_layout.count()):
            item = self._chips_layout.itemAt(i)
            w = item.widget() if item is not None else None
            if isinstance(w, _TagChip) and w._text == text:
                w.setParent(None)
                w.deleteLater()
                break
        self.value_changed.emit(self.get_value())

    def get_value(self) -> List[str]:
        return list(self._tags)

    def set_value(self, value: Any) -> None:
        while self._chips_layout.count():
            item = self._chips_layout.takeAt(0)
            w = item.widget() if item is not None else None
            if w is not None:
                w.deleteLater()
        self._tags = []
        if value:
            for tag in value:
                t = str(tag)
                if t and t not in self._tags:
                    self._tags.append(t)
                    self._add_chip(t)


@register_widget("plugins_dict")
class PluginsDictDelegate(SettingDelegate):
    """Shows each plugin as a checkbox row with name and description."""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        hint = QLabel("Changes take effect after restart.")
        hint.setObjectName("SettingDescription")
        hint_font = hint.font()
        hint_font.setPointSizeF(hint_font.pointSizeF() * 0.85)
        hint.setFont(hint_font)
        hint.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        layout.addWidget(hint)

        self._rows: dict[str, QCheckBox] = {}
        self._descriptions: dict[str, str] = {}
        self._inner_layout = layout
        self._load_plugin_descriptions()

    def _load_plugin_descriptions(self):
        from SciQLop.components.plugins.backend.loader.loader import plugins_folders, list_plugins, _discover_entry_point_plugins
        from SciQLop.components.plugins.backend.loader.plugin_desc import PluginDesc
        import os
        for folder in plugins_folders():
            for name in list_plugins(folder):
                try:
                    desc = PluginDesc.from_json(os.path.join(folder, name, "plugin.json"))
                    self._descriptions[name] = desc.description
                except Exception:
                    pass
        for name, ep in _discover_entry_point_plugins().items():
            if name not in self._descriptions:
                self._descriptions[name] = f"Installed package: {ep.value}"

    def _add_plugin_row(self, plugin_name: str, enabled: bool):
        desc = self._descriptions.get(plugin_name, "")
        label = plugin_name.replace('_', ' ').title()
        if desc:
            label = f"{label} — {desc}"
        cb = QCheckBox(label)
        cb.setChecked(enabled)
        cb.toggled.connect(lambda _: self.value_changed.emit(self.get_value()))
        self._rows[plugin_name] = cb
        self._inner_layout.addWidget(cb)

    def get_value(self) -> dict:
        from SciQLop.components.plugins.backend.settings import PluginConfig
        return {name: PluginConfig(enabled=cb.isChecked()) for name, cb in self._rows.items()}

    def set_value(self, value: Any) -> None:
        # Clear existing rows
        for cb in self._rows.values():
            cb.blockSignals(True)
            self._inner_layout.removeWidget(cb)
            cb.deleteLater()
        self._rows.clear()

        if not isinstance(value, dict):
            return
        for plugin_name, config in sorted(value.items()):
            enabled = config.enabled if hasattr(config, 'enabled') else True
            self._add_plugin_row(plugin_name, enabled)


class NotEditableDelegate(SettingDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel("not editable")
        lbl.setEnabled(False)
        layout.addWidget(lbl)

    def get_value(self) -> Any:
        return None

    def set_value(self, value: Any) -> None:
        pass


# ---------------------------------------------------------------------------
# Dispatch: field info → delegate instance
# ---------------------------------------------------------------------------

def is_field_editable(field_name: str, field_info: FieldInfo) -> bool:
    """Return True if the field has a real delegate (not NotEditableDelegate)."""
    extra = field_info.json_schema_extra or {}
    if not isinstance(extra, dict):
        extra = {}
    if extra.get("widget", ""):
        return True
    annotation = _unwrap_optional(field_info.annotation)
    if get_origin(annotation) is typing.Literal:
        return True
    try:
        if isinstance(annotation, type) and issubclass(annotation, Enum):
            return True
    except TypeError:
        pass
    if get_origin(annotation) is list:
        return True
    if hasattr(annotation, "__name__") and annotation.__name__ in _type_delegates:
        return True
    return False

def _unwrap_optional(annotation):
    """Unwrap Optional[X] to X."""
    if get_origin(annotation) is typing.Union:
        inner = [a for a in get_args(annotation) if a is not type(None)]
        if len(inner) == 1:
            return inner[0]
    return annotation


def get_delegate_for_field(field_name: str, field_info: FieldInfo) -> SettingDelegate:
    extra = field_info.json_schema_extra or {}
    if not isinstance(extra, dict):
        extra = {}

    # 1. Explicit widget hint — highest priority
    widget = extra.get("widget", "")
    if widget:
        choices = extra.get("choices")
        factory = _widget_factories.get(widget)
        if factory is not None:
            if choices is not None:
                return factory(choices=choices)
            return factory()

    # 2. Type-based resolution
    annotation = _unwrap_optional(field_info.annotation)

    # Literal → combo
    if get_origin(annotation) is typing.Literal:
        return ComboDelegate(list(get_args(annotation)))

    # Enum → combo
    try:
        if isinstance(annotation, type) and issubclass(annotation, Enum):
            return ComboDelegate([e.value for e in annotation])
    except TypeError:
        pass

    # List[str] → list_str
    if get_origin(annotation) is list:
        args = get_args(annotation)
        if args and args[0] is str:
            return ListStrDelegate()
        return ListStrDelegate()

    # Registry lookup by type name (handles bool, int, float, str)
    if hasattr(annotation, "__name__"):
        delegate_cls = _type_delegates.get(annotation.__name__)
        if delegate_cls is not None:
            return delegate_cls()

    return NotEditableDelegate()
