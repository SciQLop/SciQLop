from typing import Protocol, Tuple
from .enums import ScaleType, PlotType, CoordinateSystem


class Item(Protocol):

    @property
    def visible(self) -> bool:
        pass

    @property
    def position(self) -> Tuple[float, float]:
        pass

    @property
    def coordinate_system(self) -> CoordinateSystem:
        pass


class Plottable(Protocol):

    @property
    def data(self) -> Tuple:
        pass

    @property
    def visible(self) -> bool:
        pass


class Plot(Protocol):

    def _get_impl_or_raise(self):
        pass

    def plot(self, *args, **kwargs):
        pass

    def replot(self):
        pass

    def set_x_range(self, xmin: float, xmax: float):
        pass

    def set_y_range(self, ymin: float, ymax: float):
        pass

    @property
    def x_scale_type(self) -> ScaleType:
        pass

    @property
    def y_scale_type(self) -> ScaleType:
        pass

    @property
    def plot_type(self) -> PlotType:
        pass
