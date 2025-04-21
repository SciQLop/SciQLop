from enum import Enum


class PlotType(Enum):
    TimeSeries = 0
    Projection = 1
    XY = 2

class GraphType(Enum):
    """
    GraphType enum for the plot.
    It defines the type of graph to be used in the plot.
    - Line: A line graph where there is only one Y value for each X value and the X values are sorted. This allows optimization of the graph.
    - Curve: A curve graph where there can be multiple Y values for each X value. This allows for more complex graphs, but is less optimized.
    - ColorMap: A color map graph where the Z values are represented by colors.
    - Scatter: A scatter plot where the X and Y values are represented by points. This is useful for visualizing data that does not follow a specific pattern
    """
    Line = 0
    Curve = 1
    ColorMap = 2
    Scatter = 3

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
