from .fixtures import *
import pytest
from pytestqt import qt_compat
from pytestqt.qt_compat import qt_api
from datetime import datetime
import numpy as np
from functools import partial
from typing import Tuple

def callback(start: float, end: "float") -> Tuple["np.ndarray", "np.ndarray"]:
    x = np.linspace(start, end, int(end - start))
    y = np.sin(x)
    return x, y


def callback_dt(start: datetime, end: "datetime") -> Tuple["np.ndarray", "np.ndarray"]:
    start = datetime.timestamp(start)
    end = datetime.timestamp(end)
    x = np.linspace(start, end, int(end - start))
    y = np.sin(x)
    return x, y


def callback_dt64(start: "np.datetime64", end: np.datetime64) -> Tuple["np.ndarray", "np.ndarray"]:
    start = start.astype("datetime64[s]").astype(int)
    end = end.astype("datetime64[s]").astype(int)
    x = np.linspace(start, end, int(end - start))
    y = np.sin(x)
    return x, y


def callback_scaled(scale: float, start: float, end: "float") -> Tuple["np.ndarray", "np.ndarray"]:
    x, y = callback(start, end)
    return x, y * scale

def callback_scaled_dt(scale: float, start: datetime, end: "datetime") -> Tuple["np.ndarray", "np.ndarray"]:
    x, y = callback_dt(start, end)
    return x, y * scale

def callback_scaled_kw_dt(start: datetime, end: "datetime", scale: float=1.) -> Tuple["np.ndarray", "np.ndarray"]:
    x, y = callback_dt(start, end)
    return x, y * scale

class Functor:
    def __call__(self, start: float, end: float) -> Tuple["np.ndarray", "np.ndarray"]:
        return callback(start, end)


@pytest.mark.parametrize(
    "vp_callback",
    [
        pytest.param(callback, id="Regular callback"),
        pytest.param(lambda start, end: callback(start, end), id="lambda callback"),
        pytest.param(Functor(), id="Functor callback"),
        pytest.param(callback_dt, id="Datetime callback"),
        pytest.param(callback_dt64, id="Datetime64 callback"),
        pytest.param(partial(callback_scaled, 2.0), id="Partial function callback"),
        pytest.param(partial(callback_scaled_dt, 2.0), id="Partial function callback with datetime (positional)"),
        pytest.param(partial(callback_scaled_kw_dt, scale=2.0), id="Partial function callback with datetime (keyword argument)"),
    ]
)
def test_simple_vp(qtbot, qapp, main_window, plot_panel, vp_callback):
    assert qapp is not None
    assert main_window is not None
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType
    from SciQLop.user_api.plot import TimeRange

    # Create a virtual product
    vp = create_virtual_product(
        path="test_vp",
        callback=vp_callback,
        product_type=VirtualProductType.Scalar,
        labels=["vp"]
    )
    plot_panel.time_range = TimeRange(0., 10.)
    plt, graph = plot_panel.plot(vp)
    for i in range(10):
        qtbot.wait(10)
    x, y = graph.data
    assert len(x) > 0
    assert len(y) > 0
