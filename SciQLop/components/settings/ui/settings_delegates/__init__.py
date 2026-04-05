from typing import Any, List, Type, Mapping, Callable, get_origin, get_args
import typing
from enum import Enum
from pydantic.fields import FieldInfo
from PySide6.QtCore import Signal
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QWidget, QLabel, QCheckBox, QLineEdit,
    QSpinBox, QDoubleSpinBox, QComboBox,
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
