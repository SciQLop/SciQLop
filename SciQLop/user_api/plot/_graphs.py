import numpy as np
from .protocol import Plot, Plottable
from .enums import BinStrategy
from typing import Optional, Union, List
from ..virtual_products import VirtualProduct
from SciQLopPlots import SciQLopHistogram2D as _SciQLopHistogram2D
from SciQLopPlots import SciQLopColorMapBase as _SciQLopColorMapBase
from ._thread_safety import on_main_thread
from SciQLop.core import tracing as _tracing

from SciQLop.components.sciqlop_logging import getLogger as _getLogger

__all__ = ['Graph', 'ColorMap', 'Histogram2D']

log = _getLogger(__name__)

AnyProductType = Union[str, VirtualProduct, List[str]]


def is_array_of_double(a):
    return isinstance(a, np.ndarray) and a.dtype == np.float64


def _to_float64(a):
    if a is None:
        return None
    arr = a if isinstance(a, np.ndarray) else np.asarray(a)
    if arr.ndim == 0:
        raise ValueError("scalar (0-d) data is not plottable; pass a 1-D array")
    if np.issubdtype(arr.dtype, np.complexfloating):
        raise ValueError(
            "complex data is not plottable; take .real, .imag or np.abs() "
            "explicitly")
    if arr.dtype == np.float64:
        return np.ascontiguousarray(arr)
    if np.issubdtype(arr.dtype, np.datetime64):
        from speasy.core import datetime64_to_epoch
        return np.ascontiguousarray(datetime64_to_epoch(arr))
    return np.ascontiguousarray(arr.astype(np.float64))


def ensure_arrays_of_double(*args):
    return tuple(_to_float64(a) for a in args)


_UNSET = object()


def _with_explicit(kwargs: dict, **named) -> dict:
    """Fold caller-set keyword params into the forwarded ``kwargs`` dict.

    Values left as the ``_UNSET`` sentinel are not inserted, preserving the
    exact present/absent semantics the ``**kwargs`` passthrough had before
    these options were promoted to explicit keyword parameters. Falsy real
    values (``False``, ``[]``, ``0``) are forwarded; only ``_UNSET`` is skipped.
    """
    for key, value in named.items():
        if value is not _UNSET:
            kwargs[key] = value
    return kwargs


def _len_safe(a):
    try:
        return int(len(a))
    except TypeError:
        return 0


_VALID_Y_AXES = ("y", "y2")


def _wire_destroyed(wrapper, impl):
    """Clear the wrapper's impl when the C++ object dies, so stale handles
    raise a friendly ValueError instead of a cryptic Shiboken RuntimeError."""
    try:
        impl.destroyed.connect(wrapper._on_destroyed)
    except (AttributeError, RuntimeError):
        pass


class Graph(Plottable):
    def __init__(self, impl, plot=None):
        self._impl = impl
        self._plot = plot
        _wire_destroyed(self, impl)

    def _on_destroyed(self):
        self._impl = None

    def _get_impl_or_raise(self):
        if self._impl is None:
            raise ValueError("The graph does not exist anymore.")
        return self._impl

    @property
    @on_main_thread
    def y_axis(self) -> Optional[str]:
        """Which y-axis this graph is attached to: ``"y"`` or ``"y2"``.

        Returns ``None`` if the parent plot reference is not available
        (e.g. graphs created through low-level paths that don't carry it).
        """
        if self._plot is None:
            return None
        plot_impl = self._plot._get_impl_or_raise()
        current = self._get_impl_or_raise().y_axis()
        if current is plot_impl.y2_axis():
            return "y2"
        return "y"

    @y_axis.setter
    @on_main_thread
    def y_axis(self, name: str) -> None:
        if name not in _VALID_Y_AXES:
            raise ValueError(
                f"axis {name!r} not valid for a graph (expected one of: y, y2)"
            )
        if self._plot is None:
            raise RuntimeError(
                "cannot retarget this graph: its parent plot reference is unset"
            )
        self._get_impl_or_raise().set_y_axis(self._plot._resolve_axis(name))

    @on_main_thread
    def set_data(self, x, y):
        with _tracing.zone("Graph.set_data", cat="plot", n_points=_len_safe(x)):
            with _tracing.zone("ensure_arrays_of_double", cat="plot"):
                arrays = ensure_arrays_of_double(x, y)
            with _tracing.zone("impl.set_data", cat="plot"):
                self._get_impl_or_raise().set_data(*arrays)

    @property
    @on_main_thread
    def data(self):
        return self._get_impl_or_raise().data()

    @data.setter
    @on_main_thread
    def data(self, data):
        self.set_data(*data)

    @property
    @on_main_thread
    def visible(self) -> bool:
        return self._get_impl_or_raise().visible()

    @visible.setter
    @on_main_thread
    def visible(self, visible):
        self._get_impl_or_raise().set_visible(visible)

    def _repr_pretty_(self, p, cycle):
        if cycle:
            p.text("Graph(...)")
        else:
            p.text(f"Graph({self._impl})")


class ColorMap(Plottable):
    def __init__(self, impl):
        self._impl = impl
        _wire_destroyed(self, impl)

    def _on_destroyed(self):
        self._impl = None

    def _get_impl_or_raise(self):
        if self._impl is None:
            raise ValueError("The colormap does not exist anymore.")
        return self._impl

    @on_main_thread
    def set_data(self, x, y, z):
        with _tracing.zone("ColorMap.set_data", cat="plot",
                           nx=_len_safe(x), ny=_len_safe(y)):
            with _tracing.zone("ensure_arrays_of_double", cat="plot"):
                arrays = ensure_arrays_of_double(x, y, z)
            with _tracing.zone("impl.set_data", cat="plot"):
                self._get_impl_or_raise().set_data(*arrays)

    @property
    @on_main_thread
    def data(self):
        return self._get_impl_or_raise().data()

    @data.setter
    @on_main_thread
    def data(self, data):
        self.set_data(*data)

    @property
    @on_main_thread
    def visible(self) -> bool:
        return self._get_impl_or_raise().visible()

    @visible.setter
    @on_main_thread
    def visible(self, visible):
        self._get_impl_or_raise().set_visible(visible)

    def _repr_pretty_(self, p, cycle):
        if cycle:
            p.text("ColorMap(...)")
        else:
            p.text(f"ColorMap({self._impl})")


class Histogram2D(Plottable):
    """A 2D density histogram. Bins (x, y) scatter into an x_bins x y_bins grid."""

    def __init__(self, impl, x_bin_edges=None, y_bin_edges=None):
        self._impl: _SciQLopHistogram2D = impl
        self._x_bin_edges = x_bin_edges
        self._y_bin_edges = y_bin_edges
        _wire_destroyed(self, impl)

    def _on_destroyed(self):
        self._impl = None

    def _get_impl_or_raise(self):
        if self._impl is None:
            raise ValueError("The histogram does not exist anymore.")
        return self._impl

    @on_main_thread
    def set_data(self, x, y):
        with _tracing.zone("Histogram2D.set_data", cat="plot", n_points=_len_safe(x)):
            with _tracing.zone("ensure_arrays_of_double", cat="plot"):
                arrays = ensure_arrays_of_double(x, y)
            with _tracing.zone("impl.set_data", cat="plot"):
                self._get_impl_or_raise().set_data(*arrays)

    @property
    @on_main_thread
    def data(self):
        return self._get_impl_or_raise().data()

    @data.setter
    @on_main_thread
    def data(self, data):
        self.set_data(*data)

    @property
    @on_main_thread
    def visible(self) -> bool:
        return self._get_impl_or_raise().visible()

    @visible.setter
    @on_main_thread
    def visible(self, visible: bool):
        self._get_impl_or_raise().set_visible(visible)

    @property
    @on_main_thread
    def z_log_scale(self) -> bool:
        return self._get_impl_or_raise().z_log_scale()

    @z_log_scale.setter
    @on_main_thread
    def z_log_scale(self, v: bool):
        self._get_impl_or_raise().set_z_log_scale(v)

    @property
    @on_main_thread
    def gradient(self):
        return self._get_impl_or_raise().gradient()

    @gradient.setter
    @on_main_thread
    def gradient(self, g):
        self._get_impl_or_raise().set_gradient(g)

    @property
    def x_bin_edges(self):
        """Bin edges used along the X axis, or ``None`` if not computed."""
        return self._x_bin_edges

    @property
    def y_bin_edges(self):
        """Bin edges used along the Y axis, or ``None`` if not computed."""
        return self._y_bin_edges

    def _repr_pretty_(self, p, cycle):
        if cycle:
            p.text("Histogram2D(...)")
        else:
            p.text(f"Histogram2D({self._impl})")


def _reject_if_colormap_already_present(plot_impl) -> None:
    """A plot has a single color-scale axis, so it can host at most one
    colormap-style plottable (ColorMap, Histogram2D, Waterfall). Reject up
    front rather than silently creating a second one that fights the first
    for the color scale."""
    existing = plot_impl.plottables() or []
    for p in existing:
        if isinstance(p, _SciQLopColorMapBase):
            raise RuntimeError(
                "this plot already contains a colormap-style plottable "
                f"({type(p).__name__}); a plot can host only one. "
                "Call panel.histogram2d(...) to create a new plot instead."
            )


_MAX_HISTOGRAM_CELLS = 25_000_000


def _bin_count(bins):
    """Return the number of cells for an int or array-like bin specification."""
    if isinstance(bins, (int, np.integer)):
        return int(bins)
    edges = np.asarray(bins, dtype=np.float64)
    if edges.ndim != 1:
        raise ValueError("bin edges must be a 1-D array")
    if edges.size < 2:
        raise ValueError("bin edges must contain at least two values")
    return edges.size - 1


def validate_histogram_bins(x_bins, y_bins) -> None:
    x_count = _bin_count(x_bins)
    y_count = _bin_count(y_bins)
    if x_count < 1 or y_count < 1:
        raise ValueError(
            f"histogram bins must be >= 1 (got x_bins={x_bins}, y_bins={y_bins})")
    if x_count * y_count > _MAX_HISTOGRAM_CELLS:
        raise ValueError(
            f"histogram grid {x_count}x{y_count} exceeds the "
            f"{_MAX_HISTOGRAM_CELLS:,}-cell sanity cap; reduce x_bins/y_bins")


def _symlog_edges(lo: float, hi: float, bins: int, linthresh: Optional[float] = None):
    """Compute symmetric-log spaced edges that handle negative values.

    The interval is transformed through a smooth symmetric-log function,
    linearly binned in transformed space, and transformed back. This produces
    fine linear spacing near zero and progressively wider spacing toward the
    positive and negative extremes.
    """
    if lo == hi:
        # Degenerate range: fall back to a tiny linear span so the array has
        # the expected length and we don't hit np.geomspace/log1p edge cases.
        return np.linspace(lo, lo + 1.0, bins + 1)

    max_abs = max(abs(lo), abs(hi))
    if linthresh is None:
        linthresh = max_abs / bins if bins > 0 else max_abs
    if linthresh <= 0:
        linthresh = np.nextafter(float(0), 1.0)

    def _symlog(x):
        return np.sign(x) * np.log1p(np.abs(x) / linthresh) * linthresh

    def _inv_symlog(y):
        return np.sign(y) * linthresh * np.expm1(np.abs(y) / linthresh)

    t_lo, t_hi = _symlog(lo), _symlog(hi)
    t_edges = np.linspace(t_lo, t_hi, bins + 1)
    return _inv_symlog(t_edges)


def _compute_bin_edges(data, bins, strategy: BinStrategy):
    """Compute bin edges for a histogram axis.

    Parameters
    ----------
    data : array-like
        Values used to derive the edge range when *bins* is an integer.
    bins : int or array-like
        Number of bins or explicit monotonic bin edges.
    strategy : BinStrategy
        Spacing strategy applied when *bins* is an integer.

    Returns
    -------
    np.ndarray
        Float64 bin edges.
    """
    if not isinstance(bins, (int, np.integer)):
        edges = np.asarray(bins, dtype=np.float64)
        if edges.ndim != 1:
            raise ValueError("bin edges must be a 1-D array")
        if edges.size < 2:
            raise ValueError("bin edges must contain at least two values")
        return edges

    if bins < 1:
        raise ValueError(f"bins must be >= 1, got {bins}")

    arr = np.asarray(data, dtype=np.float64)
    lo, hi = float(np.min(arr)), float(np.max(arr))

    if strategy == BinStrategy.Linear:
        return np.linspace(lo, hi, bins + 1)
    if strategy == BinStrategy.Log:
        if lo <= 0:
            # Log spacing requires strictly positive bounds. Shift the lower
            # bound just above zero while keeping a representable edge at the
            # original minimum (the caller still sees positive edges).
            lo = max(np.nextafter(float(0), 1.0), hi / (bins + 1))
        return np.geomspace(lo, hi, bins + 1)
    if strategy == BinStrategy.SymLog:
        return _symlog_edges(lo, hi, bins)
    raise ValueError(f"Unknown bin strategy {strategy}")


def _create_histogram2d(plot_impl, *args, name: str = "histogram",
                        x_bins=100, y_bins=100,
                        x_bin_strategy: BinStrategy = BinStrategy.Linear,
                        y_bin_strategy: BinStrategy = BinStrategy.Linear,
                        z_log_scale: bool = False, gradient=None) -> Histogram2D:
    validate_histogram_bins(x_bins, y_bins)
    _reject_if_colormap_already_present(plot_impl)

    x_is_edges = not isinstance(x_bins, (int, np.integer))
    y_is_edges = not isinstance(y_bins, (int, np.integer))

    def _upstream_kwargs(x_count, y_count):
        kwargs = {"name": name, "x_bins": x_count, "y_bins": y_count}
        # Explicit edges override the strategy: the caller chose the spacing.
        if not x_is_edges and x_bin_strategy == BinStrategy.Log:
            kwargs["x_bins_log"] = True
        if not y_is_edges and y_bin_strategy == BinStrategy.Log:
            kwargs["y_bins_log"] = True
        return kwargs

    if len(args) == 1 and callable(args[0]):
        x_count = _bin_count(x_bins)
        y_count = _bin_count(y_bins)
        impl = plot_impl.histogram2d(args[0], **_upstream_kwargs(x_count, y_count))
        hist = Histogram2D(impl)
    elif len(args) == 2:
        x, y = ensure_arrays_of_double(*args)
        x_edges = _compute_bin_edges(x, x_bins, x_bin_strategy)
        y_edges = _compute_bin_edges(y, y_bins, y_bin_strategy)
        impl = plot_impl.histogram2d(
            x, y,
            **_upstream_kwargs(len(x_edges) - 1, len(y_edges) - 1))
        hist = Histogram2D(impl, x_bin_edges=x_edges, y_bin_edges=y_edges)
    else:
        raise TypeError("histogram2d expects (callable,) or (x, y)")

    if z_log_scale:
        hist.z_log_scale = z_log_scale
    if gradient is not None:
        hist.gradient = gradient
    return hist


def to_plottable(impl, plot=None) -> Optional[Plottable]:
    if impl is None:
        return None
    if isinstance(impl, _SciQLopHistogram2D):
        return Histogram2D(impl)
    if hasattr(impl, "gradient"):
        return ColorMap(impl)
    return Graph(impl, plot=plot)

