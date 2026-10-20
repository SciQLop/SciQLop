"""Product graphs drawn shifted in time (ghost curves for plot comparison)."""
from .fixtures import *
import numpy as np
import pytest

from SciQLop.components.plotting.ui.time_sync_panel import shift_buffers
from SciQLop.core import TimeRange

DAY = 86400.0


def test_shift_buffers_subtracts_offset_without_mutating():
    t = np.array([10.0, 20.0]); y = np.array([1.0, 2.0])
    out = shift_buffers([t, y], 5.0)
    assert list(out[0]) == [5.0, 15.0] and list(t) == [10.0, 20.0]
    assert out[1] is y


def test_shift_buffers_handles_colored_and_empty():
    t = np.array([10.0]); out = shift_buffers({"data": [t, t], "color": "c"}, 1.0)
    assert list(out["data"][0]) == [9.0] and out["color"] == "c"
    assert shift_buffers([], 1.0) == []


def _vp(path, seen):
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType

    def cb(start, stop):
        seen.append((start, stop))
        x = np.linspace(start, stop, 10)
        return x, x * 0
    return create_virtual_product(path, cb, VirtualProductType.Scalar, labels=["y"])


def test_time_offset_fetches_shifted_window(plot_panel, qtbot):
    seen = []
    vp = _vp("test_time_offset/vp", seen)
    plot_panel.time_range = TimeRange(1000.0, 2000.0)
    plot_panel.plot_product(vp, time_offset=DAY)
    qtbot.waitUntil(lambda: bool(seen))
    start, stop = seen[-1]
    assert start <= 1000.0 + DAY and stop >= 2000.0 + DAY
    assert start > DAY


def _notices(plot_panel):
    from SciQLop.components.plotting.ui.coverage_notice import CoverageNotice
    return plot_panel._get_impl_or_raise().findChildren(CoverageNotice)


def _cover_only_shifted_window(monkeypatch, vp):
    from SciQLopPlots import ProductsModel
    from SciQLop.components.plotting.backend.data_provider import providers
    from SciQLop.user_api.plot._plots import to_product_path
    node = ProductsModel.node(to_product_path(vp))
    monkeypatch.setattr(providers[node.provider()], "coverage",
                        lambda _node: TimeRange(1000.0 + DAY, 2000.0 + DAY), raising=False)


@pytest.mark.parametrize("offset, expect_notice", [(0.0, True), (DAY, False)])
def test_shifted_graph_does_not_offer_jump_to_data(plot_panel, qtbot, monkeypatch, offset, expect_notice):
    vp = _vp(f"test_time_offset/cov{int(offset)}", [])
    _cover_only_shifted_window(monkeypatch, vp)
    plot_panel.time_range = TimeRange(1000.0, 2000.0)
    plot_panel.plot_product(vp, time_offset=offset)
    if expect_notice:
        qtbot.waitUntil(lambda: bool(_notices(plot_panel)))
    else:
        qtbot.wait(100)  # negative case: nothing to wait for, only a short pump
        assert not _notices(plot_panel)
