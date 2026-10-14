"""Panels as trees (spec §5): v3 files, older files migrate, unknown kinds survive as placeholders."""
import json

import pytest

from .fixtures import *  # noqa: F401,F403 — main_window, simple_vp_callback
from SciQLop.components.plotting.panel_template import (TEMPLATE_VERSION, PanelTemplate, PlotModel,
                                                        ProductModel, TimeRangeModel)
from SciQLop.core.extensions import owned_by
from SciQLop.core.plot_kinds import PLOT_KINDS, TIME_PANEL, TIMESERIES, PlotKind


def _template():
    return PanelTemplate(
        name="tree", time_range=TimeRangeModel(start="2020-01-01T00:00:00+00:00", stop="2020-01-02T00:00:00+00:00"),
        plots=[PlotModel(products=[ProductModel(path="speasy//amda//imf", kind="speasy", graph_type="Line",
                                                y_axis="y")]),
               PlotModel(kind="pt_demo.slice_plot", config={"plane": "XY"})])


def test_v3_is_a_panel_tree(tmp_path):
    path = tmp_path / "t.json"
    _template().to_file(str(path))
    data = json.loads(path.read_text())
    assert TEMPLATE_VERSION == 3 and data["version"] == 3
    assert data["panel"]["kind"] == TIME_PANEL
    assert data["panel"]["config"]["time_range"]["start"].startswith("2020-01-01")
    plots = data["panel"]["slots"]["plots"]
    assert [p["kind"] for p in plots] == [TIMESERIES, "pt_demo.slice_plot"]
    assert plots[0]["config"]["products"][0]["path"] == "speasy//amda//imf"
    assert plots[1]["config"] == {"plane": "XY"}


@pytest.mark.parametrize("suffix", [".json", ".yaml"])
def test_v3_round_trips(tmp_path, suffix):
    path = tmp_path / f"t{suffix}"
    _template().to_file(str(path))
    assert PanelTemplate.from_file(str(path)).model_dump() == _template().model_dump()


def test_a_v2_file_reads_as_the_same_model_and_rewrites_as_v3(tmp_path):
    v2 = {"name": "old", "version": 2, "plots": [{"products": [{"path": "speasy//amda//imf", "graph_type": "Line",
                                                                "y_axis": "y"}]}]}
    path = tmp_path / "old.json"
    path.write_text(json.dumps(v2))
    t = PanelTemplate.from_file(str(path))
    assert t.plots[0].kind == TIMESERIES and t.plots[0].products[0].path == "speasy//amda//imf"
    t.to_file(str(path))
    assert json.loads(path.read_text())["version"] == 3
    assert PanelTemplate.from_file(str(path)).model_dump() == t.model_dump()


def test_a_v1_file_still_gets_its_axes(tmp_path):
    v1 = {"name": "older", "plots": [{"products": [{"path": "a//b", "graph_type": "ColorMap"}]}]}
    path = tmp_path / "older.json"
    path.write_text(json.dumps(v1))
    assert PanelTemplate.from_file(str(path)).plots[0].products[0].y_axis == "y2"


def test_an_unknown_panel_kind_is_refused_with_its_plugin(tmp_path):
    path = tmp_path / "x.json"
    path.write_text(json.dumps({"version": 3, "name": "x", "panel": {"kind": "vdf.study_panel"}}))
    with pytest.raises(ValueError, match="vdf"):
        PanelTemplate.from_file(str(path))


def test_unknown_plot_kind_restores_as_a_placeholder_that_keeps_its_node(qtbot):
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    panel = TimeSyncPanel("pt_panel", show_search_overlay=False)
    qtbot.addWidget(panel)
    t = PanelTemplate(name="p", plots=[PlotModel(kind="pt_gone.slice_plot", config={"plane": "YZ"})])
    t.apply(panel)
    assert len(panel.plots()) == 1
    saved = PanelTemplate.from_panel(panel)
    assert [(p.kind, p.config) for p in saved.plots] == [("pt_gone.slice_plot", {"plane": "YZ"})]


def test_a_plot_kind_restores_through_from_config_and_saves_through_to_config(qtbot):
    from SciQLopPlots import PlotType
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    made = {}

    def from_config(panel, config):
        panel.create_plot(len(panel.plots()), PlotType.TimeSeries)
        plot = panel.plots()[-1]
        made[plot.objectName()] = dict(config)
        return plot

    def owns(plot):
        return plot.objectName() in made

    with owned_by("pt_demo"):
        PLOT_KINDS.contribute(PlotKind("pt_demo.slice_plot", "Slice", plot_product=lambda *a: None, owns=owns,
                                       to_config=lambda plot: made[plot.objectName()], from_config=from_config))
    try:
        panel = TimeSyncPanel("pt_panel2", show_search_overlay=False)
        qtbot.addWidget(panel)
        PanelTemplate(name="p", plots=[PlotModel(kind="pt_demo.slice_plot", config={"plane": "XY"})]).apply(panel)
        assert list(made.values()) == [{"plane": "XY"}]
        assert [(p.kind, p.config) for p in PanelTemplate.from_panel(panel).plots] == [
            ("pt_demo.slice_plot", {"plane": "XY"})]
    finally:
        PLOT_KINDS.remove_owner("pt_demo")


def _panel(qtbot, name):
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    panel = TimeSyncPanel(name, show_search_overlay=False)
    qtbot.addWidget(panel)
    return panel


def _placeholder_panel(qtbot, name):
    panel = _panel(qtbot, name)
    PanelTemplate(name="p", plots=[PlotModel(kind="pt_gone.slice_plot", config={"plane": "YZ"})]).apply(panel)
    return panel


def test_a_placeholder_refuses_product_drops_and_keeps_its_node(qtbot, main_window, simple_vp_callback):
    from SciQLop.components.plotting.drops import drop_product
    from SciQLop.components.plotting.panel_introspection import ordered_panel_plots, plot_graphs
    from SciQLop.user_api.virtual_products import VirtualProductType, create_virtual_product
    vp = create_virtual_product("pt_drop/vp", simple_vp_callback, VirtualProductType.Scalar, labels=["y"])
    panel = _placeholder_panel(qtbot, "pt_drop_panel")
    plot = ordered_panel_plots(panel)[0]
    assert drop_product(plot, vp.path.split("/"), panel) is None
    assert plot_graphs(plot) == []
    assert [(p.kind, p.config) for p in PanelTemplate.from_panel(panel).plots] == [
        ("pt_gone.slice_plot", {"plane": "YZ"})]


def test_a_placeholder_is_never_taken_as_a_drop_placeholder(qtbot):
    from SciQLop.components.plotting.drops import take_drop_placeholder
    from SciQLop.components.plotting.panel_introspection import ordered_panel_plots
    panel = _placeholder_panel(qtbot, "pt_take_panel")
    assert take_drop_placeholder(ordered_panel_plots(panel)[0], panel) is None
    assert len(panel.plots()) == 1


def test_a_failing_from_config_leaves_a_placeholder_not_a_broken_panel(qtbot):
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel

    def boom(panel, config):
        raise RuntimeError("bad config")

    with owned_by("pt_demo"):
        PLOT_KINDS.contribute(PlotKind("pt_demo.broken", "Broken", plot_product=lambda *a: None, from_config=boom))
    try:
        panel = TimeSyncPanel("pt_panel3", show_search_overlay=False)
        qtbot.addWidget(panel)
        PanelTemplate(name="p", plots=[PlotModel(kind="pt_demo.broken", config={"a": 1})]).apply(panel)
        assert [(p.kind, p.config) for p in PanelTemplate.from_panel(panel).plots] == [("pt_demo.broken", {"a": 1})]
    finally:
        PLOT_KINDS.remove_owner("pt_demo")


def test_a_from_config_that_adds_a_plot_then_raises_leaves_only_the_placeholder(qtbot):
    from SciQLopPlots import PlotType

    def half_built(panel, config):
        panel.create_plot(len(panel.plots()), PlotType.TimeSeries)
        raise RuntimeError("late failure")

    with owned_by("pt_demo"):
        PLOT_KINDS.contribute(PlotKind("pt_demo.half", "Half", plot_product=lambda *a: None, from_config=half_built))
    try:
        panel = _panel(qtbot, "pt_half_panel")
        PanelTemplate(name="p", plots=[PlotModel(kind="pt_demo.half", config={"a": 1})]).apply(panel)
        assert len(panel.plots()) == 1
        assert [(p.kind, p.config) for p in PanelTemplate.from_panel(panel).plots] == [("pt_demo.half", {"a": 1})]
    finally:
        PLOT_KINDS.remove_owner("pt_demo")


def test_a_to_config_that_raises_skips_that_plot_only(qtbot):
    from SciQLopPlots import PlotType
    made = {}

    def from_config(panel, config):
        panel.create_plot(len(panel.plots()), PlotType.TimeSeries)
        plot = panel.plots()[-1]
        made[plot.objectName()] = config["kind"]
        return plot

    def boom(plot):
        raise RuntimeError("cannot save")

    with owned_by("pt_demo"):
        for name, to_config in (("bad", boom), ("good", lambda plot: {"kind": "good"})):
            PLOT_KINDS.contribute(PlotKind(f"pt_demo.{name}", name, plot_product=lambda *a: None,
                                           owns=lambda plot, n=name: made.get(plot.objectName()) == n,
                                           to_config=to_config, from_config=from_config))
    try:
        panel = _panel(qtbot, "pt_bad_save_panel")
        PanelTemplate(name="p", plots=[PlotModel(kind="pt_demo.bad", config={"kind": "bad"}),
                                       PlotModel(kind="pt_demo.good", config={"kind": "good"})]).apply(panel)
        assert [p.kind for p in PanelTemplate.from_panel(panel).plots] == ["pt_demo.good"]
    finally:
        PLOT_KINDS.remove_owner("pt_demo")


@pytest.mark.parametrize("suffix", [".json", ".yaml"])
def test_every_template_field_round_trips(tmp_path, suffix):
    from SciQLop.components.plotting.panel_template import AxisModel, IntervalModel
    template = PanelTemplate(
        name="full", time_range=TimeRangeModel(start="2020-01-01T00:00:00+00:00", stop="2020-01-02T00:00:00+00:00"),
        max_zoom_seconds=3600.0,
        intervals=[IntervalModel(start="2020-01-01T01:00:00+00:00", stop="2020-01-01T02:00:00+00:00",
                                 color="#ff0000", label="burst")],
        plots=[PlotModel(products=[ProductModel(path="speasy//amda//imf", graph_type="Line", y_axis="y2")],
                         y_axis=AxisModel(log=True, range=(1.0, 10.0)),
                         y2_axis=AxisModel(log=False, range=(-1.0, 1.0)))])
    path = tmp_path / f"full{suffix}"
    template.to_file(str(path))
    assert PanelTemplate.from_file(str(path)).model_dump() == template.model_dump()


def test_listing_warns_about_a_file_whose_root_panel_kind_is_unknown(tmp_path, monkeypatch):
    from SciQLop.components.plotting import panel_template
    (tmp_path / "x.json").write_text(json.dumps({"version": 3, "name": "x", "panel": {"kind": "vdf.study_panel"}}))
    warnings = []
    monkeypatch.setattr(panel_template, "templates_dir", lambda: tmp_path)
    monkeypatch.setattr(panel_template.log, "warning", lambda msg, *a, **k: warnings.append(msg))
    assert panel_template.list_templates() == []
    assert "x.json" in warnings[0] and "vdf" in warnings[0]
