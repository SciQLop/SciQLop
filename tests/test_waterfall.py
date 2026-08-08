import numpy as np
import pytest
from .fixtures import *
from SciQLop.user_api.plot.enums import GraphType


@pytest.fixture
def waterfall_data():
    x = np.linspace(0, 10, 50)
    y = np.linspace(0, 5, 10)
    z = np.sin(x) * np.exp(-y[:, None])
    return x, y, z


def test_panel_waterfall_returns_wrapper(waterfall_data, plot_panel):
    x, y, z = waterfall_data
    wf = plot_panel.waterfall(x, y, z)
    assert wf is not None


def test_waterfall_shape_validation(waterfall_data, plot_panel):
    x, y, z = waterfall_data
    with pytest.raises(ValueError):
        plot_panel.waterfall(x, y, z[:-1])  # wrong y length


def test_waterfall_omnibus_dispatcher(waterfall_data, plot_panel):
    x, y, z = waterfall_data
    wf = plot_panel.plot(x, y, z, graph_type=GraphType.Waterfall)
    assert wf is not None


def test_waterfall_setters(waterfall_data, plot_panel):
    x, y, z = waterfall_data
    wf = plot_panel.waterfall(x, y, z)
    wf.gain = 2.0
    wf.normalize = True
    assert wf.gain == 2.0
    assert wf.normalize is True
