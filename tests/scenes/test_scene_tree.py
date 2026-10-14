import numpy as np
import pytest
from PySide6.QtCore import QModelIndex, Qt

from SciQLop.components.scenes import registry, tree

from ..fixtures import *  # noqa: F401, F403
from .helpers import overlay_text, proj_of

SHUE = ["Models", "Earth", "magnetopause", "Shue 1998 (Dp=2 nPa, Bz=0)"]
EARTH_SCENE = ["Scenes", "Earth environment"]


@pytest.mark.parametrize("kind, on_scene, expected", [
    ("scene", False, "plot_scene"), ("scene", True, "plot_scene"),
    ("boundary", True, "set_boundary"), ("boundary", False, "refuse"),
    ("product", True, "add_trajectory"), ("product", False, "plot_product"),
    ("layer", False, "attach_layer"), ("layer", True, "attach_layer"),
])
def test_drop_table(kind, on_scene, expected):
    assert tree.drop_handler(kind, on_scene).__name__ == expected


def _child(model, parent, name):
    rows = (model.index(r, 0, parent) for r in range(model.rowCount(parent)))
    return next(i for i in rows if model.data(i, Qt.ItemDataRole.DisplayRole) == name)


def _mime(path):
    from SciQLopPlots import ProductsModel
    model = ProductsModel.instance()
    index = QModelIndex()
    for name in path:
        index = _child(model, index, name)
    return model.mimeData([index])


def _drop(panel, target, path):
    panel._impl._product_plot_callback.call(target, _mime(path))


def _drop_as_new_plot(panel, index, path):
    """What SciQLopPlots does for a drop on an empty panel or between plots: make a
    time-series placeholder at the drop index, then hand it to the callback."""
    from SciQLopPlots import PlotType
    _drop(panel, panel._impl.create_plot(index, PlotType.TimeSeries), path)


def _plot_with_data(panel):
    panel.plot_data(np.arange(3.0), np.arange(3.0))
    return panel._impl.plots()[-1].data()


def _scene_plots(panel):
    from SciQLop.components.scenes.scene_plot import scene_plot_for
    return [scene_plot_for(p) for p in panel._impl.plots()]


def _status_message(panel):
    return panel._impl.window().statusBar().currentMessage()


def test_registering_adds_tree_nodes(registered):
    from SciQLopPlots import ProductsModel
    scene = ProductsModel.node(EARTH_SCENE)
    model = ProductsModel.node(SHUE)
    assert scene.metadata()["sciqlop_kind"] == "scene"
    assert model.metadata()["sciqlop_kind"] == "boundary" and "doi:" in model.metadata()["description"]


def test_registering_twice_keeps_one_node_per_item(main_window, registered):
    from SciQLopPlots import ProductsModel
    from SciQLop.components.plugins.backend.loader.context import PluginContext
    from SciQLop.plugins.planetary_scenes import activate
    activate(PluginContext("planetary_scenes", "1.0.0", main_window, frozenset()))
    assert ProductsModel.node(["Scenes"]).children_count() == len(registry.SCENES.list())
    assert ProductsModel.node(SHUE[:-1]).children_count() == 1


def test_smart_search_corpus_sees_the_model_description(registered):
    from SciQLopPlots import ProductsFlatFilterModel, ProductsModel
    corpus = ProductsFlatFilterModel(ProductsModel.instance()).corpus_snapshot()
    assert any("magnetopause" in k and "doi:10.1029/98JA01103" in v for k, v in corpus.items())


def test_a_layer_node_is_tagged_with_its_kind(main_window):
    from SciQLopPlots import ProductsModel
    from SciQLop.user_api.layers._provider import LayerProvider

    def scene_tree_test_layer(start: float, stop: float):
        return []

    provider = LayerProvider("scene_tree_test/kind_tag", scene_tree_test_layer)
    try:
        assert ProductsModel.node(provider.path).metadata()["sciqlop_kind"] == "layer"
    finally:
        ProductsModel.instance().remove_node(provider.path[:-1])


def test_a_scene_dropped_on_an_empty_panel_is_its_only_plot(plot_panel, registered, qtbot):
    _drop_as_new_plot(plot_panel, 0, EARTH_SCENE)
    qtbot.waitUntil(lambda: len(_scene_plots(plot_panel)) == 1, timeout=5000)
    sps = _scene_plots(plot_panel)
    assert sps[0] is not None and sps[0].scene.name == "Earth environment"


def test_a_scene_dropped_between_plots_takes_the_drop_place(plot_panel, registered, qtbot):
    first, last = _plot_with_data(plot_panel), _plot_with_data(plot_panel)
    _drop_as_new_plot(plot_panel, 1, EARTH_SCENE)
    qtbot.waitUntil(lambda: len(_scene_plots(plot_panel)) == 3, timeout=5000)
    plots = [p.data() for p in plot_panel._impl.plots()]
    assert plots[0] is first and plots[2] is last and _scene_plots(plot_panel)[1] is not None


def test_a_boundary_dropped_as_a_new_plot_leaves_no_empty_plot(plot_panel, registered, qtbot):
    _drop_as_new_plot(plot_panel, 0, SHUE)
    qtbot.waitUntil(lambda: plot_panel._impl.plot_count() == 0, timeout=5000)
    assert "scene plot" in _status_message(plot_panel)


def test_a_boundary_dropped_on_a_plain_plot_is_refused_on_its_overlay(plot_panel, registered, qtbot):
    plot = _plot_with_data(plot_panel)
    _drop(plot_panel, plot, SHUE)
    qtbot.waitUntil(lambda: "scene plot" in overlay_text(plot), timeout=5000)
    assert _scene_plots(plot_panel) == [None]


def test_a_boundary_dropped_on_a_pane_swaps_the_scene_boundary(plot_panel, registered):
    sp = plot_panel.plot_scene("Earth environment")
    before = sp._boundary_graphs["magnetopause"]
    _drop(plot_panel, proj_of(sp).subplot(1), SHUE)
    assert sp._boundary_graphs["magnetopause"] is not before


def test_a_boundary_of_another_body_is_refused_on_the_scene(plot_panel, registered, qtbot):
    sp = plot_panel.plot_scene("Earth environment")
    pane = proj_of(sp).subplot(0)
    _drop(plot_panel, pane, ["Models", "Mars", "mpb", "Vignes 2000 MPB"])
    qtbot.waitUntil(lambda: "mars model" in overlay_text(pane), timeout=5000)
    assert set(sp._boundary_graphs) == {"magnetopause", "bow_shock"}


@pytest.fixture
def position_products(main_window):
    from SciQLopPlots import ProductsModel
    from SciQLop.core.enums import ParameterType
    from SciQLop.core.models import ProductsModelNodeType, add_product_node
    folder = ["speasy", "scene_tree_test"]
    for name in ("mms1_rtn", "mms1_pos"):
        add_product_node(folder, name, "speasy", {"speasy_id": f"cda/X/{name}"},
                         ProductsModelNodeType.PARAMETER, ParameterType.Vector)
    yield folder
    ProductsModel.instance().remove_node(folder)


@pytest.mark.parametrize("name, refusal", [("mms1_rtn", "RTN"), ("mms1_pos", "no COORDINATE_SYSTEM")])
def test_a_position_product_dropped_on_a_scene_goes_through_add_trajectory(
        plot_panel, registered, fake_speasy, position_products, qtbot, name, refusal):
    sp = plot_panel.plot_scene("Earth environment")
    proj = proj_of(sp)
    plots_before, graphs_before = len(plot_panel._impl.plots()), len(proj.plottables())
    _drop(plot_panel, proj.subplot(2), position_products + [name])
    qtbot.waitUntil(lambda: refusal in overlay_text(proj.subplot(0)), timeout=5000)
    assert (f"cda/X/{name}", {}) in fake_speasy   # resolved through the tree node's speasy_id
    assert len(plot_panel._impl.plots()) == plots_before
    assert len(proj.plottables()) == graphs_before + 1
    assert proj.time_color_enabled()


def test_a_failing_drop_never_raises_and_shows_why(plot_panel, registered, qtbot, monkeypatch):
    import SciQLopPlots
    from SciQLopPlots import ProductsModelNode
    plot = _plot_with_data(plot_panel)
    mime = _mime(EARTH_SCENE)
    monkeypatch.setattr(SciQLopPlots.ProductsModel, "node",
                        lambda path: ProductsModelNode("odd", {"sciqlop_kind": "unheard-of"}))
    plot_panel._impl._product_plot_callback.call(plot, mime)
    qtbot.waitUntil(lambda: "Earth environment" in overlay_text(plot), timeout=5000)


def test_a_refusal_on_a_deleted_plot_does_not_raise(plot_panel, qtbot):
    import shiboken6
    plot = _plot_with_data(plot_panel)
    plot_panel._impl.remove_plot(plot)
    qtbot.waitUntil(lambda: not shiboken6.isValid(plot), timeout=5000)
    tree.show_refusal(plot, None, "nowhere to show this")


def test_the_search_overlay_plots_a_scene(plot_panel, registered, qtbot):
    plot_panel._impl._on_overlay_product_selected(EARTH_SCENE)
    qtbot.waitUntil(lambda: len(_scene_plots(plot_panel)) == 1, timeout=5000)
    assert _scene_plots(plot_panel)[0] is not None


def test_plot_product_on_a_panel_refuses_a_model_visibly(plot_panel, registered):
    from SciQLop.components.plotting.ui.time_sync_panel import plot_product
    assert plot_product(plot_panel._impl, SHUE) is None
    assert "scene plot" in _status_message(plot_panel)
    assert plot_panel._impl.plot_count() == 0


def _context_menu_actions(main_window, panel, path):
    from PySide6.QtWidgets import QMenu
    from SciQLop.components.products.product_context_menu import _build_plot_target_menu
    menu = QMenu()
    _build_plot_target_menu(menu, path, main_window)
    panel_menu = next(a.menu() for a in menu.actions() if a.text() == panel.name)
    return menu, {a.text(): a for a in panel_menu.actions()}


def test_the_context_menu_new_plot_entry_plots_a_scene(plot_panel, main_window, registered, qtbot):
    menu, actions = _context_menu_actions(main_window, plot_panel, EARTH_SCENE)
    actions["+ New plot"].trigger()
    qtbot.waitUntil(lambda: len(_scene_plots(plot_panel)) == 1, timeout=5000)
    assert _scene_plots(plot_panel)[0] is not None


def test_the_context_menu_puts_a_model_on_the_chosen_scene_plot(plot_panel, main_window, registered):
    sp = plot_panel.plot_scene("Earth environment")
    before = sp._boundary_graphs["magnetopause"]
    menu, actions = _context_menu_actions(main_window, plot_panel, SHUE)
    plot_entry = next(a for text, a in actions.items() if text not in ("+ New plot", ""))
    plot_entry.trigger()
    assert sp._boundary_graphs["magnetopause"] is not before
