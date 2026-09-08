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


def test_export_share_menu_gets_proxy_actions(panel, qtbot, monkeypatch):
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QMenu
    from SciQLop.components.plotting.ui import time_sync_panel as tsp

    monkeypatch.setattr(tsp, "_speasy_proxy_url", lambda: "http://proxy/cache")
    menu = QMenu()
    tsp.TimeSyncPanel._add_proxy_share_actions(panel, menu)
    labels = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert labels == ["Copy Speasy proxy plot URL", "Open in Speasy proxy…"]
    menu.actions()[1].trigger()
    assert QGuiApplication.clipboard().text().startswith("http://proxy/cache/plot?config=")


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
