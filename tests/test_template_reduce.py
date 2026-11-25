"""A template product's ``reduce``, a list of operations ({op: mean, axis: phi, ...}): kept when a template is
read and written, v2 and v3, and applied by SciQLop before the data is drawn, each op calling the variable's
method of that name (isel, sel, sum, mean, integrate) with the other keys. A 3D particle distribution averaged
over its angles plots as an energy spectrogram. A variable without the method an op names (an older speasy)
is plotted unreduced, said once; an unknown op is an error on the graph."""
import json

import numpy as np
import pytest

from .fixtures import *  # noqa: F401,F403

REDUCE = [{"op": "mean", "axis": "phi"}, {"op": "mean", "axis": "theta", "weights": [0.25, 0.5, 0.25]}]
ENERGY = np.logspace(1, 4, 8)
SPEASY_REDUCES = hasattr(__import__("speasy.products", fromlist=["SpeasyVariable"]).SpeasyVariable, "mean")


def distribution(start: float, stop: float, cls=None):
    """A 3D distribution over (time, energy, phi, theta): each energy bin holds its own index, all angles alike."""
    from speasy.core.data_containers import DataContainer, VariableAxis, VariableTimeAxis
    from speasy.products import SpeasyVariable
    t = np.linspace(start, stop, 12)
    values = np.broadcast_to(np.arange(len(ENERGY), dtype=float)[None, :, None, None], (len(t), len(ENERGY), 4, 3))
    axes = [VariableTimeAxis(values=(t * 1e9).astype("datetime64[ns]")),
            VariableAxis(name="energy", values=ENERGY), VariableAxis(name="phi", values=np.arange(4.0)),
            VariableAxis(name="theta", values=np.arange(3.0))]
    return (cls or SpeasyVariable)(axes=axes, values=DataContainer(values=np.ascontiguousarray(values), name="dist"))


def _reducible():
    """A SpeasyVariable with the mean method a newer speasy has, for the speasy installed here, which may not."""
    from speasy.products import SpeasyVariable

    class Reducible(SpeasyVariable):
        calls = []

        def mean(self, axis, weights=None):
            from speasy.core.data_containers import DataContainer
            Reducible.calls.append(("mean", {"axis": axis} | ({"weights": weights} if weights else {})))
            dim = [a.name for a in self.axes].index(axis)
            kept = [a for i, a in enumerate(self.axes) if i != dim]
            values = np.average(self.values, axis=dim, weights=weights)
            return Reducible(axes=kept, values=DataContainer(values=values, name="omni"))

    Reducible.calls = []
    return Reducible


# ---- the template keeps it ----

def test_reduce_round_trips_in_v3_and_is_omitted_when_empty():
    from SciQLop.components.plotting.panel_template import PanelTemplate, PlotModel, ProductModel
    template = PanelTemplate(name="t", plots=[PlotModel(products=[
        ProductModel(path="speasy//cda//dist", graph_type="SciQLopColorMap", reduce=REDUCE),
        ProductModel(path="speasy//cda//b")])])
    saved = json.loads(json.dumps(template.to_tree()))
    reduced, plain = saved["panel"]["slots"]["plots"][0]["config"]["products"]
    assert reduced["reduce"] == REDUCE and "reduce" not in plain
    again = PanelTemplate.from_tree(saved)
    assert again.plots[0].products[0].reduce == REDUCE and again.plots[0].products[1].reduce == []


def test_reduce_is_read_from_a_v2_template(tmp_path):
    from SciQLop.components.plotting.panel_template import PanelTemplate
    v2 = {"version": 2, "name": "t", "plots": [{"products": [{"path": "speasy//cda//dist", "reduce": REDUCE}]}]}
    (tmp_path / "t.json").write_text(json.dumps(v2))
    template = PanelTemplate.from_file(str(tmp_path / "t.json"))
    assert template.plots[0].products[0].reduce == REDUCE
    assert template.to_tree()["panel"]["slots"]["plots"][0]["config"]["products"][0]["reduce"] == REDUCE


# ---- the data is reduced before it is drawn ----

class _Provider:
    """The DataProvider fetch path, with get_data handing back a given variable."""

    @staticmethod
    def make(variable):
        from SciQLop.components.plotting.backend.data_provider import DataProvider

        class P(DataProvider):
            def get_data(self, node, start, stop):
                return variable

            def graph_type(self, node):
                from SciQLopPlots import GraphType
                return GraphType.ColorMap
        return P.__new__(P)


def test_a_reduced_distribution_comes_out_as_an_energy_spectrogram(qapp):
    from SciQLop.components.plotting.backend.data_provider import DataProvider
    cls = _reducible()
    provider = _Provider.make(distribution(0.0, 100.0, cls))
    provider._name, provider._owns_fetched_variables = "test", False
    time, energy, values = DataProvider._get_data(provider, "dist", 0.0, 100.0, reduce=REDUCE)
    assert cls.calls == [("mean", {"axis": "phi"}), ("mean", {"axis": "theta", "weights": [0.25, 0.5, 0.25]})]
    assert list(energy) == list(ENERGY) and values.shape == (len(time), len(ENERGY))
    assert np.allclose(values[0], np.arange(len(ENERGY)))


def test_an_unknown_operation_is_an_error_on_the_graph_naming_it(qapp):
    from SciQLop.components.plotting.ui.time_sync_panel import _plot_product_callback
    provider = _Provider.make(distribution(0.0, 100.0, _reducible()))
    provider._name, provider._owns_fetched_variables = "test", False
    callback = _plot_product_callback(provider, "dist", reduce=[{"op": "mean", "axis": "phi"},
                                                                {"op": "median", "axis": "theta"}])
    assert callback(0.0, 100.0) == []
    assert "'median'" in callback.last_error and "isel, sel, sum, mean, integrate" in callback.last_error


@pytest.mark.skipif(SPEASY_REDUCES, reason="this speasy has SpeasyVariable.mean")
def test_without_reduce_in_speasy_it_is_drawn_unreduced_and_said_once(qapp):
    from SciQLop.components.plotting.backend import data_provider
    provider = _Provider.make(distribution(0.0, 100.0))
    provider._name, provider._owns_fetched_variables = "test", False
    data_provider._said_no_reduce.clear()
    logged = []
    data_provider.log.push_log.connect(logged.append)
    try:
        for _ in range(3):
            result = data_provider.DataProvider._get_data(provider, "dist", 0.0, 100.0, reduce=REDUCE)
    finally:
        data_provider.log.push_log.disconnect(logged.append)
    assert result[-1].ndim == 4
    said = [line for line in logged if "has no mean" in line]
    assert len(said) == 1 and "unreduced" in said[0]


# ---- a template plots it reduced, and saving keeps it ----

def _distribution_vp(path, cls):
    from SciQLop.user_api.virtual_products import VirtualProductType, create_virtual_product
    return create_virtual_product(path, lambda start, stop: distribution(start, stop, cls),
                                  VirtualProductType.Spectrogram, labels=["dist"])


def test_a_template_plots_its_reduced_product_as_a_spectrogram_and_saves_reduce_back(qtbot, main_window):
    from SciQLop.components.plotting.panel_introspection import plot_graphs
    from SciQLop.components.plotting.panel_template import (
        PanelTemplate, PlotModel, ProductModel, TimeRangeModel)
    cls = _reducible()
    _distribution_vp("template_reduce/dist", cls)
    template = PanelTemplate(name="omni", time_range=TimeRangeModel(start="2025-04-12T00:00:00+00:00",
                                                                     stop="2025-04-12T01:00:00+00:00"),
                             plots=[PlotModel(products=[ProductModel(path="template_reduce//dist",
                                                                     graph_type="SciQLopColorMap", reduce=REDUCE)])])
    panel = template.create_panel(main_window)
    qtbot.waitUntil(lambda: bool(cls.calls), timeout=5000)
    [graph] = [g for plot in panel.plots() for g in plot_graphs(plot) if g.property("sqp_product_path")]
    assert "ColorMap" in type(graph).__name__
    saved = PanelTemplate.from_panel(panel)
    assert saved.plots[0].products[0].reduce == REDUCE


@pytest.mark.skipif(not SPEASY_REDUCES, reason="needs a speasy with SpeasyVariable.mean")
def test_speasy_s_own_reduce_averages_the_angles(qapp):
    from SciQLop.components.plotting.backend.data_provider import DataProvider
    provider = _Provider.make(distribution(0.0, 100.0))
    provider._name, provider._owns_fetched_variables = "test", False
    time, energy, values = DataProvider._get_data(provider, "dist", 0.0, 100.0, reduce=REDUCE)
    assert list(energy) == list(ENERGY) and np.allclose(values[0], np.arange(len(ENERGY)))


def test_a_template_whose_product_cannot_be_reduced_still_opens(qtbot, main_window):
    """This speasy has no mean: the distribution reaches the spectrogram unreduced, which refuses it, and
    SciQLop goes on."""
    from SciQLop.components.plotting.backend import data_provider
    from SciQLop.components.plotting.panel_template import (
        PanelTemplate, PlotModel, ProductModel, TimeRangeModel)
    from SciQLop.user_api.virtual_products import VirtualProductType, create_virtual_product
    fetched = []

    def plain(start, stop):
        fetched.append(start)
        return distribution(start, stop)

    create_virtual_product("template_reduce/plain", plain, VirtualProductType.Spectrogram, labels=["dist"])
    data_provider._said_no_reduce.clear()
    template = PanelTemplate(name="omni", time_range=TimeRangeModel(start="2025-04-12T00:00:00+00:00",
                                                                     stop="2025-04-12T01:00:00+00:00"),
                             plots=[PlotModel(products=[ProductModel(path="template_reduce//plain",
                                                                     graph_type="SciQLopColorMap", reduce=REDUCE)])])
    panel = template.create_panel(main_window)
    qtbot.waitUntil(lambda: bool(fetched), timeout=5000)
    qtbot.wait(300)  # the refused data is handled on the next events: nothing to wait for but a short pump
    assert len(panel.plots()) == 1 and template.not_found == []
