from tests.helpers import *
import numpy as np
import pytest
from typing import Tuple
from datetime import datetime
from functools import partial


def _callback(start: float, end: float) -> Tuple[np.ndarray, np.ndarray]:
    x = np.linspace(start, end, int(end - start))
    y = np.sin(x)
    return x, y


def _callback_dt(start: datetime, end: datetime) -> Tuple[np.ndarray, np.ndarray]:
    start = datetime.timestamp(start)
    end = datetime.timestamp(end)
    x = np.linspace(start, end, int(end - start))
    y = np.sin(x)
    return x, y


def _callback_dt64(start: np.datetime64, end: np.datetime64) -> Tuple[np.ndarray, np.ndarray]:
    start = start.astype("datetime64[s]").astype(int)
    end = end.astype("datetime64[s]").astype(int)
    x = np.linspace(start, end, int(end - start))
    y = np.sin(x)
    return x, y


def _callback_scaled(scale: float, start: float, end: float) -> Tuple[np.ndarray, np.ndarray]:
    x, y = _callback(start, end)
    return x, y * scale


def _callback_scaled_dt(scale: float, start: datetime, end: datetime) -> Tuple[np.ndarray, np.ndarray]:
    x, y = _callback_dt(start, end)
    return x, y * scale


def _callback_scaled_kw_dt(start: datetime, end: datetime, scale: float = 1.0) -> Tuple[np.ndarray, np.ndarray]:
    x, y = _callback_dt(start, end)
    return x, y * scale


class _Functor:
    def __call__(self, start: float, end: float) -> Tuple[np.ndarray, np.ndarray]:
        return _callback(start, end)


@pytest.mark.parametrize(
    "vp_callback,name",
    [
        pytest.param(_callback, "float_cb", id="Regular callback"),
        pytest.param(lambda start, end: _callback(start, end), "lambda_cb", id="lambda callback"),
        pytest.param(_Functor(), "functor_cb", id="Functor callback"),
        pytest.param(_callback_dt, "dt_cb", id="Datetime callback"),
        pytest.param(_callback_dt64, "dt64_cb", id="Datetime64 callback"),
        pytest.param(partial(_callback_scaled, 2.0), "partial_cb", id="Partial function callback"),
        pytest.param(partial(_callback_scaled_dt, 2.0), "partial_dt_cb", id="Partial datetime callback"),
        pytest.param(partial(_callback_scaled_kw_dt, scale=2.0), "partial_kw_cb", id="Partial keyword callback"),
    ],
)
def test_virtual_product(main_window, qtbot, vp_callback, name):
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType
    from SciQLop.user_api.plot import TimeRange, create_plot_panel

    vp = create_virtual_product(
        path=f"test_vp_{name}",
        callback=vp_callback,
        product_type=VirtualProductType.Scalar,
        labels=["vp"],
    )
    panel = create_plot_panel()
    panel.time_range = TimeRange(0.0, 10.0)
    plt, graph = panel.plot(vp)
    for _ in range(10):
        qtbot.wait(10)
    x, y = graph.data
    assert len(x) > 0
    assert len(y) > 0
