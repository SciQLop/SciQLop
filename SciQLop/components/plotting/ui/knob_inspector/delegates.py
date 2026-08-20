from typing import Any

from PySide6.QtCore import QRegularExpression, Signal
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtCore import QDateTime, Qt
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox, QLineEdit, QLabel,
    QSlider, QDateTimeEdit,
)

from SciQLop.user_api.knobs import (
    KnobSpec, IntKnob, FloatKnob, BoolKnob, ChoiceKnob, StringKnob, StringListKnob,
    DatetimeKnob, TimeRangeKnob, ThresholdKnob,
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


class _TimeRangeDelegate(KnobDelegate):
    def __init__(self, spec: TimeRangeKnob, parent=None):
        super().__init__(spec, parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel("(set on plot)")
        self._value = spec.default
        layout.addWidget(self._label)

    def get_value(self):
        return self._value

    def set_value(self, value):
        from SciQLopPlots import SciQLopPlotRange
        if isinstance(value, SciQLopPlotRange):
            self._value = value
            self._label.setText(f"{value.start():.1f} – {value.stop():.1f}")


class _ThresholdDelegate(KnobDelegate):
    def __init__(self, spec: ThresholdKnob, parent=None):
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


class _SliderDelegate(KnobDelegate):
    """Slider beside a spin box, for a spec that asked for ``widget="slider"``.

    A slider needs both bounds to mean anything, so \ref delegate_for_spec only
    picks this when the spec has them. QSlider is integer-only; a float knob is
    therefore mapped onto a fixed number of steps between the bounds.
    """

    _STEPS = 1000

    def __init__(self, spec: KnobSpec, parent=None):
        super().__init__(spec, parent)
        self._is_int = isinstance(spec, IntKnob)
        self._min, self._max = float(spec.min), float(spec.max)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._slider = QSlider(Qt.Horizontal)
        if self._is_int:
            self._slider.setRange(int(self._min), int(self._max))
            self._slider.setSingleStep(int(spec.step) if spec.step else 1)
            self._spin = QSpinBox()
            self._spin.setRange(int(self._min), int(self._max))
        else:
            self._slider.setRange(0, self._STEPS)
            self._spin = QDoubleSpinBox()
            self._spin.setDecimals(6)
            self._spin.setRange(self._min, self._max)
        if spec.step:
            self._spin.setSingleStep(spec.step)
        layout.addWidget(self._slider, 1)
        layout.addWidget(self._spin)

        self._slider.valueChanged.connect(self._from_slider)
        self._spin.valueChanged.connect(self._from_spin)

    def _to_slider(self, value: float) -> int:
        if self._is_int:
            return int(round(value))
        if self._max == self._min:
            return 0
        return int(round((value - self._min) / (self._max - self._min) * self._STEPS))

    def _from_slider_value(self, pos: int) -> float:
        if self._is_int:
            return int(pos)
        return self._min + (pos / self._STEPS) * (self._max - self._min)

    def _from_slider(self, pos: int):
        value = self._from_slider_value(pos)
        self._spin.blockSignals(True)
        self._spin.setValue(value)
        self._spin.blockSignals(False)
        self.value_changed.emit(self.get_value())

    def _from_spin(self, value):
        self._slider.blockSignals(True)
        self._slider.setValue(self._to_slider(float(value)))
        self._slider.blockSignals(False)
        self.value_changed.emit(self.get_value())

    def get_value(self):
        return self._spin.value()

    def set_value(self, value):
        for w in (self._slider, self._spin):
            w.blockSignals(True)
        self._spin.setValue(int(value) if self._is_int else float(value))
        self._slider.setValue(self._to_slider(float(value)))
        for w in (self._slider, self._spin):
            w.blockSignals(False)


class _StringListDelegate(KnobDelegate):
    """Comma-separated list. Without this the inspector raised on the spec."""

    def __init__(self, spec: StringListKnob, parent=None):
        super().__init__(spec, parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._edit = QLineEdit()
        self._edit.setPlaceholderText("comma-separated")
        layout.addWidget(self._edit)
        self._edit.editingFinished.connect(
            lambda: self.value_changed.emit(self.get_value()))

    def get_value(self):
        return [p.strip() for p in self._edit.text().split(",") if p.strip()]

    def set_value(self, value):
        self._edit.blockSignals(True)
        self._edit.setText(", ".join(value or []))
        self._edit.blockSignals(False)


class _DatetimeDelegate(KnobDelegate):
    """UTC instant. Without this the inspector raised on the spec."""

    def __init__(self, spec: DatetimeKnob, parent=None):
        super().__init__(spec, parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._edit = QDateTimeEdit()
        self._edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self._edit.setTimeSpec(Qt.TimeSpec.UTC)
        layout.addWidget(self._edit)
        self._edit.dateTimeChanged.connect(
            lambda: self.value_changed.emit(self.get_value()))

    def get_value(self):
        return self._edit.dateTime().toSecsSinceEpoch()

    def set_value(self, value):
        self._edit.blockSignals(True)
        if hasattr(value, "timestamp"):
            value = value.timestamp()
        self._edit.setDateTime(QDateTime.fromSecsSinceEpoch(int(value or 0)))
        self._edit.blockSignals(False)


_DELEGATES = {
    IntKnob: _IntDelegate,
    FloatKnob: _FloatDelegate,
    BoolKnob: _BoolDelegate,
    ChoiceKnob: _ChoiceDelegate,
    StringKnob: _StringDelegate,
    TimeRangeKnob: _TimeRangeDelegate,
    ThresholdKnob: _ThresholdDelegate,
    StringListKnob: _StringListDelegate,
    DatetimeKnob: _DatetimeDelegate,
}


def delegate_for_spec(spec: KnobSpec, parent=None) -> KnobDelegate:
    # A spec can ask for a particular control, which used to be ignored: the
    # widget was chosen from the spec's type alone, so `widget="slider"` still
    # got a bare spin box. A slider needs both bounds to mean anything.
    if (getattr(spec, "widget", "") == "slider"
            and getattr(spec, "min", None) is not None
            and getattr(spec, "max", None) is not None):
        return _SliderDelegate(spec, parent)
    cls = _DELEGATES.get(type(spec))
    if cls is None:
        raise TypeError(f"No delegate for {type(spec).__name__}")
    return cls(spec, parent)
