import numpy as np
from .protocol import Plot, Plottable
from typing import Optional, Union, List
from ..virtual_products import VirtualProduct

from SciQLop.backend.sciqlop_logging import getLogger as _getLogger

__all__ = ['Graph', 'ColorMap']

log = _getLogger(__name__)

AnyProductType = Union[str, VirtualProduct, List[str]]


def is_array_of_double(a):
    return isinstance(a, np.ndarray) and a.dtype == np.float64


def ensure_arrays_of_double(*args):
    return (np.array(a, dtype=np.float64) if not (is_array_of_double(a) or a is None) else a for a in args)

class Graph(Plottable):
    def __init__(self, impl):
        self._impl = impl

    def set_data(self, x, y):
        self._impl.set_data(*ensure_arrays_of_double(x, y))

    @property
    def data(self):
        return self._impl.data()

    @data.setter
    def data(self, data):
        self.set_data(*data)

    @property
    def visible(self) -> bool:
        return self._impl.visible()

    @visible.setter
    def visible(self, visible):
        self._impl.set_visible(visible)

    def _repr_pretty_(self, p, cycle):
        if cycle:
            p.text("Graph(...)")
        else:
            p.text(f"Graph({self._impl})")


class ColorMap(Plottable):
    def __init__(self, impl):
        self._impl = impl

    def _get_impl_or_raise(self):
        if self._impl is None:
            raise ValueError("The plot does not exist anymore.")
        return self._impl

    def set_data(self, x, y, z):
        self._impl.set_data(*ensure_arrays_of_double(x, y, z))

    @property
    def data(self):
        return self._impl.data()

    @data.setter
    def data(self, data):
        self.set_data(*data)

    @property
    def visible(self) -> bool:
        return self._impl.visible()

    @visible.setter
    def visible(self, visible):
        self._impl.set_visible(visible)

    def _repr_pretty_(self, p, cycle):
        if cycle:
            p.text("ColorMap(...)")
        else:
            p.text(f"ColorMap({self._impl})")


def to_plottable(impl) -> Optional[Plottable]:
    if impl is None:
        return None
    if hasattr(impl, "gradient"):
        return ColorMap(impl)
    else:
        return Graph(impl)

