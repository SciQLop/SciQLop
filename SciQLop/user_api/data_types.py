"""Shared data type annotations for virtual products and layers.

These classes serve double duty:
- As **type hints** in callback signatures (``data: Vector``)
- As **data containers** passed to layer callbacks at runtime (``.time``, ``.values``)

Import from here, from ``SciQLop.user_api.virtual_products.types``,
or from ``SciQLop.user_api.layers`` — they all resolve to these classes.
"""
import numpy as np
from dataclasses import dataclass
from typing import Optional, List


@dataclass(frozen=True)
class VPTypeInfo:
    product_type: str  # "scalar", "vector", "multicomponent", "spectrogram"
    labels: Optional[List[str]]


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


def extract_vp_type_info(annotation) -> Optional[VPTypeInfo]:
    if annotation is None:
        return None
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
