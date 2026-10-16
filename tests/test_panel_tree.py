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


def test_an_unknown_panel_kind_loads_as_a_template_of_that_kind(tmp_path):
    path = tmp_path / "x.json"
    path.write_text(json.dumps({"version": 3, "name": "x", "panel": {"kind": "vdf.study_panel"}}))
    t = PanelTemplate.from_file(str(path))
    assert t.panel_kind == "vdf.study_panel" and t.plots == []


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


_ABSENT_ROOT = {"kind": "absent.viewer", "id": "v1",
                "config": {"source": {"mission": "mms", "probes": [1, 2]}, "zoom": 2.5},
                "slots": {"views": [{"kind": "absent.view", "config": {"axis": "x"}}]}}


def _absent_template_file(tmp_path, monkeypatch):
    from SciQLop.components.plotting import panel_template
    monkeypatch.setattr(panel_template, "templates_dir", lambda: tmp_path)
    path = tmp_path / "viewer.json"
    path.write_text(json.dumps({"version": 3, "name": "viewer", "description": "kept", "panel": _ABSENT_ROOT}))
    return path


def test_listing_a_template_of_another_kind_keeps_its_file_as_is(tmp_path, monkeypatch):
    from SciQLop.components.plotting import panel_template
    path = _absent_template_file(tmp_path, monkeypatch)
    before = path.read_text()
    assert [t.panel_kind for t in panel_template.list_templates()] == ["absent.viewer"]
    assert path.read_text() == before


def test_renaming_a_template_of_another_kind_keeps_its_tree(tmp_path, monkeypatch):
    from SciQLop.components.plotting import panel_template
    _absent_template_file(tmp_path, monkeypatch)
    assert panel_template.rename_template("viewer", "renamed")
    data = json.loads((tmp_path / "renamed.json").read_text())
    assert data["name"] == "renamed" and data["panel"] == _ABSENT_ROOT


_PARENT_COMMIT_TIME_TREE = {
    'version': 3, 'name': 'tree', 'description': 'd', 'max_zoom_seconds': 3600.0,
    'intervals': [{'start': '2020-01-01T01:00:00+00:00', 'stop': '2020-01-01T02:00:00+00:00', 'color': '#ff0000',
                   'label': 'burst'}],
    'panel': {'kind': 'sciqlop.time_panel', 'id': '',
              'config': {'time_range': {'start': '2020-01-01T00:00:00+00:00', 'stop': '2020-01-02T00:00:00+00:00'}},
              'slots': {'plots': [
                  {'kind': 'sciqlop.timeseries', 'id': '',
                   'config': {'products': [{'path': 'speasy//amda//imf', 'label': '', 'kind': 'sciqlop.speasy',
                                            'speasy_id': None, 'graph_type': 'Line', 'knobs': {}, 'y_axis': 'y'}],
                              'y_axis': {'log': True, 'range': [1.0, 10.0]}, 'y2_axis': None,
                              'z_axis': {'log': False, 'range': None}},
                   'slots': {}},
                  {'kind': 'pt_demo.slice_plot', 'id': '', 'config': {'plane': 'XY'}, 'slots': {}}]}}}


@pytest.mark.parametrize("suffix", [".json", ".yaml"])
def test_time_templates_are_unchanged(tmp_path, suffix):
    import yaml
    path = tmp_path / f"time{suffix}"
    path.write_text(json.dumps(_PARENT_COMMIT_TIME_TREE) if suffix == ".json" else yaml.dump(_PARENT_COMMIT_TIME_TREE))
    t = PanelTemplate.from_file(str(path))
    assert t.panel_kind == TIME_PANEL and t.to_tree() == _PARENT_COMMIT_TIME_TREE
    t.to_file(str(path))
    assert PanelTemplate.from_file(str(path)).to_tree() == _PARENT_COMMIT_TIME_TREE


@pytest.fixture
def note_kind():
    from PySide6.QtWidgets import QLabel
    from SciQLop.core.panel_kinds import PANEL_KINDS, PanelKind
    with owned_by("pt_demo"):
        PANEL_KINDS.contribute(PanelKind("pt_demo.note", "Note", create=lambda n, c: QLabel(c.get("text", "")),
                                         to_config=lambda w: {"text": w.text()}))
        PANEL_KINDS.contribute(PanelKind("pt_demo.mute", "Mute", create=lambda n, c: QLabel("")))
    yield
    PANEL_KINDS.remove_owner("pt_demo")


def _close_all(main_window, widgets):
    for w in widgets:
        main_window.remove_panel(w)


def test_a_plugin_kind_round_trips_through_a_template(main_window, tmp_path, note_kind):
    from PySide6.QtWidgets import QLabel
    w = main_window.open_panel("pt_demo.note", name="pt_note", text="hello")
    opened = [w]
    try:
        t = PanelTemplate.from_panel(w)
        t.to_file(str(tmp_path / "n.yaml"))
        loaded = PanelTemplate.from_file(str(tmp_path / "n.yaml"))
        assert loaded.panel_kind == "pt_demo.note" and loaded.name == "pt_note"
        restored = loaded.create_panel(main_window)
        opened.append(restored)
        assert isinstance(restored, QLabel) and restored.text() == "hello"
        assert restored in main_window.panels()
    finally:
        _close_all(main_window, opened)


def test_a_config_with_name_and_area_keys_reaches_create(main_window, tmp_path):
    from PySide6.QtWidgets import QLabel
    from SciQLop.core.panel_kinds import PANEL_KINDS, PanelKind
    received = []

    def create(name, config):
        received.append(dict(config))
        label = QLabel(config.get("name", ""))
        label.station_config = dict(config)
        return label

    with owned_by("pt_demo"):
        PANEL_KINDS.contribute(PanelKind("pt_demo.station", "Station", create=create,
                                         to_config=lambda w: w.station_config))
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"version": 3, "name": "pt_station", "panel": {
        "kind": "pt_demo.station", "config": {"name": "station A", "area": "north"}, "slots": {}}}))
    restored = None
    try:
        restored = PanelTemplate.from_file(str(path)).create_panel(main_window)
        assert received == [{"name": "station A", "area": "north"}]
        assert restored in main_window.panels() and restored.windowTitle() == "pt_station"
    finally:
        if restored is not None:
            main_window.remove_panel(restored)
        PANEL_KINDS.remove_owner("pt_demo")


def test_a_create_mutating_its_nested_config_leaves_the_template_as_loaded(main_window, tmp_path):
    from PySide6.QtWidgets import QLabel
    from SciQLop.core.panel_kinds import PANEL_KINDS, PanelKind
    received = []

    def create(name, config):
        received.append(config["view"]["zoom"])
        config["view"]["zoom"] = 99
        return QLabel()

    with owned_by("pt_demo"):
        PANEL_KINDS.contribute(PanelKind("pt_demo.zoomer", "Zoomer", create=create))
    path = tmp_path / "z.json"
    path.write_text(json.dumps({"version": 3, "name": "pt_zoomer", "panel": {
        "kind": "pt_demo.zoomer", "config": {"view": {"zoom": 2}}, "slots": {}}}))
    template = PanelTemplate.from_file(str(path))
    opened = []
    try:
        opened = [template.create_panel(main_window), template.create_panel(main_window)]
        assert received == [2, 2]
    finally:
        _close_all(main_window, opened)
        PANEL_KINDS.remove_owner("pt_demo")


def test_a_kind_without_to_config_cannot_be_saved(main_window, note_kind):
    from SciQLop.components.plotting.panel_template import panel_tree
    w = main_window.open_panel("pt_demo.mute", name="pt_mute")
    try:
        with pytest.raises(ValueError, match="pt_demo.mute"):
            panel_tree(w)
    finally:
        main_window.remove_panel(w)


def test_missing_kind_opens_a_placeholder(main_window, tmp_path, monkeypatch):
    from SciQLop.components.plotting import panel_template
    from SciQLop.components.plotting.ui.placeholder_panel import PlaceholderPanel
    _absent_template_file(tmp_path, monkeypatch)
    [t] = panel_template.list_templates()
    placeholder = t.create_panel(main_window)
    try:
        assert isinstance(placeholder, PlaceholderPanel)
        assert placeholder.missing_kind == "absent.viewer"
        assert "'absent'" in placeholder.message() and "absent.viewer" in placeholder.message()
        assert placeholder.windowTitle() == "viewer"
        assert placeholder in main_window.panels()
    finally:
        main_window.remove_panel(placeholder)


def test_the_placeholder_saves_its_tree_back(main_window, tmp_path, monkeypatch):
    from SciQLop.components.plotting.panel_template import panel_tree
    path = _absent_template_file(tmp_path, monkeypatch)
    placeholder = PanelTemplate.from_file(str(path)).create_panel(main_window)
    try:
        assert panel_tree(placeholder) == _ABSENT_ROOT
        panel_tree(placeholder)["config"]["source"]["probes"].append(3)
        assert panel_tree(placeholder) == _ABSENT_ROOT
        other = tmp_path / "out" / "other.json"
        other.parent.mkdir()
        PanelTemplate.from_panel(placeholder).to_file(str(other))
        assert json.loads(other.read_text())["panel"] == _ABSENT_ROOT
    finally:
        main_window.remove_panel(placeholder)


def test_apply_refuses_a_foreign_template(qtbot, tmp_path, monkeypatch):
    path = _absent_template_file(tmp_path, monkeypatch)
    with pytest.raises(TypeError, match="absent.viewer"):
        PanelTemplate.from_file(str(path)).apply(_panel(qtbot, "pt_apply_panel"))
