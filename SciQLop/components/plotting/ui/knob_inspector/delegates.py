from typing import Any

from PySide6.QtCore import QRegularExpression, Signal
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox, QLineEdit,
)

from SciQLop.user_api.knobs import (
    KnobSpec, IntKnob, FloatKnob, BoolKnob, ChoiceKnob, StringKnob,
)


class KnobDelegate(QWidget):
    value_changed = Signal(object)

    def __init__(self, spec: KnobSpec, parent=None):
        super().__init__(parent)
        self.spec = spec

    def get_value(self) -> Any:
        raise NotImplementedError

    def set_value(self, value: Any) -> None:
        raise NotImplementedError


class _IntDelegate(KnobDelegate):
    def __init__(self, spec: IntKnob, parent=None):
        super().__init__(spec, parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._spin = QSpinBox()
        if spec.min is not None:
            self._spin.setMinimum(spec.min)
        else:
            self._spin.setMinimum(-(2 ** 31))
        if spec.max is not None:
            self._spin.setMaximum(spec.max)
        else:
            self._spin.setMaximum(2 ** 31 - 1)
        if spec.step:
            self._spin.setSingleStep(spec.step)
        layout.addWidget(self._spin)
        self._spin.valueChanged.connect(self.value_changed.emit)

    def get_value(self):
        return self._spin.value()

    def set_value(self, value):
        self._spin.blockSignals(True)
        self._spin.setValue(int(value))
        self._spin.blockSignals(False)


class _FloatDelegate(KnobDelegate):
    def __init__(self, spec: FloatKnob, parent=None):
        super().__init__(spec, parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._spin = QDoubleSpinBox()
        self._spin.setDecimals(6)
        if spec.min is not None:
            self._spin.setMinimum(spec.min)
        else:
            self._spin.setMinimum(-1e18)
        if spec.max is not None:
            self._spin.setMaximum(spec.max)
        else:
            self._spin.setMaximum(1e18)
        if spec.step:
            self._spin.setSingleStep(spec.step)
        layout.addWidget(self._spin)
        self._spin.valueChanged.connect(self.value_changed.emit)

    def get_value(self):
        return self._spin.value()

    def set_value(self, value):
        self._spin.blockSignals(True)
        self._spin.setValue(float(value))
        self._spin.blockSignals(False)


class _BoolDelegate(KnobDelegate):
    def __init__(self, spec: BoolKnob, parent=None):
        super().__init__(spec, parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._cb = QCheckBox()
        layout.addWidget(self._cb)
        layout.addStretch()
        self._cb.toggled.connect(self.value_changed.emit)

    def get_value(self):
        return self._cb.isChecked()

    def set_value(self, value):
        self._cb.blockSignals(True)
        self._cb.setChecked(bool(value))
        self._cb.blockSignals(False)


class _ChoiceDelegate(KnobDelegate):
    def __init__(self, spec: ChoiceKnob, parent=None):
        super().__init__(spec, parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._combo = QComboBox()
        for label, value in spec.choices:
            self._combo.addItem(label, value)
        layout.addWidget(self._combo)
        self._combo.currentIndexChanged.connect(
            lambda i: self.value_changed.emit(self._combo.itemData(i))
        )

    def get_value(self):
        return self._combo.currentData()

    def set_value(self, value):
        self._combo.blockSignals(True)
        for i in range(self._combo.count()):
            if self._combo.itemData(i) == value:
                self._combo.setCurrentIndex(i)
                break
        self._combo.blockSignals(False)


class _StringDelegate(KnobDelegate):
    def __init__(self, spec: StringKnob, parent=None):
        super().__init__(spec, parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._edit = QLineEdit()
        if spec.pattern:
            self._edit.setValidator(
                QRegularExpressionValidator(QRegularExpression(spec.pattern), self._edit)
            )
        layout.addWidget(self._edit)
        self._edit.textChanged.connect(self.value_changed.emit)

    def get_value(self):
        return self._edit.text()

    def set_value(self, value):
        self._edit.blockSignals(True)
        self._edit.setText(str(value))
        self._edit.blockSignals(False)


_DELEGATES = {
    IntKnob: _IntDelegate,
    FloatKnob: _FloatDelegate,
    BoolKnob: _BoolDelegate,
    ChoiceKnob: _ChoiceDelegate,
    StringKnob: _StringDelegate,
}


def delegate_for_spec(spec: KnobSpec, parent=None) -> KnobDelegate:
    cls = _DELEGATES.get(type(spec))
    if cls is None:
        raise TypeError(f"No delegate for {type(spec).__name__}")
    return cls(spec, parent)
