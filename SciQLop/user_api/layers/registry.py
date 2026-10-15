"""Hot-reload building blocks shared by layers and virtual products: a swappable callback wrapper
and the knob signature that decides whether a re-run can swap the body in place."""
import functools
import inspect
from typing import Callable


def signature_kwargs(callback, skip: tuple = ("start", "stop", "data")) -> tuple:
    sig = inspect.signature(callback)
    return tuple(
        (name, p.default.__class__)
        for name, p in sig.parameters.items()
        if p.default is not inspect.Parameter.empty and name not in skip
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
