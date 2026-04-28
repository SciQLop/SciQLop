"""Layer lifecycle: MutableCallback wrapper and registry for hot-reload."""
import functools
import inspect
from dataclasses import dataclass
from typing import Callable, Dict, Optional


def _signature_kwargs(callback) -> tuple:
    sig = inspect.signature(callback)
    return tuple(
        (name, p.default.__class__)
        for name, p in sig.parameters.items()
        if p.default is not inspect.Parameter.empty and name not in ("start", "stop", "data")
    )


class MutableCallback:
    def __init__(self, callback: Callable):
        self.callback = callback

    @property
    def callback(self):
        return self._callback

    @callback.setter
    def callback(self, value):
        self._callback = value
        functools.update_wrapper(self, value)

    def __call__(self, *args, **kwargs):
        return self._callback(*args, **kwargs)


@dataclass
class LayerEntry:
    wrapper: MutableCallback
    signature_changed: bool = False


class LayerRegistry:
    def __init__(self):
        self._entries: Dict[str, LayerEntry] = {}

    def register(self, name: str, callback: Callable) -> LayerEntry:
        existing = self._entries.get(name)
        new_sig = _signature_kwargs(callback)
        if existing is not None:
            old_sig = _signature_kwargs(existing.wrapper.callback)
            if old_sig == new_sig:
                existing.wrapper.callback = callback
                existing.signature_changed = False
                return existing

        wrapper = MutableCallback(callback)
        entry = LayerEntry(wrapper=wrapper, signature_changed=existing is not None)
        self._entries[name] = entry
        return entry

    def get(self, name: str) -> Optional[LayerEntry]:
        return self._entries.get(name)


_registry = LayerRegistry()
