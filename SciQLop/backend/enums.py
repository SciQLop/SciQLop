from enum import Enum


class GraphType(Enum):
    SingleLine = 0
    MultiLines = 1
    ColorMap = 2


class DataOrder(Enum):
    X_FIRST = 0
    Y_FIRST = 1


class ParameterType(Enum):
    NONE = 0
    SCALAR = 1
    VECTOR = 2
    MULTICOMPONENT = 3
    SPECTROGRAM = 4
