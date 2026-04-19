from typing import Iterable

from PySide6.QtCore import QObject, Signal

from SciQLop.user_api.knobs import (
    KnobSpec, coerce_value, validate_dict, defaults_for, canonical_hash,
)


class GraphKnobState(QObject):
    knobs_changed = Signal(dict)

    def __init__(self, specs: Iterable[KnobSpec], parent=None):
        super().__init__(parent)
        self._specs = list(specs)
        self._values = defaults_for(self._specs)

    @property
    def specs(self) -> list[KnobSpec]:
        return list(self._specs)

    @property
    def values(self) -> dict:
        return dict(self._values)

    def set_value(self, name: str, value):
        spec = next((s for s in self._specs if s.name == name), None)
        if spec is None:
            raise KeyError(name)
        coerced = coerce_value(spec, value)
        if self._values.get(name) == coerced:
            return
        self._values[name] = coerced
        self.knobs_changed.emit(dict(self._values))

    def set_all(self, values: dict):
        new = validate_dict(self._specs, values)
        if new == self._values:
            return
        self._values = new
        self.knobs_changed.emit(dict(self._values))

    def replace_specs(self, specs: Iterable[KnobSpec]):
        self._specs = list(specs)
        self._values = validate_dict(self._specs, self._values)
        self.knobs_changed.emit(dict(self._values))

    def cache_key(self) -> str:
        return canonical_hash(self._values)
