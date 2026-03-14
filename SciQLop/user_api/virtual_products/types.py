from dataclasses import dataclass
from typing import Optional, List


@dataclass(frozen=True)
class VPTypeInfo:
    product_type: str  # "scalar", "vector", "multicomponent", "spectrogram"
    labels: Optional[List[str]]


class _VPType:
    _product_type: str

    def __init_subclass__(cls, product_type: str = "", **kwargs):
        super().__init_subclass__(**kwargs)
        cls._product_type = product_type

    def __class_getitem__(cls, labels):
        if not isinstance(labels, tuple):
            labels = (labels,)
        return _VPTypeWithLabels(cls._product_type, list(labels))


class _VPTypeWithLabels:
    def __init__(self, product_type: str, labels: List[str]):
        self.product_type = product_type
        self.labels = labels


class Scalar(_VPType, product_type="scalar"):
    pass


class Vector(_VPType, product_type="vector"):
    pass


class MultiComponent(_VPType, product_type="multicomponent"):
    pass


class Spectrogram(_VPType, product_type="spectrogram"):
    pass


def extract_vp_type_info(annotation) -> Optional[VPTypeInfo]:
    if annotation is None:
        return None
    if isinstance(annotation, _VPTypeWithLabels):
        return VPTypeInfo(product_type=annotation.product_type, labels=annotation.labels)
    if isinstance(annotation, type) and issubclass(annotation, _VPType):
        return VPTypeInfo(product_type=annotation._product_type, labels=None)
    return None
