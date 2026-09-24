"""Shared data type annotations for virtual products and layers.

These classes serve double duty:
- As **type hints** in callback signatures (``data: Vector``)
- As **data containers** passed to layer callbacks at runtime (``.time``, ``.values``)

Import from here, from ``SciQLop.user_api.virtual_products.types``,
or from ``SciQLop.user_api.layers`` — they all resolve to these classes.
"""
import dataclasses
import numpy as np
from dataclasses import dataclass
from typing import Any, Optional, List


@dataclass(frozen=True)
class VPTypeInfo:
    product_type: str  # "scalar", "vector", "multicomponent", "spectrogram"
    labels: Optional[List[str]]
    colored: bool = False


class _DataType:
    """Base for data type annotations that also hold graph data at runtime."""
    _product_type: str = ""
    time: np.ndarray
    values: np.ndarray

    def __init_subclass__(cls, product_type: str = "", **kwargs):
        super().__init_subclass__(**kwargs)
        cls._product_type = product_type

    def __init__(self, time: np.ndarray, values: np.ndarray):
        self.time = time
        self.values = values

    def __len__(self):
        return len(self.time)

    def __class_getitem__(cls, labels):
        if not isinstance(labels, tuple):
            labels = (labels,)
        return _DataTypeWithLabels(cls._product_type, list(labels))


class _DataTypeWithLabels:
    def __init__(self, product_type: str, labels: List[str]):
        self.product_type = product_type
        self.labels = labels


class Scalar(_DataType, product_type="scalar"):
    pass


class Vector(_DataType, product_type="vector"):
    pass


class MultiComponent(_DataType, product_type="multicomponent"):
    pass


class Spectrogram(_DataType, product_type="spectrogram"):
    pass


@dataclass(frozen=True)
class _ColoredAnnotation:
    inner: Any


@dataclass(frozen=True)
class Colored:
    """A VP result coloured point by point: ``return Colored(data, color=c)``.

    ``data`` is anything the inner type accepts (SpeasyVariable or ``(t, values)``);
    ``color`` has one value per time sample. Annotate with ``-> Colored[Vector[...]]``.
    """
    data: Any
    color: Any

    def __class_getitem__(cls, inner):
        if inner is Spectrogram or getattr(inner, "product_type", None) == "spectrogram":
            raise TypeError("Colored[Spectrogram] is not supported: a spectrogram already has a colour axis")
        return _ColoredAnnotation(inner)

    def checked(self) -> "Colored":
        """The colour as float64, one value per sample, sorted by time together with the data.

        SciQLop sorts unsorted data by time; the colour has to follow or it lands on the
        wrong points. Raises ValueError when the colour does not match the samples.
        """
        if self.data is None:
            return self
        t = _time_of(self.data)
        color = _as_color_values(self.color, len(t))
        order = np.argsort(t, kind="stable")
        if np.array_equal(order, np.arange(len(t))):
            return Colored(self.data, color)
        return Colored(_take(self.data, order), color[order])


def _time_of(data) -> np.ndarray:
    return np.asarray(data.time if hasattr(data, "time") else data[0])


def _take(data, order: np.ndarray):
    if hasattr(data, "time"):
        return data[order]
    return tuple(np.asarray(a)[order] for a in data)


def _as_color_values(color, n: int) -> np.ndarray:
    values = np.squeeze(np.asarray(color))
    if np.issubdtype(values.dtype, np.datetime64):
        values = values.astype("datetime64[ns]").astype(np.int64) / 1e9
    if values.ndim != 1 or len(values) != n:
        raise ValueError(f"expected one colour value per time sample ({n}), got shape {np.shape(color)}")
    return np.ascontiguousarray(values, dtype=np.float64)


def extract_vp_type_info(annotation) -> Optional[VPTypeInfo]:
    if annotation is None:
        return None
    if isinstance(annotation, _ColoredAnnotation):
        inner = extract_vp_type_info(annotation.inner)
        return dataclasses.replace(inner, colored=True) if inner is not None else None
    if isinstance(annotation, _DataTypeWithLabels):
        return VPTypeInfo(product_type=annotation.product_type, labels=annotation.labels)
    if isinstance(annotation, type) and issubclass(annotation, _DataType):
        return VPTypeInfo(product_type=annotation._product_type, labels=None)
    return None


def wrap_graph_data(raw_data, data_type_cls: type) -> Optional[_DataType]:
    """Wrap raw graph.data() output into a typed data container."""
    if raw_data is None or len(raw_data) < 2:
        return None
    time = np.asarray(raw_data[0])
    values = np.asarray(raw_data[1])
    return data_type_cls(time=time, values=values)


_PRODUCT_TYPE_TO_CLASS = {
    "scalar": Scalar,
    "vector": Vector,
    "multicomponent": MultiComponent,
    "spectrogram": Spectrogram,
    "any": _DataType,
}


def data_class_for_product_type(product_type: str) -> type:
    return _PRODUCT_TYPE_TO_CLASS.get(product_type, _DataType)
