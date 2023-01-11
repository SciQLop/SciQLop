from enum import Enum


class GraphType(Enum):
    SingleLine = 0
    MultiLines = 1
    ColorMap = 2


class DataOrder(Enum):
    X_FIRST = 0
    Y_FIRST = 1
