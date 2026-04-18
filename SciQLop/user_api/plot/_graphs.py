import numpy as np
from .protocol import Plot, Plottable
from typing import Optional, Union, List
from ..virtual_products import VirtualProduct
from SciQLopPlots import SciQLopHistogram2D as _SciQLopHistogram2D
from ._thread_safety import on_main_thread

from SciQLop.components.sciqlop_logging import getLogger as _getLogger

__all__ = ['Graph', 'ColorMap', 'Histogram2D']

log = _getLogger(__name__)

AnyProductType = Union[str, VirtualProduct, List[str]]


def is_array_of_double(a):
    return isinstance(a, np.ndarray) and a.dtype == np.float64


def _to_float64(a):
    if a is None:
        return None
    if is_array_of_double(a):
        return a
    if hasattr(a, 'dtype') and np.issubdtype(a.dtype, np.datetime64):
        from speasy.core import datetime64_to_epoch
        return datetime64_to_epoch(a)
    return np.array(a, dtype=np.float64)


def ensure_arrays_of_double(*args):
    return (_to_float64(a) for a in args)

class Graph(Plottable):
    def __init__(self, impl):
        self._impl = impl

    @on_main_thread
    def set_data(self, x, y):
        self._impl.set_data(*ensure_arrays_of_double(x, y))

    @property
    @on_main_thread
    def data(self):
        return self._impl.data()

    @data.setter
    @on_main_thread
    def data(self, data):
        self.set_data(*data)

    @property
    @on_main_thread
    def visible(self) -> bool:
        return self._impl.visible()

    @visible.setter
    @on_main_thread
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

    @on_main_thread
    def set_data(self, x, y, z):
        self._impl.set_data(*ensure_arrays_of_double(x, y, z))

    @property
    @on_main_thread
    def data(self):
        return self._impl.data()

    @data.setter
    @on_main_thread
    def data(self, data):
        self.set_data(*data)

    @property
    @on_main_thread
    def visible(self) -> bool:
        return self._impl.visible()

    @visible.setter
    @on_main_thread
    def visible(self, visible):
        self._impl.set_visible(visible)

    def _repr_pretty_(self, p, cycle):
        if cycle:
            p.text("ColorMap(...)")
        else:
            p.text(f"ColorMap({self._impl})")


class Histogram2D(Plottable):
    """A 2D density histogram. Bins (x, y) scatter into a key_bins x value_bins grid."""

    def __init__(self, impl):
        self._impl: _SciQLopHistogram2D = impl

    def _get_impl_or_raise(self):
        if self._impl is None:
            raise ValueError("The histogram does not exist anymore.")
        return self._impl

    @on_main_thread
    def set_data(self, x, y):
        self._impl.set_data(*ensure_arrays_of_double(x, y))

    @property
    @on_main_thread
    def data(self):
        return self._impl.data()

    @data.setter
    @on_main_thread
    def data(self, data):
        self.set_data(*data)

    @property
    @on_main_thread
    def visible(self) -> bool:
        return self._impl.visible()

    @visible.setter
    @on_main_thread
    def visible(self, visible: bool):
        self._impl.set_visible(visible)

    @property
    @on_main_thread
    def z_log_scale(self) -> bool:
        return self._impl.z_log_scale()

    @z_log_scale.setter
    @on_main_thread
    def z_log_scale(self, v: bool):
        self._impl.set_z_log_scale(v)

    @property
    @on_main_thread
    def gradient(self):
        return self._impl.gradient()

    @gradient.setter
    @on_main_thread
    def gradient(self, g):
        self._impl.set_gradient(g)

    def _repr_pretty_(self, p, cycle):
        if cycle:
            p.text("Histogram2D(...)")
        else:
            p.text(f"Histogram2D({self._impl})")


def to_plottable(impl) -> Optional[Plottable]:
    if impl is None:
        return None
    if isinstance(impl, _SciQLopHistogram2D):
        return Histogram2D(impl)
    if hasattr(impl, "gradient"):
        return ColorMap(impl)
    return Graph(impl)

