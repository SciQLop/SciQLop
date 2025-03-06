from enum import Enum
from SciQLopPlots import ParameterType

class GraphType(Enum):
    SingleLine = 0
    MultiLines = 1
    ColorMap = 2
    Unknown = -1


def graph_type_repr(graph_type: GraphType) -> str:
    return {
        GraphType.SingleLine: "Single Line Graph",
        GraphType.MultiLines: "Multi-lines Graph",
        GraphType.ColorMap: "Colormap Graph",
        GraphType.Unknown: "Unknown Graph Type"
    }.get(graph_type, "Unknown Graph Type")


class DataOrder(Enum):
    X_FIRST = 0
    Y_FIRST = 1


