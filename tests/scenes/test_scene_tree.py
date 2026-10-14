import pytest
from PySide6.QtCore import QModelIndex, Qt

from SciQLop.components.scenes import registry, tree

from ..fixtures import *  # noqa: F401, F403
from .test_scene_plot import earth, overlay_text, proj_of  # noqa: F401
from .test_trajectory import fake_speasy  # noqa: F401

SHUE = ["Models", "Earth", "magnetopause", "Shue 1998 (Dp=2 nPa, Bz=0)"]


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


def _first_plot(panel):
    from SciQLopPlots import PlotType
    panel._impl.create_plot(0, PlotType.TimeSeries)
    return panel._impl.plots()[0]


def _scene_plots(panel):
    from SciQLop.components.scenes.scene_plot import scene_plot_for
    plots = [ptr.data() for ptr in panel._impl.plots()]   # plots() hands out smart-pointer wrappers
    return [sp for sp in map(scene_plot_for, plots) if sp is not None]


@pytest.fixture
def registered(main_window, earth):
    from SciQLop.plugins.planetary_scenes import load
    load(main_window)


def test_registering_adds_tree_nodes(registered):
    from SciQLopPlots import ProductsModel
    scene = ProductsModel.node(["Scenes", "Earth environment"])
    model = ProductsModel.node(SHUE)
    assert scene.metadata()["sciqlop_kind"] == "scene"
    assert model.metadata()["sciqlop_kind"] == "boundary" and "doi:" in model.metadata()["description"]


def test_registering_twice_keeps_one_node_per_item(main_window, registered):
    from SciQLopPlots import ProductsModel
    from SciQLop.plugins.planetary_scenes import load
    load(main_window)
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


def test_dropping_a_scene_creates_a_scene_plot(plot_panel, registered, qtbot):
    _drop(plot_panel, _first_plot(plot_panel), ["Scenes", "Earth environment"])
    qtbot.waitUntil(lambda: len(_scene_plots(plot_panel)) == 1, timeout=5000)
    assert _scene_plots(plot_panel)[0].scene.name == "Earth environment"


def test_a_boundary_dropped_on_a_plain_plot_is_refused_on_its_overlay(plot_panel, registered, qtbot):
    plot = _first_plot(plot_panel)
    _drop(plot_panel, plot, SHUE)
    qtbot.waitUntil(lambda: "scene plot" in overlay_text(plot), timeout=5000)
    assert _scene_plots(plot_panel) == []


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
    plot = _first_plot(plot_panel)
    mime = _mime(["Scenes", "Earth environment"])
    monkeypatch.setattr(SciQLopPlots.ProductsModel, "node",
                        lambda path: ProductsModelNode("odd", {"sciqlop_kind": "unheard-of"}))
    plot_panel._impl._product_plot_callback.call(plot, mime)
    qtbot.waitUntil(lambda: "Earth environment" in overlay_text(plot), timeout=5000)
