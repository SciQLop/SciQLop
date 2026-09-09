"""Speasy proxy share URL: panel → JSON config (proxy `/plot?config=` schema v1)."""
import base64
import json

import pytest
from PySide6.QtWidgets import QWidget

from SciQLopPlots import SciQLopPlot, SciQLopGraphInterface


class _Range:
    def __init__(self, start, stop):
        self._start, self._stop = start, stop

    def start(self): return self._start

    def stop(self): return self._stop


class _FakePanel(QWidget):
    def __init__(self, plots, start, stop):
        super().__init__()
        self._range = _Range(start, stop)
        for p in plots:
            p.setParent(self)

    def plots(self):
        return self.findChildren(SciQLopPlot)

    def time_axis_range(self):
        return self._range

    def set_time_axis_range(self, tr):
        self.time_range = tr

    def clear(self):
        pass


def _graph(plot, name, **meta):
    base = {"graph_id": name, "panel_name": "P", "plot_index": 0, "graph_type": "Line"}
    g = SciQLopGraphInterface("Graph", {**base, **meta}, plot)
    g.setObjectName(name)
    return g


@pytest.fixture
def panel(qtbot):
    plot0, plot1, plot2 = SciQLopPlot(), SciQLopPlot(), SciQLopPlot()
    plot0.setObjectName("plot0")
    plot1.setObjectName("plot1")
    plot2.setObjectName("plot2")
    # Bare SciQLopGraphInterface wrappers are Python-owned: keep them alive.
    graphs = [
        _graph(plot0, "imf", kind="speasy", speasy_id="amda/imf", provider_name="Speasy"),
        _graph(plot0, "vp", kind="vp", vp_path="my/vp", provider_name="my/vp"),
        _graph(plot1, "spectro", kind="speasy", speasy_id="cda/DS/spec", provider_name="Speasy",
               graph_type="SciQLopColorMap", knobs={"method": "fast"}),
        _graph(plot2, "static", kind="static"),
    ]
    plot0.y_axis().set_log(True)
    plot1.z_axis().set_log(True)
    p = _FakePanel([plot0, plot1, plot2], start=1577836800.0, stop=1577923200.0)
    p._graphs = graphs
    qtbot.addWidget(p)
    return p


def test_config_lists_speasy_products_per_plot_in_order(panel):
    from SciQLop.components.plotting.ui.proxy_share import proxy_plot_config
    cfg = proxy_plot_config(panel)
    assert cfg["version"] == 1
    assert cfg["time_range"] == {"start": "2020-01-01T00:00:00Z", "stop": "2020-01-02T00:00:00Z"}
    assert cfg["plots"] == [
        {"products": [{"path": "amda/imf", "label": "imf"}], "y_axis": {"log": True}},
        {"products": [{"path": "cda/DS/spec", "label": "spectro",
                       "product_inputs": {"method": "fast"}}],
         "y_axis": {"log": False}, "log_z": True},
    ]


def test_url_is_base64url_without_padding_and_round_trips(panel):
    from SciQLop.components.plotting.ui.proxy_share import proxy_plot_config, proxy_plot_url
    url = proxy_plot_url(panel, "https://sciqlop.lpp.polytechnique.fr/cache/")
    prefix = "https://sciqlop.lpp.polytechnique.fr/cache/plot?config="
    assert url.startswith(prefix)
    encoded = url[len(prefix):]
    assert "=" not in encoded and "+" not in encoded and "/" not in encoded
    padded = encoded + "=" * (-len(encoded) % 4)
    assert json.loads(base64.urlsafe_b64decode(padded)) == proxy_plot_config(panel)


def test_nan_time_range_gives_no_url(qtbot):
    from SciQLop.components.plotting.ui.proxy_share import proxy_plot_config
    plot = SciQLopPlot()
    graph = _graph(plot, "imf", kind="speasy", speasy_id="amda/imf", provider_name="Speasy")
    p = _FakePanel([plot], start=float("nan"), stop=float("nan"))
    p._graphs = [graph]
    qtbot.addWidget(p)
    assert proxy_plot_config(p) is None


def test_no_speasy_graph_gives_no_url(qtbot):
    from SciQLop.components.plotting.ui.proxy_share import proxy_plot_config, proxy_plot_url
    plot = SciQLopPlot()
    graph = _graph(plot, "static", kind="static")
    p = _FakePanel([plot], start=0.0, stop=1.0)
    p._graphs = [graph]
    qtbot.addWidget(p)
    assert proxy_plot_config(p) is None
    assert proxy_plot_url(p, "http://x/cache") is None


def test_export_share_menu_opens_proxy_url_in_browser(panel, qtbot, monkeypatch):
    from PySide6.QtWidgets import QMenu
    from SciQLop.components.plotting.ui import time_sync_panel as tsp

    opened = []
    monkeypatch.setattr(tsp, "_speasy_proxy_url", lambda: "http://proxy/cache")
    monkeypatch.setattr(tsp.QDesktopServices, "openUrl", lambda url: opened.append(url.toString()))
    menu = QMenu()
    tsp.TimeSyncPanel._add_proxy_share_actions(panel, menu)
    labels = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert labels == ["Open in Speasy web viewer"]
    menu.actions()[-1].trigger()
    assert len(opened) == 1 and opened[0].startswith("http://proxy/cache/plot?config=")


def test_export_share_menu_hides_proxy_actions_without_speasy_graphs(qtbot, monkeypatch):
    from PySide6.QtWidgets import QMenu
    from SciQLop.components.plotting.ui import time_sync_panel as tsp

    monkeypatch.setattr(tsp, "_speasy_proxy_url", lambda: "http://proxy/cache")
    plot = SciQLopPlot()
    graph = _graph(plot, "static", kind="static")
    p = _FakePanel([plot], start=0.0, stop=1.0)
    p._graphs = [graph]
    qtbot.addWidget(p)
    menu = QMenu()
    tsp.TimeSyncPanel._add_proxy_share_actions(p, menu)
    assert menu.actions() == []


# --- reverse direction: pasted proxy URL → panel ---------------------------

_CONFIG = {
    "version": 1,
    "time_range": {"start": "2020-01-01T00:00:00Z", "stop": "2020-01-02T00:00:00Z"},
    "plots": [
        {"products": [{"path": "amda/imf", "label": "imf"},
                      {"path": "amda/missing", "label": "gone"}],
         "y_axis": {"log": True}},
        {"products": [{"path": "cda/DS/spec", "label": "spec", "product_inputs": {"method": "fast"}}],
         "y_axis": {"log": False}, "log_z": True},
    ],
}


def _encode(config):
    return base64.urlsafe_b64encode(json.dumps(config).encode()).decode().rstrip("=")


@pytest.mark.parametrize("text", [
    "https://sciqlop.lpp.polytechnique.fr/cache/plot?config=" + _encode(_CONFIG),
    "http://localhost:6543/plot?config=" + _encode(_CONFIG) + "#zoom",
    "config=" + _encode(_CONFIG),
    "  https://x/cache/plot?foo=1&config=" + _encode(_CONFIG) + "  ",
])
def test_config_from_text_accepts_proxy_urls(text):
    from SciQLop.components.plotting.ui.proxy_share import proxy_plot_config_from_text
    assert proxy_plot_config_from_text(text) == _CONFIG


@pytest.mark.parametrize("text", [
    "MMS FGM",
    "https://sciqlop.lpp.polytechnique.fr/cache/plot",
    "config=not-base64!!",
    "config=" + _encode({"version": 1, "plots": []}),
    "config=" + _encode({"version": 1, "time_range": {}, "plots": [{"products": []}]}),
    "config=" + _encode([1, 2]),
])
def test_config_from_text_rejects_non_configs(text):
    from SciQLop.components.plotting.ui.proxy_share import proxy_plot_config_from_text
    assert proxy_plot_config_from_text(text) is None


def test_speasy_product_paths_resolves_ids_in_one_tree_walk():
    from SciQLopPlots import ProductsModelNode, ProductsModelNodeType, ParameterType
    from SciQLop.components.plotting.ui.proxy_share import speasy_product_paths
    root = ProductsModelNode("speasy")
    amda = ProductsModelNode("amda")
    root.add_child(amda)
    leaf = ProductsModelNode("b_gse", "Speasy", {"speasy_id": "amda/imf"},
                             ProductsModelNodeType.PARAMETER, ParameterType.Vector)
    amda.add_child(leaf)
    paths = speasy_product_paths(["amda/imf", "amda/missing"], root=root)
    assert paths == {"amda/imf": leaf.path()}


def test_apply_proxy_config_sets_range_and_plots_products(qtbot, monkeypatch):
    from SciQLop.components.plotting.ui import proxy_share, time_sync_panel
    from SciQLop.components.plotting.ui.proxy_share import apply_proxy_config

    panel = _FakePanel([], start=0.0, stop=1.0)
    qtbot.addWidget(panel)
    calls = []

    def fake_plot_product(target, path, **kwargs):
        calls.append((path, target, kwargs.get("product_inputs")))
        if target is not panel:
            return ("existing", "graph")
        plot = SciQLopPlot()
        plot.setObjectName(f"plot{len(panel.plots())}")
        plot.setParent(panel)
        return (plot, "graph")

    monkeypatch.setattr(time_sync_panel, "plot_product", fake_plot_product)
    monkeypatch.setattr(proxy_share, "speasy_product_paths",
                        lambda ids, root=None: {"amda/imf": ["root", "speasy", "amda", "imf"],
                                                "cda/DS/spec": ["root", "speasy", "cda", "spec"]})
    skipped = apply_proxy_config(panel, _CONFIG)

    assert skipped == ["amda/missing"]
    assert (panel.time_range.start(), panel.time_range.stop()) == (1577836800.0, 1577923200.0)
    assert [c[0] for c in calls] == [["root", "speasy", "amda", "imf"],
                                     ["root", "speasy", "cda", "spec"]]
    assert all(c[1] is panel for c in calls)
    assert [c[2] for c in calls] == [None, {"method": "fast"}]
    plots = panel.plots()
    assert [p.y_axis().log() for p in plots] == [True, False]
    assert plots[1].z_axis().log() is True


def test_apply_proxy_config_groups_products_on_the_same_subplot(qtbot, monkeypatch):
    from SciQLop.components.plotting.ui import proxy_share, time_sync_panel
    from SciQLop.components.plotting.ui.proxy_share import apply_proxy_config

    panel = _FakePanel([], start=0.0, stop=1.0)
    qtbot.addWidget(panel)
    calls = []

    plots = []

    def fake_plot_product(target, path, **kwargs):
        if target is panel:
            plots.append(SciQLopPlot())
            plots[-1].setParent(panel)
            target = None
        calls.append((path[-1], target))
        return (plots[-1], "graph")

    monkeypatch.setattr(time_sync_panel, "plot_product", fake_plot_product)
    monkeypatch.setattr(proxy_share, "speasy_product_paths",
                        lambda ids, root=None: {i: ["root", "speasy", i] for i in ids})
    config = {"version": 1, "time_range": _CONFIG["time_range"],
              "plots": [{"products": [{"path": "a"}, {"path": "b"}]},
                        {"products": [{"path": "c"}]}]}
    assert apply_proxy_config(panel, config) == []
    assert calls == [("a", None), ("b", plots[0]), ("c", None)]


def test_overlay_emits_config_when_a_proxy_url_is_pasted(qtbot):
    from SciQLop.components.plotting.ui.product_search_overlay import ProductSearchOverlay
    overlay = ProductSearchOverlay()
    qtbot.addWidget(overlay)
    received = []
    overlay.proxy_config_pasted.connect(received.append)
    overlay._search_box.setText("https://x/cache/plot?config=" + _encode(_CONFIG))
    assert received == [_CONFIG]
    assert not overlay._debounce.isActive()


# --- colormaps are SciQLopPlottableInterface, not SciQLopGraphInterface -----

def _colormap(plot, name, **meta):
    from SciQLopPlots import SciQLopColorMapInterface
    base = {"graph_id": name, "panel_name": "P", "plot_index": 0, "graph_type": "SciQLopColorMap"}
    cm = SciQLopColorMapInterface({**base, **meta}, plot)
    cm.setObjectName(name)
    return cm


@pytest.fixture
def colormap_panel(qtbot):
    plot = SciQLopPlot()
    plot.setObjectName("plot0")
    cm = _colormap(plot, "spectro", kind="speasy", speasy_id="cda/DS/spec", provider_name="Speasy")
    p = _FakePanel([plot], start=1577836800.0, stop=1577923200.0)
    p._graphs = [cm]
    qtbot.addWidget(p)
    return p


def test_config_exports_colormap_graphs(colormap_panel):
    from SciQLop.components.plotting.ui.proxy_share import proxy_plot_config
    cfg = proxy_plot_config(colormap_panel)
    assert cfg is not None
    assert cfg["plots"] == [{"products": [{"path": "cda/DS/spec", "label": "spectro"}],
                             "y_axis": {"log": False}, "log_z": False}]


def test_panel_reproducer_snippet_includes_colormap_graphs(colormap_panel):
    from SciQLop.components.plotting.ui.graph_context_snippets import panel_reproducer_snippet
    snippet = panel_reproducer_snippet(colormap_panel)
    assert snippet is not None and "cda/DS/spec" in snippet


def test_panel_reproducer_snippet_passes_knobs_as_product_inputs(panel):
    from SciQLop.components.plotting.ui.graph_context_snippets import panel_reproducer_snippet
    snippet = panel_reproducer_snippet(panel)
    assert 'panel.plot_product("cda/DS/spec", product_inputs={\'method\': \'fast\'})' in snippet
