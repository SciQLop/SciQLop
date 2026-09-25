import numpy as np
import pytest

from tests.helpers import *  # noqa: F401,F403
from SciQLop.user_api.data_types import Colored


def _colored_source(start: float, stop: float):
    t = np.linspace(start, stop, 16)
    return Colored((t, np.column_stack([t, t, t])), color=np.linspace(1.0, 2.0, 16))


@pytest.fixture(autouse=True)
def _isolate_registry():
    import SciQLop.components.plotting.backend.remote.registry as reg_mod
    old = reg_mod._REGISTRY
    reg_mod._REGISTRY = None
    yield
    if reg_mod._REGISTRY is not None:
        try:
            reg_mod._REGISTRY.shutdown_all()
        except Exception:
            pass
    reg_mod._REGISTRY = old


def test_reduce_result_appends_the_colour():
    from SciQLop.components.plotting.backend.remote.reduction import reduce_result
    arrays = reduce_result(_colored_source(0.0, 1.0), 2)
    assert len(arrays) == 3
    assert np.array_equal(arrays[2], np.linspace(1.0, 2.0, 16))


def test_reduce_result_sorts_the_colour_with_the_data():
    from SciQLop.components.plotting.backend.remote.reduction import reduce_result
    t = np.array([3.0, 1.0, 2.0])
    arrays = reduce_result(Colored((t, np.zeros((3, 3))), color=np.array([30.0, 10.0, 20.0])), 2)
    assert np.array_equal(arrays[2], [10.0, 20.0, 30.0])


def _z_range(plot):
    r = plot.z_axis().range()
    return r.start(), r.stop()


def test_remote_colored_vector_is_coloured_and_not_left_busy(qtbot, main_window):
    from SciQLop.components.plotting.backend.easy_provider import EasyVector
    from SciQLop.components.plotting.backend.color_axis import ColorAxis
    from SciQLop.components.plotting.ui.time_sync_panel import plot_product
    from SciQLop.user_api.plot import create_plot_panel
    EasyVector(path="colored_remote/vec", get_data_callback=_colored_source,
               components_names=["x", "y", "z"], metadata={}, out_of_process=True,
               color_axis=ColorAxis(label="c"))
    panel = create_plot_panel()
    panel.time_range = (1_700_000_000.0, 1_700_000_100.0)
    plot, graph = plot_product(panel._impl, ["colored_remote", "vec"])
    qtbot.waitUntil(lambda: _z_range(plot) == pytest.approx((1.0, 2.0)), timeout=15000)
    qtbot.waitUntil(lambda: not graph.busy(), timeout=5000)
    assert plot.z_axis().label() == "c"
