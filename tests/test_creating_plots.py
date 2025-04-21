from .fixtures import *
import pytest
from pytestqt import qt_compat
from pytestqt.qt_compat import qt_api
from datetime import datetime
import numpy as np
from functools import partial
from typing import Tuple


def test_create_panel(qtbot, qapp, main_window):
    assert qapp is not None
    assert main_window is not None
    from SciQLop.user_api.plot import create_plot_panel
    plot_panel = create_plot_panel()
    assert plot_panel is not None
    assert plot_panel._impl is not None


@pytest.mark.parametrize(
    "plot_args,plot_kwargs",
    [
        pytest.param([[1, 2, 3], [1, 2, 3]], {}, id="simple static data plot"),
        pytest.param(["TestPlugin//TestMultiComponent"], {}, id="simple product plot"),
    ]
)
def test_create_plot(qtbot, qapp, main_window, plot_panel, plot_args, plot_kwargs):
    assert qapp is not None
    assert main_window is not None
    plot, graph = plot_panel.plot(*plot_args, **plot_kwargs)
    assert plot is not None
    assert graph is not None
    for i in range(3):
        qtbot.wait(1)
    assert len(graph.data[0])
