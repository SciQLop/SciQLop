from enum import Enum


class PlotType(Enum):
    TimeSeries = 0
    Projection = 1
    XY = 2


class ScaleType(Enum):
    Linear = 0
    Logarithmic = 1


class CoordinateSystem(Enum):
    Pixel = 0
    Data = 1


class Orientation(Enum):
    Horizontal = 0
    Vertical = 1


class Observables(Enum):
    Nothing = 0
    TimeRange = 1
    Data = 2
    XAxis = 3
    YAxis = 4
