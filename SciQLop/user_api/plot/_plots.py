from .enums import ScaleType
from .protocol import Plot
from ._graphs import Graph, ColorMap, to_plottable, ensure_arrays_of_double
from typing import Optional, Union, List, Any
from ..virtual_products import VirtualProduct
from SciQLop.backend import TimeRange
from SciQLop.backend.sciqlop_logging import getLogger as _getLogger
from SciQLopPlots import SciQLopPlot as _SciQLopPlot
from SciQLopPlots import SciQLopTimeSeriesPlot as _SciQLopTimeSeriesPlot
from SciQLopPlots import SciQLopPlotAxis as _SciQLopPlotAxis
from SciQLopPlots import SciQLopNDProjectionPlot as _SciQLopNDProjectionPlot
from SciQLopPlots import GraphType as _GraphType
from SciQLop.widgets.plots.time_sync_panel import plot_product as _plot_product

from speasy.core import AnyDateTimeType

log = _getLogger(__name__)

AnyProductType = Union[str, VirtualProduct, List[str]]

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


def to_product_path(product: AnyProductType) -> List[str]:
    if isinstance(product, VirtualProduct):
        return _split_path(product.path)
    elif isinstance(product, str):
        return _split_path(product)
    elif isinstance(product, list) and all(isinstance(p, str) for p in product):
        return product
    return []



class _BasePlot(Plot):
    def __init__(self, impl):
        self._impl: Optional[_SciQLopPlot] = impl
        self._impl.destroyed.connect(self._on_destroyed)

    def _get_impl_or_raise(self):
        if self._impl is None:
            raise ValueError("The plot does not exist anymore.")
        return self._impl

    def _on_destroyed(self):
        self._impl = None

class XYPlot(_BasePlot):
    def __init__(self, impl):
        super().__init__(impl)
        assert is_xy_plot(impl)

    def plot(self, *args, **kwargs):
        """Plot data on the plot, either two vectors or a product path or a function"""
        kwargs["graph_type"] = kwargs.get("graph_type", _GraphType.ParametricCurve)
        if len(args) == 1:
            if callable(args[0]):
                return Graph(self._impl.plot(*args, **kwargs))
            else:
                raise ValueError("Invalid arguments")
        elif len(args) == 2:
            Graph(self._impl.plot(*ensure_arrays_of_double(*args), **kwargs))
        elif len(args) == 3:
            ColorMap(self._impl.plot(*ensure_arrays_of_double(*args), **kwargs))

    def set_x_range(self, xmin: float, xmax: float):
        xmin, xmax = min(xmin, xmax), max(xmin, xmax)
        self._impl.set_x_range(xmin, xmax)

    def set_y_range(self, ymin: float, ymax: float):
        ymin, ymax = min(ymin, ymax), max(ymin, ymax)
        self._impl.set_y_range(ymin, ymax)

    @property
    def x_scale_type(self) -> ScaleType:
        return _get_axis_scale_type(self._impl.x_axis())

    @x_scale_type.setter
    def x_scale_type(self, scale_type: ScaleType):
        _set_axis_scale_type(scale_type, self._impl.x_axis())
        self.replot()

    @property
    def y_scale_type(self) -> ScaleType:
        return _get_axis_scale_type(self._impl.y_axis())

    @y_scale_type.setter
    def y_scale_type(self, scale_type: ScaleType):
        _set_axis_scale_type(scale_type, self._impl.y_axis())
        self.replot()

    def replot(self):
        self._impl.replot()

    def _repr_pretty_(self, p, cycle):
        if cycle:
            p.text("XYPlot(...)")
        else:
            p.text(f"XYPlot({self._impl})")


class TimeSeriesPlot(_BasePlot):
    def __init__(self, impl):
        super().__init__(impl)
        assert is_time_series_plot(impl)

    def plot(self, *args, **kwargs):
        if len(args) == 1:
            if callable(args[0]):
                return to_plottable(self._impl.plot(*args, **kwargs))
            else:
                return to_plottable(_plot_product(self._get_impl_or_raise(), to_product_path(args[0]), **kwargs))
        elif 3 >= len(args) >= 2:
            return to_plottable(self._get_impl_or_raise().plot(*ensure_arrays_of_double(*args), **kwargs))
        raise ValueError("Invalid arguments")

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
        self._get_impl_or_raise().y_axis().set_range(s_y_min, s_y_max)

    def set_y_scale_type(self, scale: ScaleType):
        """Set the scale type of the main y-axis.

        Args:
            scale (ScaleType): The scale type.
        """
        self.y_scale_type = scale

    @property
    def time_range(self) -> TimeRange:
        return self._get_impl_or_raise().time_axis().range()

    @time_range.setter
    def time_range(self, time_range: TimeRange):
        self._impl.set_time_range(time_range)

    @property
    def y_scale_type(self) -> ScaleType:
        return _get_axis_scale_type(self._get_impl_or_raise().y_axis())

    @y_scale_type.setter
    def y_scale_type(self, scale_type: ScaleType):
        _set_axis_scale_type(scale_type, self._get_impl_or_raise().y_axis())
        self.replot()

    def replot(self):
        self._get_impl_or_raise().replot()

    def _repr_pretty_(self, p, cycle):
        if cycle:
            p.text("TimeSeriesPlot(...)")
        else:
            p.text(f"TimeSeriesPlot({self._impl})")


class ProjectionPlot:
    def __init__(self, impl):
        assert is_projection_plot(impl)
        self._impl = impl

    def _get_impl_or_raise(self) -> _SciQLopNDProjectionPlot:
        if self._impl is None:
            raise ValueError("The plot does not exist anymore.")
        return self._impl

    def set_x_range(self, min: float, max: float):
        pass

    def set_y_range(self, min: float, max: float):
        pass

    def set_x_scale_type(self, scale: ScaleType):
        pass

    def set_y_scale_type(self, scale: ScaleType):
        pass

    def plot(self, product: Union[str, VirtualProduct], **kwargs) -> Optional[Graph]:
        return to_plottable(
            _plot_product(self._get_impl_or_raise(), to_product_path(product), graph_type=_GraphType.ParametricCurve))

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
