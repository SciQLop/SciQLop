from typing import Dict, Callable, Any, Optional, Protocol, List, Type, Mapping
from PySide6.QtCore import QObject, Signal, Slot, Property
from PySide6.QtWidgets import QWidget, QFormLayout, QLabel

__delegate_classes__: Mapping[str, Type[QWidget]] = {}


def register_delegate(cls: type):
    def _(delegate: Type[QWidget]):
        __delegate_classes__[cls.__name__] = delegate
        return delegate

    return _


def delegate_for(obj: QObject) -> Optional[Type[QWidget]]:
    def inner_delegate_for(cls: type) -> Optional[Type[QWidget]]:
        delegate = __delegate_classes__.get(cls.__name__, None)
        if delegate is None and cls.__base__ is not None:
            return inner_delegate_for(cls.__base__)
        else:
            return delegate

    return inner_delegate_for(type(obj))
