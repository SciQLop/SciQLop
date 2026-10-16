"""Spec §10 interop proof for plot kinds, drop rules and the panel tree: one plugin contributes a product kind, a
plot kind and a drop rule; a second uses its API; a panel mixing them round-trips through the v3 template, and
survives the plugin being gone as placeholders."""
import json
import sys
import textwrap

import pytest
import yaml

from SciQLop.components.plugins.backend.loader import context, loader
from SciQLop.core import extensions

from .helpers import restore_extension_points

_OWNERS = ("pi_vdf", "pi_study")


@pytest.fixture
def fresh(qapp):
    saved = (dict(context.STATES), set(loader._attempted), dict(vars(loader.loaded_plugins)))
    saved_points = dict(extensions._EXTENSION_POINTS)
    yield
    for ep in extensions.all_extension_points():
        for owner in _OWNERS:
            ep.remove_owner(owner)
    for live, old in zip((context.STATES, loader._attempted, vars(loader.loaded_plugins)), saved):
        live.clear()
        live.update(old)
    restore_extension_points(saved_points)


def _plugin(folder, name, code, **desc):
    pkg = folder / name
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(textwrap.dedent(code))
    (pkg / "plugin.json").write_text(json.dumps({"name": name, "version": "1.0.0", **desc}))
    return (str(folder), name)


_VDF = """
    from SciQLop.core.drop_rules import DropRule
    from SciQLopPlots import PlotType
    from SciQLop.core.mime.types import PRODUCT_LIST_MIME_TYPE
    from SciQLop.core.plot_kinds import PlotKind
    from SciQLop.core.product_kinds import ProductKind

    CONFIGS = {}

    def from_config(panel, config):
        plot = panel.create_plot(len(panel.plots()), PlotType.TimeSeries)
        CONFIGS[plot.objectName()] = dict(config)
        return plot

    def owns(plot):
        return plot.objectName() in CONFIGS

    def to_config(plot):
        return CONFIGS[plot.objectName()]

    def plot_product(target, product, kwargs):
        return from_config(target, {"product": "//".join(product), "plane": "XY"}), None

    def drop(plot, product, panel):
        from SciQLop.components.plotting.drops import take_drop_placeholder
        slot = take_drop_placeholder(plot, panel)
        new_plot = from_config(panel, {"product": "//".join(product), "plane": "XY"})
        if slot is not None:
            panel.move_plot(panel.plot_count() - 1, slot)
        return new_plot

    class Api:
        SLICE = "pi_vdf.slice_plot"

    def activate(ctx):
        ctx.contribute("sciqlop.product_kinds", ProductKind("pi_vdf.distribution", "VDF", 0, "pi_vdf.slice_plot"))
        ctx.contribute("sciqlop.plot_kinds", PlotKind("pi_vdf.slice_plot", "VDF slice", plot_product, owns,
                                                      to_config, from_config))
        ctx.contribute("sciqlop.drop_rules", DropRule("pi_vdf.drop", PRODUCT_LIST_MIME_TYPE, drop,
                                                      product_kind="pi_vdf.distribution", creates_plot=True))
        return Api()
"""

_STUDY = """
    SLICE = None

    def activate(ctx):
        global SLICE
        SLICE = ctx.plugin("pi_vdf").SLICE
"""

_PRODUCT = ["pi_vdf_products", "dis"]
_SAVED_CONFIGS = [{"product": "pi_vdf_products//dis", "plane": "YZ"},
                  {"product": "pi_vdf_products//dis", "plane": "XY"}]


def _plot_nodes(path):
    saved = yaml.safe_load(path.read_text())
    return saved["panel"], saved["panel"]["slots"]["plots"]


def _new_panel(qtbot, name):
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    panel = TimeSyncPanel(name, show_search_overlay=False)
    qtbot.addWidget(panel)
    return panel


def _drop_between_plots(monkeypatch, panel):
    """What SciQLopMultiPlotPanel::dropEvent does: an empty plot is made and handed to the MIME callback."""
    from PySide6.QtCore import QMimeData
    from SciQLopPlots import PlotType
    from SciQLop.components.plotting import drops
    monkeypatch.setattr(drops, "decode_mime", lambda mime, types: [_PRODUCT])
    panel.create_plot(len(panel.plots()), PlotType.TimeSeries)
    panel._product_plot_callback.call(panel.plots()[-1], QMimeData())
    assert len(panel.plots()) == 1


def test_plugin_plot_kinds_round_trip_through_the_panel_tree(tmp_path, qtbot, fresh, monkeypatch):
    from SciQLop.components.plotting.drops import dispatch_drop
    from SciQLop.components.plotting.panel_template import PanelTemplate
    from SciQLop.core.enums import ParameterType
    from SciQLop.core.mime.types import PRODUCT_LIST_MIME_TYPE
    from SciQLop.core.models import ProductsModelNodeType, add_product_node
    from SciQLop.core.product_kinds import PRODUCT_KIND_KEY
    from SciQLop.user_api.plot import PlotPanel

    loader.activate_all([_plugin(tmp_path, "pi_study", _STUDY, dependencies=["pi-vdf>=1"]),
                         _plugin(tmp_path, "pi_vdf", _VDF)], main_window=object(), ep_plugins={})
    assert {n: context.STATES[n].status for n in _OWNERS} == {"pi_vdf": "active", "pi_study": "active"}, \
        {n: context.STATES[n].reason for n in _OWNERS}

    add_product_node(_PRODUCT[:-1], _PRODUCT[-1], "pi_vdf", {PRODUCT_KIND_KEY: "pi_vdf.distribution"},
                     ProductsModelNodeType.PARAMETER, ParameterType.Scalar)
    panel = _new_panel(qtbot, "pi_panel")
    PlotPanel(panel).add(sys.modules["pi_study"].SLICE, product="pi_vdf_products//dis", plane="YZ")
    dispatch_drop(panel, None, PRODUCT_LIST_MIME_TYPE, [_PRODUCT])
    assert len(panel.plots()) == 2
    _drop_between_plots(monkeypatch, _new_panel(qtbot, "pi_drop"))

    study = tmp_path / "study.yaml"
    PanelTemplate.from_panel(panel).to_file(study)
    root, nodes = _plot_nodes(study)
    assert root["kind"] == "sciqlop.time_panel"
    assert [n["kind"] for n in nodes] == ["pi_vdf.slice_plot"] * 2
    assert [n["config"] for n in nodes] == _SAVED_CONFIGS

    configs = sys.modules["pi_vdf"].CONFIGS
    before = len(configs)
    PanelTemplate.from_file(study).apply(_new_panel(qtbot, "pi_second"))
    assert len(configs) == before + 2
    assert list(configs.values())[-2:] == _SAVED_CONFIGS

    for ep in extensions.all_extension_points():
        ep.remove_owner("pi_vdf")
    third = _new_panel(qtbot, "pi_third")
    PanelTemplate.from_file(study).apply(third)
    assert len(third.plots()) == 2
    resaved = tmp_path / "resaved.yaml"
    PanelTemplate.from_panel(third).to_file(resaved)
    assert _plot_nodes(resaved)[1] == nodes
