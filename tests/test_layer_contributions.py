"""Annotation layers are contributions to sciqlop.layers, keyed by product-tree path (Layers/...)."""
import pytest

from tests.fixtures import *  # noqa: F401,F403

from SciQLop.core.extensions import owned_by
from SciQLop.user_api.layers import Marker, register_layer, remove_layer
from SciQLop.user_api.layers._provider import LAYERS, define_layer, follow_layers


def f1(start: float, stop: float, threshold: float = 0.5):
    return [Marker(time=start, value=1.0)]


def f2(start: float, stop: float, threshold: float = 0.5):
    return [Marker(time=start, value=2.0)]


def f_level(start: float, stop: float, threshold: float = 0.5, level: float = 1.0):
    return [Marker(time=start, value=3.0)]


@pytest.fixture
def layers(qapp, main_window):
    follow_layers()
    yield
    for key in LAYERS.keys():
        if key.startswith("Layers/lc/"):
            LAYERS.remove(key)


def _node(path):
    from SciQLopPlots import ProductsModel
    return ProductsModel.instance().node(path)


def _plot(plot_panel, qtbot):
    """The panel and its first plot as a SciQLopPlot: `plots()` hands back interface pointers."""
    from SciQLopPlots import PlotType, SciQLopPlot
    impl = plot_panel._get_impl_or_raise()
    impl.create_plot(0, PlotType.TimeSeries)
    qtbot.wait(50)
    name = impl.plots()[0].objectName()
    return impl, next(p for p in impl.findChildren(SciQLopPlot) if p.objectName() == name)


def test_a_layer_is_a_contribution(layers):
    register_layer("lc/a")(f1)
    assert "Layers/lc/a" in LAYERS
    assert _node(["Layers", "lc", "a"]) is not None


def test_same_signature_rerun_swaps_the_body(layers):
    p1 = define_layer("lc/b", f1)
    p2 = define_layer("lc/b", f2)
    assert p1 is p2
    assert p1.callback(0.0, 1.0)[0].value == 2.0


def f_default(start: float, stop: float, threshold: float = 0.9):
    return [Marker(time=start, value=1.0)]


def test_same_signature_rerun_refreshes_knob_defaults(layers):
    p = define_layer("lc/k", f1)
    define_layer("lc/k", f_default)
    assert p.get_knobs()[0].default == 0.9


def test_changed_signature_refreshes_knobs(layers):
    p1 = define_layer("lc/c", f1)
    p2 = define_layer("lc/c", f_level)
    assert p1 is p2
    assert "level" in {k.name for k in p1.get_knobs()}
    assert p1.callback(0.0, 1.0)[0].value == 3.0


def test_rerun_sets_the_scope(layers):
    p = define_layer("lc/s", f1, scope="panel")
    define_layer("lc/s", f2, scope="plot")
    assert p.resolve_scope() == "plot"


def test_same_function_at_two_paths_gives_two_layers(layers):
    a = define_layer("lc/one", f1)
    b = define_layer("lc/two", f1)
    assert a is not b
    assert {"Layers/lc/one", "Layers/lc/two"} <= set(LAYERS.keys())


def test_withdrawal_removes_the_node(layers, plot_panel, qtbot):
    from SciQLop.components.plotting.ui.time_sync_panel import attach_layer
    with owned_by("layer_demo"):
        define_layer("lc/w", f1)
    assert LAYERS.owner_of("Layers/lc/w") == "layer_demo"
    LAYERS.remove_owner("layer_demo")
    assert "Layers/lc/w" not in LAYERS
    assert _node(["Layers", "lc", "w"]) is None
    panel, plot = _plot(plot_panel, qtbot)
    assert attach_layer(plot, ["Layers", "lc", "w"], panel=panel) is None


def test_takeover_from_another_owner_is_logged(layers, monkeypatch):
    from SciQLop.user_api.layers import _provider
    warnings = []
    monkeypatch.setattr(_provider.log, "warning", warnings.append)
    with owned_by("a"):
        _provider.LayerProvider("lc/t", f1)
    with owned_by("b"):
        _provider.LayerProvider("lc/t", f2)
    takeovers = [w for w in warnings if "Layers/lc/t" in w]
    assert len(takeovers) == 1 and "of a" in takeovers[0] and "from b" in takeovers[0]
    assert LAYERS.owner_of("Layers/lc/t") == "b"


def test_redefining_a_plugin_layer_takes_it_over(layers, monkeypatch):
    from SciQLop.user_api.layers import _provider
    warnings = []
    monkeypatch.setattr(_provider.log, "warning", warnings.append)
    with owned_by("p"):
        p1 = define_layer("lc/own", f1)
    p2 = define_layer("lc/own", f2)
    assert p1 is p2
    assert LAYERS.owner_of("Layers/lc/own") == "user"
    takeovers = [w for w in warnings if "Layers/lc/own" in w]
    assert len(takeovers) == 1 and "of p" in takeovers[0] and "from user" in takeovers[0]
    LAYERS.remove_owner("p")
    assert "Layers/lc/own" in LAYERS


def test_remove_layer(layers):
    register_layer("lc/a")(f1)
    remove_layer("lc/a")
    assert "Layers/lc/a" not in LAYERS
    assert _node(["Layers", "lc", "a"]) is None
    with pytest.raises(LookupError):
        remove_layer("lc/nowhere")


def test_attach_layer_finds_the_provider(layers, plot_panel, qtbot):
    from SciQLop.components.plotting.ui.time_sync_panel import attach_layer
    define_layer("lc/attach", f1)
    panel, plot = _plot(plot_panel, qtbot)
    renderer = attach_layer(plot, ["Layers", "lc", "attach"], panel=panel)
    assert renderer is not None
    assert renderer._callback is LAYERS.get("Layers/lc/attach").callback


LAYER_CELL = """
def lc_cell(start: float, stop: float, threshold: float = 0.5):
    return [Marker(time=start, value={value})]
"""


def test_layer_cell_rerun_updates_an_attached_layer(layers, plot_panel, qtbot):
    from SciQLop.components.plotting.ui.time_sync_panel import attach_layer
    from SciQLop.user_api.layers.magic import layer_magic
    layer_magic("--path lc/cell", LAYER_CELL.format(value=1.0), local_ns={})
    panel, plot = _plot(plot_panel, qtbot)
    renderer = attach_layer(plot, ["Layers", "lc", "cell"], panel=panel)
    layer_magic("--path lc/cell", LAYER_CELL.format(value=2.0), local_ns={})
    assert renderer._callback(0.0, 1.0)[0].value == 2.0
