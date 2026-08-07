import pytest
from SciQLop.user_api.plot.enums import GraphType, BinStrategy, GraphLineStyle, AxisType


def test_graph_type_has_waterfall():
    assert GraphType.Waterfall.value == 4


def test_bin_strategy_values():
    assert BinStrategy.Linear.value == "linear"
    assert BinStrategy.Log.value == "log"
    assert BinStrategy.SymLog.value == "symlog"


def test_graph_line_style_values():
    assert GraphLineStyle.Solid.value == 0
    assert GraphLineStyle.Dash.value == 1


def test_axis_type_values():
    assert AxisType.Linear.value == 0
    assert AxisType.Logarithmic.value == 1
