import numpy as np
from .enums import PlotType, ScaleType, BinStrategy
from .protocol import Plot
from ._graphs import (Graph, ColorMap, Histogram2D, to_plottable,
                      ensure_arrays_of_double, _create_histogram2d,
                      _reject_if_colormap_already_present, _UNSET, _with_explicit)
from ._graphic_primitives import HorizontalLine
from typing import Optional, Union, List, Any
from ..virtual_products import VirtualProduct
from SciQLop.core import TimeRange
from SciQLop.components.sciqlop_logging import getLogger as _getLogger
from SciQLopPlots import SciQLopPlot as _SciQLopPlot
from SciQLopPlots import SciQLopTimeSeriesPlot as _SciQLopTimeSeriesPlot
from SciQLopPlots import SciQLopPlotAxis as _SciQLopPlotAxis
from SciQLopPlots import SciQLopNDProjectionPlot as _SciQLopNDProjectionPlot
from SciQLopPlots import GraphType as _GraphType, GraphMarkerShape as _GraphMarkerShape
from SciQLop.components.plotting.ui.time_sync_panel import plot_product as _plot_product
from ._thread_safety import on_main_thread
from ._overlay import Overlay
from .._annotations import experimental_api
from PySide6.QtGui import QColor as _QColor, QPen as _QPen

from speasy.core import AnyDateTimeType

_AxisName = str  # one of "x", "y", "y2", "z"

log = _getLogger(__name__)

AnyProductType = Union[str, VirtualProduct, List[str]]


def _fix_scatter_marker_pen(graph):
    for comp in graph.components():
        comp.set_marker_pen(_QPen(comp.color(), 1.5))

__all__ = ['XYPlot', 'TimeSeriesPlot', 'ProjectionPlot']


def is_product(product: Any) -> bool:
    if isinstance(product, (str, VirtualProduct)):
        return True
    if isinstance(product, list) and all(isinstance(p, str) for p in product):
        return True
    return False


def is_meta_object_instance(obj, meta_type: str):
    if hasattr(obj, "metaObject"):
        return obj.metaObject().className() == meta_type
    return False


def is_projection_plot(impl):
    return isinstance(impl, _SciQLopNDProjectionPlot) or is_meta_object_instance(impl, "SciQLopNDProjectionPlot")


def is_time_series_plot(impl):
    return isinstance(impl, _SciQLopTimeSeriesPlot) or is_meta_object_instance(impl, "SciQLopTimeSeriesPlot")


def is_xy_plot(impl):
    return isinstance(impl, _SciQLopPlot) or is_meta_object_instance(impl, "SciQLopPlot")


def _split_path(path: str) -> List[str]:
    if '//' in path:
        return path.split('//')
    return path.split('/')


def _get_axis_scale_type(axis: _SciQLopPlotAxis):
    return ScaleType.Logarithmic if axis.log() else ScaleType.Linear


def _set_axis_scale_type(scale_type: ScaleType, axis: _SciQLopPlotAxis):
    if scale_type == ScaleType.Linear:
        axis.set_log(False)
    elif scale_type == ScaleType.Logarithmic:
        axis.set_log(True)
    else:
        raise ValueError(f"Unknown scale type {scale_type}")


def _bind_y_axis(plottable, y_axis: str):
    """Retarget a freshly created plottable to the given y axis name.

    No-op when the target is the default (``"y"``) or when the plottable is
    not a line/curve/scatter Graph (colormaps share the plot's z scale and
    cannot live on a different y axis)."""
    if plottable is None or y_axis == "y":
        return plottable
    if isinstance(plottable, Graph):
        plottable.y_axis = y_axis
    return plottable


def _apply_name(raw_plottable, name):
    """Set the name on a freshly created plottable, unless *name* was left
    unset.

    Applied *after* creation rather than forwarded through ``**kwargs``: the
    installed SciQLopPlots 0.29.2 ``line()``/``scatter()``/
    ``parametric_curve()`` bindings reject an upfront ``name=`` keyword (only
    ``colormap()`` accepts it — verified directly), and the product path's
    ``plot_product()`` sometimes sets its own ``name=`` internally (e.g. for
    spectrograms), which would collide with a forwarded one. ``set_name()``
    on the returned object works uniformly across every graph type and
    every path (line, curve, colormap, scatter, product), matching the
    pattern already used for ``PlotPanel.plot_data``/``plot_function``."""
    if name is not _UNSET:
        raw_plottable.set_name(name)
    return raw_plottable


def _reject_zero_width_range(axis_name: str, lo: float, hi: float) -> None:
    """SciQLopPlots silently no-ops on `set_range(t, t)`, leaving the axis at
    its previous range with no indication anything went wrong. Reject up
    front so callers see the bug immediately."""
    if lo == hi:
        raise ValueError(
            f"zero-width {axis_name}-axis range ({lo} == {hi}); "
            "widen by at least one epsilon, or skip the call to keep the "
            "existing range"
        )


def to_product_path(product: AnyProductType) -> List[str]:
    if isinstance(product, VirtualProduct):
        return _split_path(product.path)
    elif isinstance(product, str):
        return _split_path(product)
    elif isinstance(product, list) and all(isinstance(p, str) for p in product):
        return product
    return []


def plot_product_or_raise(impl, product: AnyProductType, **kwargs):
    """Call the internal ``plot_product`` with a validated path, turning its
    silent ``None`` returns into actionable errors."""
    path = to_product_path(product)
    if not path or not all(segment.strip() for segment in path):
        raise ValueError(
            f"invalid product {product!r}: expected a 'provider//path//product' "
            "string, a list of path segments, or a VirtualProduct")
    result = _plot_product(impl, path, **kwargs)
    if result is None:
        raise ValueError(
            f"cannot plot product {'//'.join(path)!r}: not found in the "
            "products tree, or its provider is unavailable (paths use display "
            "names from the Products panel, joined with '//')")
    return result


def _concrete_impl(impl):
    """``panel.plots()`` yields ``SciQLopPlotInterfacePtr`` smart-pointer
    wrappers whose Shiboken type the C++ binding constructors (plot items,
    spans, …) reject. Dereference to the most-derived concrete plot once, at
    wrapper construction, so every downstream call sees the same type
    regardless of how the plot was obtained."""
    data = getattr(impl, "data", None)
    return data() if callable(data) else impl


class _BasePlot(Plot):
    def __init__(self, impl):
        self._impl: Optional[_SciQLopPlot] = _concrete_impl(impl)
        self._get_impl_or_raise().destroyed.connect(self._on_destroyed)

    def _get_impl_or_raise(self):
        if self._impl is None:
            raise ValueError("The plot does not exist anymore.")
        return self._impl

    def _on_destroyed(self):
        self._impl = None

    @property
    @on_main_thread
    def overlay(self) -> Overlay:
        """Access the in-canvas message overlay for this plot.

        Returns a fresh Overlay handle on each access — the wrapper is cheap
        and avoids stale-reference issues if the underlying overlay is
        recreated.
        """
        return Overlay(self._get_impl_or_raise().overlay())

    @experimental_api()
    @on_main_thread
    def scatter(self, x, y, *, labels=_UNSET, name=_UNSET, colors=_UNSET,
                **kwargs) -> Graph:
        """Plot data as a scatter graph (markers only, no lines).

        Parameters
        ----------
        x, y : array-like
            Data arrays. Converted to float64 automatically.
        labels : list[str], optional
            Per-component legend names.
        name : str, optional
            Graph name.
        colors : list, optional
            Per-component colors.
        **kwargs
            Forwarded to SciQLopPlots (e.g. ``marker``, ``y_axis``).

        Returns
        -------
        Graph
            The created scatter graph.

        Note
        ----
        ``name`` is applied via ``set_name()`` on the created graph rather
        than forwarded — the installed SciQLopPlots 0.29.2 ``scatter()``
        binding rejects an upfront ``name=`` keyword (verified directly; see
        ``_apply_name``).
        """
        kwargs = _with_explicit(kwargs, labels=labels, colors=colors)
        impl = self._get_impl_or_raise()
        kwargs.setdefault('marker', _GraphMarkerShape.FilledCircle)
        y_axis = kwargs.pop("y_axis", "y")
        graph = _apply_name(
            impl.scatter(*ensure_arrays_of_double(x, y), **kwargs), name)
        _fix_scatter_marker_pen(graph)
        wrapped = Graph(graph, plot=self)
        if y_axis != "y":
            wrapped.y_axis = y_axis
        return wrapped

    @experimental_api()
    @on_main_thread
    def add_hline(self, value: float, *,
                  color: Union[str, _QColor, None] = None,
                  movable: bool = False) -> HorizontalLine:
        """Add a horizontal line at a fixed Y value.

        Parameters
        ----------
        value : float
            Y-axis position.
        color : str or QColor, optional
            Line color (CSS string or QColor).
        movable : bool
            Whether the user can drag the line.

        Returns
        -------
        HorizontalLine
            The line object (position, color, line_width are settable).
        """
        return HorizontalLine(self, value, color=color, movable=movable)

    @experimental_api()
    @on_main_thread
    def remove_graph(self, graph: Graph) -> None:
        """Remove a graph (line, scatter, etc.) from this plot.

        Parameters
        ----------
        graph : Graph
            The graph to remove. Obtained from ``plot()``, ``scatter()``, etc.

        Raises
        ------
        TypeError
            If *graph* is not a graph wrapper.
        ValueError
            If the graph was already removed, or belongs to another plot.
        """
        if not isinstance(graph, (Graph, ColorMap, Histogram2D)):
            raise TypeError(
                f"remove_graph expects a Graph, ColorMap or Histogram2D, "
                f"got {type(graph).__name__}")
        if graph._impl is None:
            raise ValueError("The graph does not exist anymore.")
        impl = self._get_impl_or_raise()
        if graph._impl not in (impl.plottables() or []):
            raise ValueError("graph does not belong to this plot")
        impl.remove_plottable(graph._impl)

    @on_main_thread
    def rescale_axes(self) -> None:
        """Auto-fit axes to the currently visible data.

        Note
        ----
        For time-series and XY plots this fits the y axis to data inside the
        **currently visible x window**, not the full data extent. Set the time
        range (or x range) *before* calling ``rescale_axes`` — calling it
        before the data x window is set leaves y at its default range.
        """
        self._get_impl_or_raise().rescale_axes()

    def _resolve_axis(self, axis: _AxisName):
        impl = self._get_impl_or_raise()
        getter_name = f"{axis}_axis"
        getter = getattr(impl, getter_name, None)
        if getter is None:
            raise ValueError(
                f"axis {axis!r} not available on this plot "
                f"(expected one of: x, y, y2, z)"
            )
        return getter()

    @on_main_thread
    def apply_hints(self, hints) -> None:
        """Apply a :class:`SciQLop.core.plot_hints.PlotHints` bundle.

        Sets axis labels, units, and scales declaratively. Only fields set on
        the hints object are written. This is the supported way to push
        ISTP/HAPI metadata onto a plot from a plugin or notebook — prefer it
        over reaching through ``plot._impl``.
        """
        from SciQLop.core.plot_hints import apply_plot_hints as _apply
        _apply(self._get_impl_or_raise(), hints)

    @on_main_thread
    def set_axis_label(self, axis: _AxisName, label: str,
                       unit: Optional[str] = None) -> None:
        """Set a single axis label (with optional unit).

        Parameters
        ----------
        axis : {"x", "y", "y2", "z"}
            Which axis to label.
        label : str
            Axis label text.
        unit : str, optional
            Unit string, appended as " [unit]" if provided.
        """
        text = f"{label} [{unit}]" if unit else label
        self._resolve_axis(axis).set_label(text)

    @on_main_thread
    def set_axis_scale(self, axis: _AxisName, scale: ScaleType) -> None:
        """Set a single axis scale (linear or logarithmic).

        Parameters
        ----------
        axis : {"x", "y", "y2", "z"}
            Which axis to update.
        scale : ScaleType
            Linear or Logarithmic.
        """
        _set_axis_scale_type(scale, self._resolve_axis(axis))

    @on_main_thread
    def set_axis_range(self, axis: _AxisName, lo: float, hi: float) -> None:
        """Set a single axis range.

        Parameters
        ----------
        axis : {"x", "y", "y2", "z"}
            Which axis to update.
        lo, hi : float
            Range bounds. Swapped automatically when ``lo > hi``.

        Raises
        ------
        ValueError
            If the range is zero-width or the axis name is unknown.
        """
        lo, hi = min(lo, hi), max(lo, hi)
        _reject_zero_width_range(axis, lo, hi)
        self._resolve_axis(axis).set_range(lo, hi)

    @experimental_api()
    @on_main_thread
    def set_y2_range(self, ymin: float, ymax: float) -> None:
        """Set the secondary y-axis range.

        Parameters
        ----------
        ymin, ymax : float
            Range bounds. Swapped automatically when ``ymin > ymax``.
        """
        self.set_axis_range("y2", ymin, ymax)

    @property
    @experimental_api()
    @on_main_thread
    def y2_scale_type(self) -> ScaleType:
        """Scale type (linear/log) of the secondary y-axis."""
        return _get_axis_scale_type(self._resolve_axis("y2"))

    @y2_scale_type.setter
    @experimental_api()
    @on_main_thread
    def y2_scale_type(self, scale_type: ScaleType) -> None:
        _set_axis_scale_type(scale_type, self._resolve_axis("y2"))

    @property
    @experimental_api()
    @on_main_thread
    def y2_visible(self) -> bool:
        """Visibility of the secondary y-axis."""
        return self._resolve_axis("y2").visible()

    @y2_visible.setter
    @experimental_api()
    @on_main_thread
    def y2_visible(self, value: bool) -> None:
        self._resolve_axis("y2").set_visible(bool(value))


class XYPlot(_BasePlot):
    """A class representing a 2D XY plot where the x-axis and y-axis can represent any type of data.
    The plot can be used to visualize data in a Cartesian coordinate system.
    Usually users won't directly create an XYPlot, but rather use the PlotPanel plot method to create one.

    See Also
    --------
    TimeSeriesPlot : A class representing a time series plot where the x-axis always represents time.
    ProjectionPlot : A class representing a projection plot.
    """

    def __init__(self, impl):
        super().__init__(impl)
        assert is_xy_plot(impl)

    @property
    @on_main_thread
    def plot_type(self) -> PlotType:
        self._get_impl_or_raise()
        return PlotType.XY

    @on_main_thread
    def plot(self, *args, labels=_UNSET, name=_UNSET, colors=_UNSET,
             graph_type=_UNSET, y_log_scale=_UNSET, z_log_scale=_UNSET,
             y_axis="y", **kwargs):
        """Plot on this XY plot: two vectors ``(x, y)``, three ``(x, y, z)`` →
        colormap, or a callback ``f(start, stop) -> (x, y)``. Product paths are
        not accepted here — use ``PlotPanel.plot_product`` or
        ``TimeSeriesPlot.plot``.

        Parameters
        ----------
        labels : list[str], optional
            Per-component legend names.
        name : str, optional
            Graph name.
        colors : list, optional
            Per-component colors.
        graph_type : GraphType, optional
            Defaults to ``ParametricCurve`` for XY plots.
        y_log_scale, z_log_scale : bool, optional
            Logarithmic Y / Z scale.
        y_axis : {"y", "y2"}
            Bind the graph to the primary or secondary y-axis (line / curve /
            scatter only — not colormaps).
        **kwargs
            Forwarded to SciQLopPlots.
        """
        kwargs = _with_explicit(kwargs, labels=labels, colors=colors,
                                graph_type=graph_type, y_log_scale=y_log_scale,
                                z_log_scale=z_log_scale)
        kwargs["graph_type"] = kwargs.get("graph_type", _GraphType.ParametricCurve)
        if len(args) == 1:
            if callable(args[0]):
                raw = _apply_name(self._get_impl_or_raise().plot(*args, **kwargs), name)
                return _bind_y_axis(Graph(raw, plot=self), y_axis)
            else:
                raise ValueError("Invalid arguments")
        elif len(args) == 2:
            raw = _apply_name(
                self._get_impl_or_raise().plot(*ensure_arrays_of_double(*args), **kwargs), name)
            return _bind_y_axis(Graph(raw, plot=self), y_axis)
        elif len(args) == 3:
            _reject_if_colormap_already_present(self._get_impl_or_raise())
            raw = _apply_name(
                self._get_impl_or_raise().plot(*ensure_arrays_of_double(*args), **kwargs), name)
            return ColorMap(raw)
        return None

    @experimental_api()
    @on_main_thread
    def histogram2d(self, x, y, *, name: str = "histogram",
                    x_bins: Union[int, np.ndarray] = 100,
                    y_bins: Union[int, np.ndarray] = 100,
                    x_bin_strategy: BinStrategy = BinStrategy.Linear,
                    y_bin_strategy: BinStrategy = BinStrategy.Linear,
                    z_log_scale: bool = False) -> Histogram2D:
        """Add a 2D density histogram to this plot.

        Parameters
        ----------
        x, y : array-like
            Scatter data to bin.
        name : str
            Histogram label.
        x_bins, y_bins : int or array-like
            Bin counts along X and Y, or explicit monotonic bin edges.
        x_bin_strategy, y_bin_strategy : BinStrategy
            Spacing strategy used when *x_bins* / *y_bins* are integers.
        z_log_scale : bool
            Use a logarithmic color scale.

        Returns
        -------
        Histogram2D
            The histogram plottable.
        """
        return _create_histogram2d(self._get_impl_or_raise(), x, y,
                                   name=name, x_bins=x_bins,
                                   y_bins=y_bins,
                                   x_bin_strategy=x_bin_strategy,
                                   y_bin_strategy=y_bin_strategy,
                                   z_log_scale=z_log_scale)

    @on_main_thread
    def set_x_range(self, xmin: float, xmax: float):
        """Set the x-axis range of the plot and replot.

        Parameters
        ----------
        xmin : float
            The minimum value of the x-axis range.
        xmax : float
            The maximum value of the x-axis range.
        """
        xmin, xmax = min(xmin, xmax), max(xmin, xmax)
        _reject_zero_width_range("x", xmin, xmax)
        self._get_impl_or_raise().x_axis().set_range(xmin, xmax)

    @on_main_thread
    def set_y_range(self, ymin: float, ymax: float):
        """Set the y-axis range of the plot and replot.

        Parameters
        ----------
        ymin : float
            The minimum value of the y-axis range.
        ymax : float
            The maximum value of the y-axis range.
        """
        ymin, ymax = min(ymin, ymax), max(ymin, ymax)
        _reject_zero_width_range("y", ymin, ymax)
        self._get_impl_or_raise().y_axis().set_range(ymin, ymax)

    @property
    @on_main_thread
    def x_scale_type(self) -> ScaleType:
        return _get_axis_scale_type(self._get_impl_or_raise().x_axis())

    @x_scale_type.setter
    @on_main_thread
    def x_scale_type(self, scale_type: ScaleType):
        _set_axis_scale_type(scale_type, self._get_impl_or_raise().x_axis())
        self.replot()

    @property
    @on_main_thread
    def y_scale_type(self) -> ScaleType:
        return _get_axis_scale_type(self._get_impl_or_raise().y_axis())

    @y_scale_type.setter
    @on_main_thread
    def y_scale_type(self, scale_type: ScaleType):
        _set_axis_scale_type(scale_type, self._get_impl_or_raise().y_axis())
        self.replot()

    @on_main_thread
    def replot(self):
        """Replot the plot. This method is used to force a redraw of the plot.
        """
        self._get_impl_or_raise().replot()

    def _repr_pretty_(self, p, cycle):
        if cycle:
            p.text("XYPlot(...)")
        else:
            p.text(f"XYPlot({self._impl})")


class TimeSeriesPlot(_BasePlot):
    """A class representing a time series plot. The x-axis always represents time, while the y-axis can represent any type of data.
    Usually users won't directly create a TimeSeriesPlot, but rather use the PlotPanel plot method to create one.

    See Also
    --------
    XYPlot : A class representing a 2D XY plot where the x-axis and y-axis can represent any type of data.
    ProjectionPlot : A class representing a projection plot.
    """

    def __init__(self, impl):
        super().__init__(impl)
        assert is_time_series_plot(impl)

    @property
    @on_main_thread
    def plot_type(self) -> PlotType:
        self._get_impl_or_raise()
        return PlotType.TimeSeries

    @on_main_thread
    def plot(self, *args, labels=_UNSET, name=_UNSET, colors=_UNSET,
             graph_type=_UNSET, y_log_scale=_UNSET, z_log_scale=_UNSET,
             y_axis="y", **kwargs):
        """Plot on this time-series plot: two/three vectors ``(x, y[, z])``, a
        product path, or a callback ``f(start, stop) -> (x, y[, z])``.

        Parameters
        ----------
        labels : list[str], optional
            Per-component legend names.
        name : str, optional
            Graph name.
        colors : list, optional
            Per-component colors.
        graph_type : GraphType, optional
            Line (default), Curve, ColorMap or Scatter.
        y_log_scale, z_log_scale : bool, optional
            Logarithmic Y / Z scale.
        y_axis : {"y", "y2"}
            Bind the graph to the primary or secondary y-axis.
        **kwargs
            Forwarded to SciQLopPlots.

        Returns
        -------
        Optional[Graph]

        Note
        ----
        For the product path (``plot(product)``), ``labels`` is supplied by
        the product's provider — passing it here conflicts with the
        provider's own value and raises ``TypeError`` (verified against
        SciQLopPlots 0.29.2). ``name`` is safe on every path: it is applied
        via ``set_name()`` on the created graph rather than forwarded.
        """
        kwargs = _with_explicit(kwargs, labels=labels, colors=colors,
                                graph_type=graph_type, y_log_scale=y_log_scale,
                                z_log_scale=z_log_scale)
        if len(args) == 1:
            if callable(args[0]):
                raw = _apply_name(self._get_impl_or_raise().plot(*args, **kwargs), name)
                return _bind_y_axis(to_plottable(raw, plot=self), y_axis)
            else:
                raw = _apply_name(
                    plot_product_or_raise(self._get_impl_or_raise(), args[0], **kwargs), name)
                return _bind_y_axis(to_plottable(raw, plot=self), y_axis)
        elif 3 >= len(args) >= 2:
            if len(args) == 3:
                _reject_if_colormap_already_present(self._get_impl_or_raise())
            raw = _apply_name(
                self._get_impl_or_raise().plot(*ensure_arrays_of_double(*args), **kwargs), name)
            return _bind_y_axis(to_plottable(raw, plot=self), y_axis)
        raise ValueError("Invalid arguments")

    @experimental_api()
    @on_main_thread
    def histogram2d(self, x, y, *, name: str = "histogram",
                    x_bins: Union[int, np.ndarray] = 100,
                    y_bins: Union[int, np.ndarray] = 100,
                    x_bin_strategy: BinStrategy = BinStrategy.Linear,
                    y_bin_strategy: BinStrategy = BinStrategy.Linear,
                    z_log_scale: bool = False) -> Histogram2D:
        """Add a 2D density histogram to this plot. See XYPlot.histogram2d."""
        return _create_histogram2d(self._get_impl_or_raise(), x, y,
                                   name=name, x_bins=x_bins,
                                   y_bins=y_bins,
                                   x_bin_strategy=x_bin_strategy,
                                   y_bin_strategy=y_bin_strategy,
                                   z_log_scale=z_log_scale)

    @on_main_thread
    def set_x_range(self, xmin: AnyDateTimeType, xmax: AnyDateTimeType):
        """Set the x-axis range of the plot.
        This method accepts any type of datetime object, Python datetime object, or timestamp or string.

        Args:
            xmin (AnyDateTimeType): The minimum value of the x-axis range.
            xmax (AnyDateTimeType): The maximum value of the x-axis range.

        Note:
            Setting the x-axis range will adjust the time range of the plot panel in which the plot is displayed and
            thus affect all plots in the panel.

            While this is discouraged, it is possible to set xmin>xmax, in which case it will automatically swap the values.
        """
        self.time_range = TimeRange(xmin, xmax)

    @on_main_thread
    def set_y_range(self, ymin: float, ymax: float):
        """Set the main y-axis range of the plot.

        Args:
            ymin (float): The minimum value of the y-axis range.
            ymax (float): The maximum value of the y-axis range.

        Note:
            Setting the y-axis range will only affect the plot in which it is called. It will not affect other plots in the same plot panel.
            While this is discouraged, it is possible to set ymin>ymax, in which case it will automatically swap the values.
        """
        s_y_min = min(ymin, ymax)
        s_y_max = max(ymin, ymax)
        _reject_zero_width_range("y", s_y_min, s_y_max)
        self._get_impl_or_raise().y_axis().set_range(s_y_min, s_y_max)

    @on_main_thread
    def set_y_scale_type(self, scale: ScaleType):
        """Set the scale type of the main y-axis.

        Args:
            scale (ScaleType): The scale type.
        """
        self.y_scale_type = scale

    @property
    @on_main_thread
    def time_range(self) -> TimeRange:
        return self._get_impl_or_raise().time_axis().range()

    @time_range.setter
    @on_main_thread
    def time_range(self, time_range: TimeRange):
        self._get_impl_or_raise().set_time_range(time_range)

    @property
    @on_main_thread
    def y_scale_type(self) -> ScaleType:
        return _get_axis_scale_type(self._get_impl_or_raise().y_axis())

    @y_scale_type.setter
    @on_main_thread
    def y_scale_type(self, scale_type: ScaleType):
        _set_axis_scale_type(scale_type, self._get_impl_or_raise().y_axis())
        self.replot()

    @on_main_thread
    def replot(self):
        """Replot the plot. This method is used to force a redraw of the plot.
        """
        self._get_impl_or_raise().replot()

    def _repr_pretty_(self, p, cycle):
        if cycle:
            p.text("TimeSeriesPlot(...)")
        else:
            p.text(f"TimeSeriesPlot({self._impl})")


class ProjectionPlot:
    """A class representing a projection plot. The x-axis and y-axis can represent any type of data.
    The plot can be used to visualize data in a Cartesian coordinate system.
    Usually users won't directly create a ProjectionPlot, but rather use the PlotPanel plot method to create one.

    See Also
    --------
    XYPlot : A class representing a 2D XY plot where the x-axis and y-axis can represent any type of data.
    TimeSeriesPlot : A class representing a time series plot where the x-axis always represents time.
    """

    def __init__(self, impl):
        assert is_projection_plot(impl)
        self._impl: Optional[_SciQLopNDProjectionPlot] = _concrete_impl(impl)
        self._get_impl_or_raise().destroyed.connect(self._on_destroyed)

    @property
    @on_main_thread
    def plot_type(self) -> PlotType:
        self._get_impl_or_raise()
        return PlotType.Projection

    def _on_destroyed(self):
        self._impl = None

    def _get_impl_or_raise(self) -> _SciQLopNDProjectionPlot:
        if self._impl is None:
            raise ValueError("The plot does not exist anymore.")
        return self._impl

    @on_main_thread
    def set_x_range(self, min: float, max: float):
        """Set the x-axis range of every projection subplot.

        The SciQLopNDProjectionPlot axes are range-coupled by default, so
        setting the first subplot propagates across the others; we still write
        the value to every subplot to stay robust if coupling is disabled.

        Parameters
        ----------
        min : float
            The minimum value of the x-axis range.
        max : float
            The maximum value of the x-axis range.
        """
        impl = self._get_impl_or_raise()
        for i in range(impl.subplot_count()):
            impl.subplot(i).x_axis().set_range(min, max)

    @on_main_thread
    def set_y_range(self, min: float, max: float):
        """Set the y-axis range of every projection subplot.

        Parameters
        ----------
        min : float
            The minimum value of the y-axis range.
        max : float
            The maximum value of the y-axis range.
        """
        impl = self._get_impl_or_raise()
        for i in range(impl.subplot_count()):
            impl.subplot(i).y_axis().set_range(min, max)

    @on_main_thread
    def set_x_scale_type(self, scale: ScaleType):
        """Set the scale type (linear/log) of the x-axis on every projection
        subplot.

        Parameters
        ----------
        scale : ScaleType
            The scale type.
        """
        impl = self._get_impl_or_raise()
        for i in range(impl.subplot_count()):
            _set_axis_scale_type(scale, impl.subplot(i).x_axis())

    @on_main_thread
    def set_y_scale_type(self, scale: ScaleType):
        """Set the scale type (linear/log) of the y-axis on every projection
        subplot.

        Parameters
        ----------
        scale : ScaleType
            The scale type.
        """
        impl = self._get_impl_or_raise()
        for i in range(impl.subplot_count()):
            _set_axis_scale_type(scale, impl.subplot(i).y_axis())

    @on_main_thread
    def plot(self, product: Union[str, VirtualProduct], **kwargs) -> Optional[Graph]:
        """Plot a product on the plot.
        Parameters
        ----------
        product : Union[str, VirtualProduct]
            The product to plot. Can be a string or a VirtualProduct.
        **kwargs : Any
            Additional arguments to pass to the plot method. Actually unused.
        Returns
        -------
        Optional[Graph]
            The graph object representing the plot.
        """
        return to_plottable(
            plot_product_or_raise(self._get_impl_or_raise(), product, graph_type=_GraphType.ParametricCurve))

    def _repr_pretty_(self, p, cycle):
        if cycle:
            p.text("ProjectionPlot(...)")
        else:
            p.text(f"ProjectionPlot({self._impl})")


def to_plot(plot) -> Union[ProjectionPlot, TimeSeriesPlot, XYPlot, None]:
    if is_time_series_plot(plot):
        return TimeSeriesPlot(plot)
    elif is_projection_plot(plot):
        return ProjectionPlot(plot)
    elif is_xy_plot(plot):
        return XYPlot(plot)
    else:
        return None
