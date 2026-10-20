from datetime import datetime, timezone

import numpy as np
import pytest

from ..fixtures import *  # noqa: F401, F403
from SciQLop.components.comparison.backend.dimensions import contribute_core_dimensions, resolve_sides
from SciQLop.components.comparison.backend.model import Comparison, Variant
from SciQLop.components.plotting.panel_template import PanelTemplate, PlotModel, ProductModel, TimeRangeModel
from SciQLop.core.graph_context import graph_name
from SciQLop.core.plot_hints import AxisHints, PlotHints

BASE_RANGE = (1_000.0, 1_100.0)
FILL = -1e31


@pytest.fixture(autouse=True)
def core_dimensions():
    contribute_core_dimensions()


def _iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat()


def _vp(name, callback, kind=None, labels=("y",)):
    from SciQLop.user_api.plot._plots import to_product_path
    from SciQLop.user_api.virtual_products import VirtualProductType, create_virtual_product
    vp = create_virtual_product(f"test_diff/{name}", callback, kind or VirtualProductType.Scalar,
                                labels=list(labels) if kind is None else None)
    return vp, "//".join(to_product_path(vp))


def _gain_vp(name):
    def ones(start: float, stop: float, gain: float = 1.0):
        x = np.linspace(start, stop, 50)
        return x, np.full(len(x), gain)
    return _vp(name, ones)


def _template(*plots):
    return PanelTemplate(name="P", time_range=TimeRangeModel(start=_iso(BASE_RANGE[0]), stop=_iso(BASE_RANGE[1])),
                         plots=[PlotModel(products=list(products)) for products in plots])


def _comparison(template, dimension, variants):
    return Comparison(base=template.to_tree(), dimension=dimension, variants=list(variants))


def _settings_comparison(path, base_knobs, variant_knobs, is_colormap=False):
    template = _template([ProductModel(path=path, knobs=base_knobs, graph_type="SciQLopColorMap" if is_colormap else "")])
    return _comparison(template, "settings", [Variant(label="v", params={"target": [0, 0], "knobs": variant_knobs})])


def _product_comparison(path_a, path_b):
    return _comparison(_template([ProductModel(path=path_a)]), "product",
                       [Variant(label="other", params={"target": [0, 0], "path": path_b})])


def _build(comparison, qtbot, options=None):
    from SciQLop.components.comparison.ui.difference_view import build_difference, default_options
    panel = build_difference(comparison, resolve_sides(comparison), options or dict(default_options), None, None)
    qtbot.addWidget(panel)
    return panel


def _graphs(plot):
    from SciQLop.components.plotting.panel_introspection import plot_graphs
    return plot_graphs(plot)


def _buffers(graph):
    data = graph.data() or []
    return [np.empty(0) if b is None else np.asarray(b) for b in data] or [np.empty(0)] * 3


def _y_values(graph):
    return _buffers(graph)[1]


def _overlay_text(plot):
    from SciQLop.components.plotting.ui.diagnostic_overlay import overlay_of
    return overlay_of(plot).text()


def test_difference_adds_a_relation_row_after_each_changed_plot(main_window, qtbot):
    _, path = _gain_vp("gain")
    panel = _build(_settings_comparison(path, {"gain": 1.0}, {"gain": 3.0}), qtbot)
    qtbot.waitUntil(lambda: len(panel.plots()) == 2)
    assert panel.plots()[1].metaObject().className() == "SciQLopTimeSeriesPlot"
    assert len(_graphs(panel.plots()[0])) == 2
    rel = _graphs(panel.plots()[1])[0]
    assert graph_name(rel).endswith(": A − B")
    qtbot.waitUntil(lambda: _y_values(rel).size > 0)
    assert np.allclose(_y_values(rel), -2.0)


def test_each_relation_row_follows_its_base_plot(main_window, qtbot):
    _, path_a = _gain_vp("first")
    _, path_b = _gain_vp("second")
    template = _template([ProductModel(path=path_a)], [ProductModel(path=path_b)])
    comparison = _comparison(template, "time", [Variant(label="later", params={"start": 2_000.0, "stop": 2_100.0})])
    panel = _build(comparison, qtbot)
    qtbot.waitUntil(lambda: len(panel.plots()) == 4)
    first = [graph_name(_graphs(p)[0]) for p in panel.plots()]
    assert first[1] == f"{first[0]}: A − B"
    assert first[3] == f"{first[2]}: A − B"


def test_ratio_operation_and_unknown_operation_falls_back(main_window, qtbot, caplog):
    _, path = _gain_vp("ratio")
    comparison = _settings_comparison(path, {"gain": 1.0}, {"gain": 4.0})
    rel = _graphs(_build(comparison, qtbot, {"operation": "ratio", "method": "linear"}).plots()[1])[0]
    assert graph_name(rel).endswith(": A / B")
    qtbot.waitUntil(lambda: _y_values(rel).size > 0)
    assert np.allclose(_y_values(rel), 0.25)
    rel = _graphs(_build(comparison, qtbot, {"operation": "bogus", "method": "linear"}).plots()[1])[0]
    assert graph_name(rel).endswith(": A − B")
    assert "bogus" in caplog.text


def test_difference_not_applicable_with_three_sides():
    from SciQLop.components.comparison.ui.difference_view import applies_difference
    template = _template([ProductModel(path="a//b")])
    three = _comparison(template, "time", [Variant(label=f"e{i}", params={"start": s, "stop": s + 100.0})
                                           for i, s in enumerate((2_000.0, 3_000.0))])
    assert applies_difference(three, resolve_sides(three)) == "Difference needs exactly two sides"
    same = _comparison(template, "settings", [Variant(label="v", params={"target": [0, 0], "knobs": {}})])
    assert applies_difference(same, resolve_sides(same)) == "nothing differs between the sides"
    two = _comparison(template, "time", [Variant(label="e", params={"start": 2_000.0, "stop": 2_100.0})])
    assert applies_difference(two, resolve_sides(two)) is None


def test_difference_masks_fill_values(main_window, qtbot):
    def holes(start: float, stop: float, gain: float = 1.0):
        x = np.linspace(start, stop, 50)
        y = np.full(len(x), gain)
        if gain != 1.0:
            y[::2] = FILL
        return x, y

    _, path = _vp("holes", holes)
    rel = _graphs(_build(_settings_comparison(path, {"gain": 1.0}, {"gain": 3.0}), qtbot).plots()[1])[0]
    qtbot.waitUntil(lambda: _y_values(rel).size > 0)
    y = _y_values(rel).ravel()
    assert np.isnan(y[::2]).all()
    assert np.allclose(y[1::2], -2.0)


def _spectrogram_vp(name):
    from SciQLop.user_api.virtual_products import VirtualProductType

    def descending(start: float, stop: float, gain: float = 1.0):
        x = np.linspace(start, stop, 20)
        y = np.array([100.0, 10.0, 1.0])
        return x, y, np.ones((len(x), 1)) * y[None, :] ** gain

    return _vp(name, descending, VirtualProductType.Spectrogram)


def test_spectrogram_relation_keeps_base_orientation(main_window, qtbot):
    from SciQLopPlots import ColorGradient
    _, path = _spectrogram_vp("spec")
    panel = _build(_settings_comparison(path, {"gain": 1.0}, {"gain": 3.0}, is_colormap=True), qtbot)
    qtbot.waitUntil(lambda: len(panel.plots()) == 2)
    assert len(_graphs(panel.plots()[0])) == 1
    rel = _graphs(panel.plots()[1])[0]
    assert graph_name(rel).endswith(": log₁₀(A / B)")
    qtbot.waitUntil(lambda: _buffers(rel)[0].size > 0)
    _, y, z = _buffers(rel)
    assert np.all(np.diff(y) > 0)
    assert np.allclose(z.reshape(-1, 3)[0], [0.0, -2.0, -4.0])
    assert rel.gradient() == ColorGradient.Coolwarm
    assert not rel.z_log_scale()
    z_axis = panel.plots()[1].z_axis()
    qtbot.waitUntil(lambda: z_axis.range().stop() > 0
                    and np.isclose(z_axis.range().start(), -z_axis.range().stop()))


def _speasy_vp(name, unit):
    from speasy.core import epoch_to_datetime64
    from speasy.core.data_containers import DataContainer
    from speasy.products import SpeasyVariable, VariableTimeAxis

    def with_unit(start: float, stop: float) -> SpeasyVariable:
        t = np.linspace(start, stop, 50)
        return SpeasyVariable(axes=[VariableTimeAxis(values=epoch_to_datetime64(t))],
                              values=DataContainer(values=np.sin(t)[:, None], meta={"UNITS": unit}, name=name),
                              columns=["y"])

    return _vp(name, with_unit)


def test_relation_refuses_fetched_units_that_differ(main_window, qtbot):
    _, nT = _speasy_vp("diff_nT", "nT")
    _, mV = _speasy_vp("diff_mV", "mV")
    panel = _build(_product_comparison(nT, mV), qtbot)
    qtbot.waitUntil(lambda: len(panel.plots()) == 2)
    rel_plot = panel.plots()[1]
    qtbot.waitUntil(lambda: "different units: nT vs mV" in _overlay_text(rel_plot))


def test_static_mismatch_is_shown_instead_of_a_relation(main_window, qtbot, monkeypatch):
    nT, nT_path = _gain_vp("static_nT")
    mV, mV_path = _gain_vp("static_mV")
    monkeypatch.setattr(nT._impl, "plot_hints", lambda node: PlotHints(y=AxisHints(unit="nT")), raising=False)
    monkeypatch.setattr(mV._impl, "plot_hints", lambda node: PlotHints(y=AxisHints(unit="mV")), raising=False)
    panel = _build(_product_comparison(nT_path, mV_path), qtbot)
    assert len(panel.plots()) == 2
    assert _graphs(panel.plots()[1]) == []
    assert "different units: nT vs mV" in _overlay_text(panel.plots()[1])


def test_remote_products_are_refused(main_window, qtbot, monkeypatch):
    from SciQLop.components.comparison.ui import difference_view
    _, path = _gain_vp("remote")
    monkeypatch.setattr(difference_view, "is_remote", lambda p: True)
    panel = _build(_settings_comparison(path, {"gain": 1.0}, {"gain": 3.0}), qtbot)
    assert _graphs(panel.plots()[1]) == []
    assert "remote products are not supported in the Difference view" in _overlay_text(panel.plots()[1])


def _axis_label(axis):
    return axis.label()


def _with_hints(monkeypatch, vp, hints):
    monkeypatch.setattr(vp._impl, "plot_hints", lambda node: hints, raising=False)


LOG_LINE_HINTS = PlotHints(y=AxisHints(label="B", unit="nT", scale="log", valid_range=(0.1, 10.0)), fill_value=FILL)


@pytest.mark.parametrize("operation, label", [("difference", "A − B B [nT]"), ("ratio", "A / B B")])
def test_line_relation_axis_is_linear_and_named_after_the_operation(main_window, qtbot, monkeypatch,
                                                                     operation, label):
    vp, path = _gain_vp(f"log_line_{operation}")
    _with_hints(monkeypatch, vp, LOG_LINE_HINTS)
    panel = _build(_settings_comparison(path, {"gain": 1.0}, {"gain": 3.0}), qtbot,
                   {"operation": operation, "method": "linear"})
    rel_plot = panel.plots()[1]
    assert not rel_plot.y_axis().log()
    assert _axis_label(rel_plot.y_axis()) == label


LOG_SPECTRO_HINTS = PlotHints(display_type="spectrogram", z=AxisHints(label="flux", unit="cm-3", scale="log"),
                              y2=AxisHints(label="E", unit="eV", scale="log"))


def test_spectrogram_relation_z_axis_is_linear_and_unitless(main_window, qtbot, monkeypatch):
    vp, path = _spectrogram_vp("log_spec")
    _with_hints(monkeypatch, vp, LOG_SPECTRO_HINTS)
    panel = _build(_settings_comparison(path, {"gain": 1.0}, {"gain": 3.0}, is_colormap=True), qtbot)
    rel_plot = panel.plots()[1]
    rel = _graphs(rel_plot)[0]
    assert not rel_plot.z_axis().log()
    assert _axis_label(rel_plot.z_axis()) == "log₁₀(A / B) flux"
    qtbot.waitUntil(lambda: _buffers(rel)[0].size > 0)
    z_axis = rel_plot.z_axis()
    qtbot.waitUntil(lambda: z_axis.range().stop() > 0
                    and np.isclose(z_axis.range().start(), -z_axis.range().stop()))
    assert not z_axis.log()


@pytest.mark.parametrize("base_log", [True, False])
def test_spectrogram_relation_y_scale_follows_the_base_plot(main_window, qtbot, base_log):
    from SciQLop.components.plotting.panel_template import AxisModel
    _, path = _spectrogram_vp(f"y_scale_{base_log}")
    product = ProductModel(path=path, knobs={"gain": 1.0}, graph_type="SciQLopColorMap")
    axes = {} if base_log else {"y_axis": AxisModel(log=False), "y2_axis": AxisModel(log=False)}
    template = _template([product])
    template.plots[0] = PlotModel(products=[product], **axes)
    comparison = _comparison(template, "settings",
                             [Variant(label="v", params={"target": [0, 0], "knobs": {"gain": 3.0}})])
    panel = _build(comparison, qtbot)
    base, rel = _graphs(panel.plots()[0])[0], _graphs(panel.plots()[1])[0]
    assert bool(base.y_axis().log()) is base_log
    assert bool(rel.y_axis().log()) is base_log


def test_spectrogram_and_line_sides_are_refused(main_window, qtbot):
    _, line = _gain_vp("mixed_line")
    _, spec = _spectrogram_vp("mixed_spec")
    comparison = _comparison(_template([ProductModel(path=line)]), "product",
                             [Variant(label="spec", params={"target": [0, 0], "path": spec, "is_colormap": True})])
    panel = _build(comparison, qtbot)
    assert _graphs(panel.plots()[1]) == []
    assert "cannot relate a spectrogram to a line plot" in _overlay_text(panel.plots()[1])


def test_descending_bins_relation_row_lines_up_with_the_base_row(main_window, qtbot):
    _, path = _spectrogram_vp("descending_rows")
    panel = _build(_settings_comparison(path, {"gain": 1.0}, {"gain": 3.0}, is_colormap=True), qtbot)
    base, rel = _graphs(panel.plots()[0])[0], _graphs(panel.plots()[1])[0]
    qtbot.waitUntil(lambda: _buffers(base)[0].size > 0 and _buffers(rel)[0].size > 0)
    y_base, y_rel = (np.asarray(_buffers(g)[1]).reshape(-1, 3)[0] for g in (base, rel))
    assert np.allclose(y_base, y_rel)
    z_base, z_rel = (np.asarray(_buffers(g)[2]).reshape(-1, 3)[0] for g in (base, rel))
    assert np.allclose(z_base, y_base) and np.allclose(z_rel, -2 * np.log10(y_base))


def test_keep_symmetric_applies_to_the_range_the_axis_already_has(main_window, qtbot):
    from SciQLopPlots import SciQLopPlotRange
    from SciQLop.components.comparison.ui.difference_view import _keep_symmetric
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel, plot_product
    from SciQLop.core import TimeRange
    panel = TimeSyncPanel("sym", time_range=TimeRange(*BASE_RANGE))
    qtbot.addWidget(panel)
    _, path = _gain_vp("symmetric")
    plot, _ = plot_product(panel, path.split("//"))
    axis = plot.y_axis()
    axis.set_range(SciQLopPlotRange(1.0, 5.0))
    _keep_symmetric(axis)
    assert (axis.range().start(), axis.range().stop()) == pytest.approx((-5.0, 5.0))
