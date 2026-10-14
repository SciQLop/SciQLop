"""panel.add(kind, **config): one call builds any plot kind, the same path templates and plugins use (spec §5)."""
import pytest

from .fixtures import *  # noqa: F401,F403 — main_window
from SciQLop.core.extensions import NotRegistered, owned_by
from SciQLop.core.plot_kinds import PLOT_KINDS, PlotKind


@pytest.fixture
def panel(qtbot, main_window):
    from SciQLop.user_api.plot import create_plot_panel
    return create_plot_panel()


def test_add_builds_a_plugin_plot_kind_from_its_config(panel):
    got = []
    with owned_by("pa_demo"):
        PLOT_KINDS.contribute(PlotKind("pa_demo.slice_plot", "Slice", plot_product=lambda *a: None,
                                       from_config=lambda p, config: got.append(config) or "slice"))
    try:
        assert panel.add("pa_demo.slice_plot", plane="XY") == "slice"
        assert got == [{"plane": "XY"}]
    finally:
        PLOT_KINDS.remove_owner("pa_demo")


def test_add_unknown_kind_names_the_available_ones(panel):
    with pytest.raises(NotRegistered, match="sciqlop.timeseries"):
        panel.add("pa_nowhere.plot")


def test_add_kind_without_from_config_is_a_value_error(panel):
    with owned_by("pa_demo"):
        PLOT_KINDS.contribute(PlotKind("pa_demo.view_only", "View", plot_product=lambda *a: None))
    try:
        with pytest.raises(ValueError, match="pa_demo.view_only"):
            panel.add("pa_demo.view_only")
    finally:
        PLOT_KINDS.remove_owner("pa_demo")


@pytest.fixture
def scalar_vp(main_window, simple_vp_callback):
    from SciQLop.user_api.virtual_products import VirtualProductType, create_virtual_product
    return create_virtual_product("pa_add/scalar", simple_vp_callback, VirtualProductType.Scalar, labels=["y"])


@pytest.mark.parametrize("config", [lambda path: {"product": path}, lambda path: {"products": [path]},
                                    lambda path: {"products": [{"path": path}]}])
def test_add_time_series_plots_the_product_it_is_given(panel, scalar_vp, config):
    from SciQLop.user_api.plot import TimeSeriesPlot
    plot = panel.add("sciqlop.timeseries", **config("//".join(scalar_vp.path.split("/"))))
    assert isinstance(plot, TimeSeriesPlot)
    assert len(plot.graphs) == 1


def test_add_time_series_with_an_unknown_key_raises(panel, scalar_vp):
    with pytest.raises(ValueError, match="produt"):
        panel.add("sciqlop.timeseries", produt="x")
