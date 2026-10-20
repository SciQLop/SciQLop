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


def _product_graphs(panel_impl):
    from SciQLop.components.plotting.panel_introspection import plot_graphs
    return [g for plot in panel_impl.plots() for g in plot_graphs(plot) if g.property("sqp_product_path")]


def test_shifted_graph_legend_says_it_is_shifted(plot_panel, qtbot):
    from SciQLop.core.graph_context import graph_name
    vp = _vp("test_time_offset/legend", [])
    plot_panel.time_range = TimeRange(1000.0, 2000.0)
    plot_panel.plot_product(vp, time_offset=DAY)
    plot_panel.plot_product(vp, plot_index=0)
    names = sorted(graph_name(g) for g in _product_graphs(plot_panel._get_impl_or_raise()))
    assert names == ["legend", "legend (+1 day, 0:00:00)"]


def test_time_offset_round_trips_through_a_template(main_window, plot_panel, qtbot, tmp_path):
    from SciQLop.components.plotting.panel_template import PanelTemplate
    vp = _vp("test_time_offset/template", [])
    plot_panel.time_range = TimeRange(1000.0, 2000.0)
    plot_panel.plot_product(vp, time_offset=DAY)
    template = PanelTemplate.from_panel(plot_panel._get_impl_or_raise())
    assert [p.time_offset for p in template.plots[0].products] == [DAY]
    template.to_file(str(tmp_path / "shifted.json"))
    restored = PanelTemplate.from_file(str(tmp_path / "shifted.json")).create_panel(main_window)
    try:
        graphs = _product_graphs(restored)
        assert len(graphs) == 1 and graphs[0].property("sqp_time_offset") == DAY
        assert [p.time_offset for p in PanelTemplate.from_panel(restored).plots[0].products] == [DAY]
    finally:
        main_window.remove_panel(restored)


def test_zero_time_offset_is_omitted_without_pydantic_exclude_if():
    """exclude_if needs pydantic >= 2.12, which the project does not pin."""
    from SciQLop.components.plotting.panel_template import ProductModel
    assert getattr(ProductModel.model_fields["time_offset"], "exclude_if", None) is None
    assert "time_offset" not in ProductModel(path="a//b").model_dump()
    assert "time_offset" not in ProductModel(path="a//b").model_dump(mode="json")
    assert ProductModel(path="a//b", time_offset=DAY).model_dump()["time_offset"] == DAY
    assert ProductModel.model_validate_json(ProductModel(path="a", time_offset=DAY).model_dump_json()).time_offset == DAY
