"""Annotation types for layer callbacks."""
import types as _types
from dataclasses import dataclass, field
from typing import Any, Optional, Union, get_args, get_origin


@dataclass(frozen=True)
class Marker:
    time: float
    value: float
    label: Optional[str] = None
    color: Optional[str] = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Span:
    start: float
    stop: float
    label: Optional[str] = None
    color: Optional[str] = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HLine:
    value: float
    label: Optional[str] = None
    color: Optional[str] = None
    meta: dict[str, Any] = field(default_factory=dict)


Annotation = Union[Marker, Span, HLine]

_TYPE_MAP = {Marker: "marker", Span: "span", HLine: "hline"}


def infer_annotation_type(items: list) -> Optional[str]:
    if not items:
        return None
    types = {type(item) for item in items}
    if len(types) == 1:
        return _TYPE_MAP.get(types.pop())
    return "mixed"


def infer_type_from_annotation(annotation) -> Optional[str]:
    if annotation is None:
        return None
    origin = get_origin(annotation)
    if origin is not list:
        return None
    args = get_args(annotation)
    if not args:
        return None
    inner = args[0]
    if inner in _TYPE_MAP:
        return _TYPE_MAP[inner]
    inner_origin = get_origin(inner)
    if inner_origin is Union or isinstance(inner, _types.UnionType):
        union_args = get_args(inner)
        mapped = {_TYPE_MAP.get(a) for a in union_args}
        mapped.discard(None)
        if len(mapped) > 1:
            return "mixed"
        if len(mapped) == 1:
            return mapped.pop()
    return None
