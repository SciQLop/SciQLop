"""Detect whether a layer callback is data-aware and extract its type filter."""
import inspect
from dataclasses import dataclass
from typing import Optional, get_type_hints

from SciQLop.user_api.data_types import (
    _DataType, _DataTypeWithLabels, VPTypeInfo,
)


@dataclass(frozen=True)
class DataTypeInfo:
    product_type: str
    labels: Optional[list[str]] = None


def extract_data_type(callback) -> Optional[DataTypeInfo]:
    """Return the DataTypeInfo for the ``data`` parameter, or None if range-only."""
    sig = inspect.signature(callback)
    if "data" not in sig.parameters:
        return None
    try:
        hints = get_type_hints(callback, include_extras=True)
    except (NameError, TypeError):
        hints = {}
    annot = hints.get("data", sig.parameters["data"].annotation)
    if annot is inspect.Parameter.empty:
        return DataTypeInfo(product_type="any")
    return _info_from_annotation(annot) or DataTypeInfo(product_type="any")


def _info_from_annotation(annot) -> Optional[DataTypeInfo]:
    if isinstance(annot, _DataTypeWithLabels):
        return DataTypeInfo(product_type=annot.product_type, labels=annot.labels)
    if isinstance(annot, type) and issubclass(annot, _DataType):
        return DataTypeInfo(product_type=annot._product_type)
    return None
