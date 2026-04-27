from typing import Optional

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QPushButton, QHBoxLayout,
)

from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
from SciQLop.components.plotting.ui.knob_inspector.delegates import (
    KnobDelegate, delegate_for_spec,
)


class KnobsSection(QWidget):
    def __init__(self, state: GraphKnobState, debounce_ms: int = 400, parent=None):
        super().__init__(parent)
        self._state = state
        self._debounce_ms = debounce_ms
        self._widgets: dict[str, KnobDelegate] = {}
        self._timers: dict[str, QTimer] = {}
        self._pending: dict[str, object] = {}
        self._suppress_state_signal = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(form)

        for spec in state.specs:
            w = delegate_for_spec(spec, parent=self)
            w.set_value(state.values[spec.name])
            label = spec.label or spec.name
            if spec.unit:
                label = f"{label} [{spec.unit}]"
            form.addRow(label, w)
            if spec.description:
                w.setToolTip(spec.description)
            w.value_changed.connect(lambda v, n=spec.name: self._on_widget_changed(n, v))
            self._widgets[spec.name] = w

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._apply_btn = QPushButton("Apply")
        self._apply_btn.setVisible(any(s.apply == "manual" for s in state.specs))
        self._apply_btn.clicked.connect(self.apply_manual)
        btn_row.addWidget(self._apply_btn)
        self._reset_btn = QPushButton("⟳")
        self._reset_btn.setToolTip("Reset all parameters to defaults")
        self._reset_btn.clicked.connect(self.reset_to_defaults)
        btn_row.addWidget(self._reset_btn)
        outer.addLayout(btn_row)

        state.knobs_changed.connect(self._on_state_changed)

    def widget_for(self, name: str) -> Optional[KnobDelegate]:
        return self._widgets.get(name)

    def reset_to_defaults(self):
        defaults = {s.name: s.default for s in self._state.specs}
        for name, value in defaults.items():
            w = self._widgets[name]
            w.set_value(value)
            w.value_changed.emit(value)

    def apply_manual(self):
        for name, value in list(self._pending.items()):
            spec = next(s for s in self._state.specs if s.name == name)
            if spec.apply == "manual":
                self._commit(name, value)

    def _on_widget_changed(self, name: str, value):
        spec = next(s for s in self._state.specs if s.name == name)
        if spec.apply == "manual":
            self._pending[name] = value
            return
        self._pending[name] = value
        timer = self._timers.get(name)
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda n=name: self._commit_pending(n))
            self._timers[name] = timer
        timer.start(self._debounce_ms)

    def _commit_pending(self, name: str):
        if name not in self._pending:
            return
        self._commit(name, self._pending.pop(name))

    def _commit(self, name: str, value):
        try:
            self._suppress_state_signal = True
            self._state.set_value(name, value)
        except (ValueError, TypeError, KeyError):
            w = self._widgets.get(name)
            if w is not None:
                w.set_value(self._state.values.get(name))
        finally:
            self._suppress_state_signal = False

    def _on_state_changed(self, values: dict):
        if self._suppress_state_signal:
            return
        for name, value in values.items():
            w = self._widgets.get(name)
            if w is not None and w.get_value() != value:
                w.set_value(value)
