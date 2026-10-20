from datetime import datetime, timezone

import numpy as np
import pytest

from ..fixtures import *  # noqa: F401, F403
from SciQLop.components.comparison.backend.dimensions import contribute_core_dimensions, resolve_sides
from SciQLop.components.comparison.backend.model import Comparison, Variant
from SciQLop.components.plotting.panel_template import PanelTemplate, PlotModel, ProductModel, TimeRangeModel
from SciQLop.core.plot_hints import AxisHints, PlotHints
from SciQLop.core.graph_context import graph_name

BASE_RANGE = (1_000.0, 1_100.0)


@pytest.fixture(autouse=True)
def core_dimensions():
    contribute_core_dimensions()


def _iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat()


def _vp(name, callback=None, labels=("y",)):
    from SciQLop.user_api.plot._plots import to_product_path
    from SciQLop.user_api.virtual_products import VirtualProductType, create_virtual_product

    def sine(start: float, stop: float):
        x = np.linspace(start, stop, 50)
        return x, np.column_stack([np.sin(x) * (i + 1) for i in range(len(labels))])

    kind = VirtualProductType.Scalar if len(labels) == 1 else VirtualProductType.MultiComponent
    vp = create_virtual_product(f"test_cmp/{name}", callback or sine, kind, labels=list(labels))
    return vp, "//".join(to_product_path(vp))


def _comparison(path, dimension="time", variants=()):
    template = PanelTemplate(name="P", time_range=TimeRangeModel(start=_iso(BASE_RANGE[0]), stop=_iso(BASE_RANGE[1])),
                             plots=[PlotModel(products=[ProductModel(path=path)])])
    return Comparison(base=template.to_tree(), dimension=dimension, variants=list(variants))


def _time_variants(*starts, length=100.0):
    return [Variant(label=f"event {i}", params={"start": s, "stop": s + length}) for i, s in enumerate(starts)]


def _build(comparison, qtbot):
    from SciQLop.components.comparison.ui.overlay_view import build_overlay
    panel = build_overlay(comparison, resolve_sides(comparison), {}, None, None)
    qtbot.addWidget(panel)
    return panel


def _graphs(plot):
    from SciQLop.components.plotting.panel_introspection import plot_graphs
    return plot_graphs(plot)


def _overlay_text(plot):
    from SciQLop.components.plotting.ui.diagnostic_overlay import overlay_of
    return overlay_of(plot).text()


def test_overlay_adds_one_ghost_per_variant(main_window, qtbot):
    _, path = _vp("vp")
    comparison = _comparison(path, variants=_time_variants(2_000.0, 3_000.0))
    panel = _build(comparison, qtbot)
    plot = panel.plots()[0]
    qtbot.waitUntil(lambda: len(_graphs(plot)) == 3)
    names = [graph_name(g) for g in _graphs(plot)]
    assert names[1].endswith("— " + comparison.variants[0].label)
    assert names[2].endswith("— " + comparison.variants[1].label)


def test_ghost_is_dashed_and_lighter_than_its_base(main_window, qtbot):
    from PySide6.QtCore import Qt
    _, path = _vp("vp2", labels=("a", "b"))
    panel = _build(_comparison(path, variants=_time_variants(2_000.0, 3_000.0)), qtbot)
    base, first, second = _graphs(panel.plots()[0])

    def styled(ghost, index):
        pairs = list(zip(base.components(), ghost.components()))
        return len(pairs) == 2 and all(g.pen().style() == Qt.PenStyle.DashLine
                                       and g.color() == b.color().lighter(130 + 20 * index) for b, g in pairs)

    qtbot.waitUntil(lambda: styled(first, 0) and styled(second, 1))


def test_overlay_ghost_with_no_data_stays_empty_without_error(main_window, qtbot, monkeypatch):
    from SciQLop.components.plotting.ui.time_sync_panel import _ProductCallbackBase
    outcomes = []
    record_error, record_success = _ProductCallbackBase._record_error, _ProductCallbackBase._record_success
    monkeypatch.setattr(_ProductCallbackBase, "_record_error",
                        lambda self, e: (outcomes.append((self.time_offset, e)), record_error(self, e)))
    monkeypatch.setattr(_ProductCallbackBase, "_record_success",
                        lambda self: (outcomes.append((self.time_offset, None)), record_success(self)))
    calls = []

    def sparse(start: float, stop: float):
        calls.append(start)
        if start > 5_000.0:
            return np.array([]), np.array([])
        x = np.linspace(start, stop, 50)
        return x, np.sin(x)

    _, path = _vp("sparse", sparse)
    panel = _build(_comparison(path, variants=_time_variants(10_000.0)), qtbot)
    plot = panel.plots()[0]
    qtbot.waitUntil(lambda: {offset == 0 for offset, _ in outcomes} == {True, False})
    assert len(_graphs(plot)) == 2
    assert [e for _, e in outcomes if e is not None] == []
    assert any(s < 5_000.0 for s in calls) and any(s > 5_000.0 for s in calls)


def test_overlay_refuses_mismatched_units(main_window, qtbot, monkeypatch):
    nT, nT_path = _vp("nT")
    mV, mV_path = _vp("mV")
    monkeypatch.setattr(nT._impl, "plot_hints", lambda node: PlotHints(y=AxisHints(unit="nT")), raising=False)
    monkeypatch.setattr(mV._impl, "plot_hints", lambda node: PlotHints(y=AxisHints(unit="mV")), raising=False)
    comparison = _comparison(nT_path, dimension="product",
                             variants=[Variant(label="other", params={"target": [0, 0], "path": mV_path})])
    plot = _build(comparison, qtbot).plots()[0]
    assert len(_graphs(plot)) == 1
    assert "other: not overlaid — different units: nT vs mV" in _overlay_text(plot)


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


def test_overlay_removes_ghost_when_fetched_units_differ(main_window, qtbot):
    _, nT_path = _speasy_vp("fetched_nT", "nT")
    _, mV_path = _speasy_vp("fetched_mV", "mV")
    comparison = _comparison(nT_path, dimension="product",
                             variants=[Variant(label="other", params={"target": [0, 0], "path": mV_path})])
    plot = _build(comparison, qtbot).plots()[0]
    qtbot.waitUntil(lambda: "other: not overlaid — different units: nT vs mV" in _overlay_text(plot))
    qtbot.waitUntil(lambda: len(_graphs(plot)) == 1)


def test_ghost_colour_is_stable_while_the_base_has_no_data(main_window, qtbot):
    calls = []

    def late(start: float, stop: float):
        calls.append(start)
        if stop < 1_500.0:
            return np.array([]), np.array([])
        x = np.linspace(start, stop, 50)
        return x, np.sin(x)

    _, path = _vp("late", late)
    panel = _build(_comparison(path, variants=_time_variants(2_000.0)), qtbot)
    ghost = _graphs(panel.plots()[0])[1]
    qtbot.waitUntil(lambda: len(ghost.components()) == 1)
    colour = ghost.components()[0].color()
    from SciQLop.core import TimeRange
    for shift in (10.0, 20.0, 30.0):
        before = len(calls)
        panel.time_range = TimeRange(BASE_RANGE[0] + shift, BASE_RANGE[1] + shift)
        qtbot.waitUntil(lambda: len(calls) >= before + 2)
    assert ghost.components()[0].color() == colour


def test_overlay_reports_unplottable_variant(main_window, qtbot):
    _, path = _vp("vp3")
    comparison = _comparison(path, dimension="product",
                             variants=[Variant(label="gone", params={"target": [0, 0], "path": "no//such//product"})])
    plot = _build(comparison, qtbot).plots()[0]
    assert len(_graphs(plot)) == 1
    assert "gone: no//such//product could not be plotted" in _overlay_text(plot)


def test_overlay_does_not_ghost_spectrogram_variants(main_window, qtbot):
    _, path = _vp("vp7")
    comparison = _comparison(path, dimension="product", variants=[
        Variant(label="spec", params={"target": [0, 0], "path": path, "is_colormap": True})])
    plot = _build(comparison, qtbot).plots()[0]
    assert len(_graphs(plot)) == 1
    text = _overlay_text(plot)
    assert "a spectrogram and a line plot cannot be overlaid" in text
    assert "use Difference" not in text


def _spectrogram_path(name):
    from SciQLop.user_api.plot._plots import to_product_path
    from SciQLop.user_api.virtual_products import VirtualProductType, create_virtual_product

    def spectrogram(start: float, stop: float, gain: float = 1.0):
        x = np.linspace(start, stop, 20)
        y = np.array([1.0, 10.0, 100.0])
        return x, y, np.ones((len(x), 1)) * y[None, :] * gain

    vp = create_virtual_product(f"test_cmp/{name}", spectrogram, VirtualProductType.Spectrogram)
    return "//".join(to_product_path(vp))


def test_overlay_points_spectrogram_variants_of_a_spectrogram_to_difference(main_window, qtbot):
    path = _spectrogram_path("spec_settings")
    template = PanelTemplate(name="P", time_range=TimeRangeModel(start=_iso(BASE_RANGE[0]), stop=_iso(BASE_RANGE[1])),
                             plots=[PlotModel(products=[ProductModel(path=path, knobs={"gain": 1.0},
                                                                     graph_type="SciQLopColorMap")])])
    comparison = Comparison(base=template.to_tree(), dimension="settings",
                            variants=[Variant(label="v", params={"target": [0, 0], "knobs": {"gain": 2.0}})])
    plot = _build(comparison, qtbot).plots()[0]
    assert "spectrogram variants are not shown in Overlay — use Difference" in _overlay_text(plot)


def test_overlay_warns_about_long_variants_and_many_variants(main_window, qtbot):
    _, path = _vp("vp4")
    starts = [2_000.0 + 1_000.0 * i for i in range(7)]
    plot = _build(_comparison(path, variants=_time_variants(*starts, length=200.0)), qtbot).plots()[0]
    text = _overlay_text(plot)
    assert "many variants — an Epoch view will summarise them better" in text
    assert "some variants are longer than the view; only the first 0:01:40 are shown" in text


def test_applies_overlay_needs_a_change():
    from SciQLop.components.comparison.ui.overlay_view import applies_overlay
    same = _comparison("a//b", dimension="settings",
                       variants=[Variant(label="v", params={"target": [0, 0], "knobs": {}})])
    assert applies_overlay(same, resolve_sides(same)) == "nothing differs between the sides"
    moved = _comparison("a//b", variants=_time_variants(2_000.0))
    assert applies_overlay(moved, resolve_sides(moved)) is None


def test_inner_panel_is_read_only(main_window, qtbot):
    from SciQLop.components.comparison.ui.inner_panel import build_inner_panel
    from SciQLop.components.plotting.ui.product_search_overlay import ProductSearchOverlay
    _, path = _vp("vp5")
    panel, plots = build_inner_panel(_comparison(path), None, None)
    qtbot.addWidget(panel)
    assert not panel.acceptDrops()
    assert not panel.findChildren(ProductSearchOverlay)
    assert plots == [panel.plots()[0].data()]


def test_inner_panel_uses_the_given_time_range(main_window, qtbot):
    from SciQLop.components.comparison.ui.inner_panel import build_inner_panel
    _, path = _vp("vp6")
    panel, _ = build_inner_panel(_comparison(path), (5_000.0, 5_050.0), None)
    qtbot.addWidget(panel)
    rng = panel.time_axis_range()
    assert (rng.start(), rng.stop()) == (5_000.0, 5_050.0)


def _knob_vp(name):
    def scaled(start: float, stop: float, scale: float = 1.0):
        x = np.linspace(start, stop, 50)
        return x, np.sin(x) * scale
    return _vp(name, callback=scaled)


def _settings_overlay(path, qtbot):
    return _build(_comparison(path, dimension="settings", variants=[
        Variant(label="x2", params={"target": [0, 0], "knobs": {"scale": 2.0}})]), qtbot)


def test_read_only_graphs_keep_their_knob_values_without_editing_ui(main_window, qtbot):
    _, path = _knob_vp("knob_ro")
    plot = _settings_overlay(path, qtbot).plots()[0]
    qtbot.waitUntil(lambda: len(_graphs(plot)) == 2)
    base, ghost = _graphs(plot)
    assert ghost._knob_state.values["scale"] == 2.0
    for graph in (base, ghost):
        assert getattr(graph, "_knob_inspector_ext", None) is None
        assert getattr(graph, "_visual_knob_dispose", None) is None


def _menu_texts(menu):
    texts = []
    for action in menu.actions():
        texts.append(action.text())
        if action.menu() is not None:
            texts += _menu_texts(action.menu())
    return texts


@pytest.mark.parametrize("read_only", [False, True])
def test_read_only_panel_menu_has_no_export_or_input_reset(main_window, qtbot, read_only):
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel, plot_product
    from SciQLop.core import TimeRange
    from SciQLop.user_api.plot._plots import to_product_path
    vp, _ = _knob_vp(f"knob_menu_{read_only}")
    panel = TimeSyncPanel("ro", time_range=TimeRange(*BASE_RANGE), read_only=read_only)
    qtbot.addWidget(panel)
    plot_product(panel, to_product_path(vp))
    menu = panel._build_context_menu()
    texts = _menu_texts(menu)
    menu.deleteLater()
    editable = not read_only
    assert ("Export" in texts) == editable
    assert any(t.startswith("Reset inputs:") for t in texts) == editable
    graph = _graphs(panel.plots()[0].data())[0]
    assert (getattr(graph, "_knob_inspector_ext", None) is not None) == editable


def test_shifted_remote_ghost_is_refused_with_a_reason(main_window, qtbot, monkeypatch):
    from SciQLop.components.comparison.ui import overlay_view
    monkeypatch.setattr(overlay_view, "is_remote", lambda path: True)
    _, path = _vp("remote_shift")
    plot = _build(_comparison(path, variants=_time_variants(2_000.0)), qtbot).plots()[0]
    text = _overlay_text(plot)
    assert "event 0: not overlaid — remote products cannot be shifted in time yet" in text
    assert "could not be plotted" not in text


def test_ghost_components_beyond_the_base_are_dashed_and_lightened_once(main_window, qtbot):
    from PySide6.QtCore import Qt
    from SciQLop.components.comparison.ui.styling import ghost_style
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel, plot_product
    from SciQLop.core import TimeRange
    _, one = _vp("style_one")
    _, three = _vp("style_three", labels=("a", "b", "c"))
    panel = TimeSyncPanel("style", time_range=TimeRange(*BASE_RANGE))
    qtbot.addWidget(panel)
    plot, base = plot_product(panel, one.split("//"))
    ghost = plot_product(plot, three.split("//"))
    qtbot.waitUntil(lambda: len(base.components()) == 1 and len(ghost.components()) == 3)
    own = [c.color() for c in ghost.components()]
    assert ghost_style(ghost, base, 0)
    ghost_style(ghost, base, 0)
    colours = [c.color() for c in ghost.components()]
    assert colours[0] == base.components()[0].color().lighter(130)
    assert colours[1:] == [c.lighter(130) for c in own[1:]]
    assert all(c.pen().style() == Qt.PenStyle.DashLine for c in ghost.components())
