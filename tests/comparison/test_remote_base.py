"""A comparison whose base product really goes through plot_remote (out_of_process), not a patched is_remote."""
from datetime import datetime, timezone

import numpy as np
import pytest

from ..fixtures import *  # noqa: F401, F403
from SciQLop.components.comparison.backend.dimensions import contribute_core_dimensions, resolve_sides
from SciQLop.components.comparison.backend.model import Comparison, Variant
from SciQLop.components.plotting.panel_template import PanelTemplate, PlotModel, ProductModel, TimeRangeModel

BASE_RANGE = (1_000.0, 1_100.0)


def _remote_source(start: float, stop: float):
    t = np.linspace(start, stop, 16)
    return t, np.sin(t)


@pytest.fixture(autouse=True)
def core_dimensions():
    contribute_core_dimensions()


@pytest.fixture(autouse=True)
def _isolate_remote_registry(monkeypatch):
    import SciQLop.components.plotting.backend.remote.registry as reg_mod
    monkeypatch.setenv("SPEASY_CORE_DISABLED_PROVIDERS", "amda,archive,cda,cdpp3dview,csa,ssc,uiowaephtool")
    old = reg_mod._REGISTRY
    reg_mod._REGISTRY = None
    yield
    if reg_mod._REGISTRY is not None:
        reg_mod._REGISTRY.shutdown_all()
    reg_mod._REGISTRY = old


def _iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat()


def _remote_product(name: str) -> str:
    from SciQLop.components.plotting.backend.easy_provider import EasyScalar
    EasyScalar(path=f"test_cmp_remote/{name}", get_data_callback=_remote_source, component_name="y",
               metadata={}, out_of_process=True)
    return f"test_cmp_remote//{name}"


def _local_product(name: str) -> str:
    from SciQLop.user_api.plot._plots import to_product_path
    from SciQLop.user_api.virtual_products import VirtualProductType, create_virtual_product
    vp = create_virtual_product(f"test_cmp_remote_local/{name}", _remote_source, VirtualProductType.Scalar,
                                labels=["y"])
    return "//".join(to_product_path(vp))


def _comparison(path, dimension, variants):
    template = PanelTemplate(name="P", time_range=TimeRangeModel(start=_iso(BASE_RANGE[0]), stop=_iso(BASE_RANGE[1])),
                             plots=[PlotModel(products=[ProductModel(path=path)])])
    return Comparison(base=template.to_tree(), dimension=dimension, variants=list(variants))


def _overlay_text(plot):
    from SciQLop.components.plotting.ui.diagnostic_overlay import overlay_of
    return overlay_of(plot).text()


def test_remote_base_graph_carries_its_product_path(main_window, qtbot):
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel, plot_product
    from SciQLop.core import TimeRange
    path = _remote_product("path_prop")
    panel = TimeSyncPanel("remote", time_range=TimeRange(*BASE_RANGE))
    qtbot.addWidget(panel)
    _plot, graph = plot_product(panel, path.split("//"))
    assert graph.property("sqp_product_path") == path


def test_overlay_refuses_a_shifted_remote_ghost_with_a_note(main_window, qtbot):
    from SciQLop.components.comparison.ui.overlay_view import build_overlay
    comparison = _comparison(_remote_product("overlay"), "time",
                             [Variant(label="event 0", params={"start": 2_000.0, "stop": 2_100.0})])
    panel = build_overlay(comparison, resolve_sides(comparison), {}, None, None)
    qtbot.addWidget(panel)
    assert "event 0: not overlaid — remote products cannot be shifted in time yet" in _overlay_text(panel.plots()[0])


def test_difference_refuses_a_remote_base_with_a_message(main_window, qtbot):
    from SciQLop.components.comparison.ui.difference_view import build_difference, default_options
    comparison = _comparison(_remote_product("difference"), "product",
                             [Variant(label="other", params={"target": [0, 0], "path": _local_product("b")})])
    panel = build_difference(comparison, resolve_sides(comparison), dict(default_options), None, None)
    qtbot.addWidget(panel)
    assert len(panel.plots()) == 2
    assert "remote products are not supported in the Difference view" in _overlay_text(panel.plots()[1])
