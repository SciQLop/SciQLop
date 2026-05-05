"""End-to-end tests for graph context attachment via the producer paths.

Heavier than test_graph_context.py — these go through real
SciQLopMultiPlotPanel + plot_product / plot_static_data / plot_function
paths.
"""
import pytest


def test_post_plot_invokes_attach_context_for_speasy(qtbot, monkeypatch):
    """When _post_plot runs on a speasy provider, attach_context is called
    with kind='speasy'."""
    from SciQLop.components.plotting.ui import time_sync_panel as tsp
    from PySide6.QtCore import QObject

    captured = {}

    def _capture_attach(graph, ctx, rich=None):
        captured["graph"] = graph
        captured["ctx"] = ctx
        captured["rich"] = rich

    monkeypatch.setattr(tsp, "attach_context", _capture_attach)
    monkeypatch.setattr(tsp, "_set_product_path", lambda *a, **kw: None)
    monkeypatch.setattr(tsp, "_register_graph_hints", lambda *a, **kw: None)
    monkeypatch.setattr(tsp, "_attach_knob_state", lambda *a, **kw: None)

    class _FakeNode:
        def name(self): return "imf"
        def metadata(self, key=None):
            if key == "speasy_id":
                return "amda/imf"
            return {}

    class _FakeProvider:
        name = "Speasy"

    class _FakeGraph(QObject):
        def __init__(self, name):
            super().__init__()
            self.setObjectName(name)

        def set_name(self, n): self.setObjectName(n)
        def name(self): return self.objectName()

    class _FakePlot(QObject):
        def __init__(self):
            super().__init__()
            self.setObjectName("plot0")

    class _FakeTarget:
        def plots(self): return [_FakePlot()]
        def windowTitle(self): return "PanelX"

    callback = type("C", (), {"_post_fetch": None})()
    plot, graph = _FakePlot(), _FakeGraph("g0")
    tsp._post_plot((plot, graph), _FakeProvider(), _FakeNode(),
                   callback, _FakeTarget(),
                   "amda//imf", existing_plot=None)

    assert captured["ctx"].kind == "speasy"
    assert captured["ctx"].speasy_id == "amda/imf"
    assert captured["ctx"].provider_name == "Speasy"


def test_post_plot_invokes_attach_context_for_vp(qtbot, monkeypatch):
    """When _post_plot runs on an EasyProvider (VP), attach_context is
    called with kind='vp' and rich refs containing the callback."""
    from SciQLop.components.plotting.ui import time_sync_panel as tsp
    from SciQLop.components.plotting.backend.easy_provider import EasyProvider
    from PySide6.QtCore import QObject

    captured = {}

    def _capture_attach(graph, ctx, rich=None):
        captured["graph"] = graph
        captured["ctx"] = ctx
        captured["rich"] = rich

    monkeypatch.setattr(tsp, "attach_context", _capture_attach)
    monkeypatch.setattr(tsp, "_set_product_path", lambda *a, **kw: None)
    monkeypatch.setattr(tsp, "_register_graph_hints", lambda *a, **kw: None)
    monkeypatch.setattr(tsp, "_attach_knob_state", lambda *a, **kw: None)

    def my_vp_callback(start, stop):
        return None

    class _FakeNode:
        def name(self): return "vp_node"
        def metadata(self, key=None): return None if key else {}

    fake_provider = EasyProvider.__new__(EasyProvider)
    fake_provider._path = ["root", "my_vp"]
    fake_provider._name = "my_vp_callback-1"
    fake_provider._callback = my_vp_callback
    fake_provider._knobs_model = None

    class _FakeGraph(QObject):
        def __init__(self, name):
            super().__init__()
            self.setObjectName(name)

    class _FakePlot(QObject):
        def __init__(self):
            super().__init__()
            self.setObjectName("plot0")

    class _FakeTarget:
        def plots(self): return [_FakePlot()]
        def windowTitle(self): return "PanelY"

    callback = type("C", (), {"_post_fetch": None})()
    plot, graph = _FakePlot(), _FakeGraph("g_vp")
    tsp._post_plot((plot, graph), fake_provider, _FakeNode(),
                   callback, _FakeTarget(),
                   "root//my_vp", existing_plot=None)

    assert captured["ctx"].kind == "vp"
    assert captured["ctx"].vp_path == "root/my_vp"
    assert captured["ctx"].provider_name == "my_vp_callback-1"
    assert captured["ctx"].callback_qualname == my_vp_callback.__qualname__
    assert captured["rich"] is not None
    assert captured["rich"].callback is my_vp_callback


def test_plot_static_data_attaches_static_context(qtbot, monkeypatch):
    from SciQLop.components.plotting.ui import time_sync_panel as tsp
    from PySide6.QtCore import QObject

    captured = []
    monkeypatch.setattr(tsp, "attach_context",
                        lambda g, ctx, rich=None: captured.append(ctx))

    class _FakeGraph(QObject):
        def __init__(self):
            super().__init__()
            self.setObjectName("sg")

    class _FakePlot(QObject):
        def __init__(self):
            super().__init__()
            self.setObjectName("plot0")

    class _FakeTarget:
        def plot(self, *a, **kw): return (_FakePlot(), _FakeGraph())
        def plots(self): return [_FakePlot()]
        def windowTitle(self): return "P"

    monkeypatch.setattr(tsp, "_resolve_plot_target",
                         lambda p, kwargs: (_FakeTarget(), None))

    tsp.plot_static_data(None, [1, 2, 3], [4, 5, 6])
    assert len(captured) == 1
    assert captured[0].kind == "static"
    assert captured[0].provider_name is None


def test_plot_function_attaches_function_context(qtbot, monkeypatch):
    from SciQLop.components.plotting.ui import time_sync_panel as tsp
    from PySide6.QtCore import QObject

    captured = []
    monkeypatch.setattr(tsp, "attach_context",
                        lambda g, ctx, rich=None: captured.append((ctx, rich)))

    class _FakeGraph(QObject):
        def __init__(self):
            super().__init__()
            self.setObjectName("fg")

    class _FakePlot(QObject):
        def __init__(self):
            super().__init__()
            self.setObjectName("plot0")

    class _FakeTarget:
        def plot(self, *a, **kw): return (_FakePlot(), _FakeGraph())
        def plots(self): return [_FakePlot()]
        def windowTitle(self): return "P"

    monkeypatch.setattr(tsp, "_resolve_plot_target",
                         lambda p, kwargs: (_FakeTarget(), None))

    def my_func(start, stop): return ([0], [0])
    tsp.plot_function(None, my_func)

    assert len(captured) == 1
    ctx, rich = captured[0]
    assert ctx.kind == "function"
    # qualname will be "test_plot_function_attaches_function_context.<locals>.my_func"
    assert "my_func" in ctx.callback_qualname
    assert rich is not None
    assert rich.callback is my_func


def test_add_graph_context_actions_shows_copy_for_speasy(qtbot, monkeypatch):
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QMenu
    from SciQLop.components.plotting.ui.graph_context_menu import (
        add_graph_context_actions,
    )
    from SciQLop.core.graph_context import build_speasy_ctx
    from SciQLop.components.plotting.backend.data_provider import providers

    class _FakeGraph(QObject):
        def __init__(self, name):
            super().__init__(); self.setObjectName(name)
        _md = {}
        def meta_data(self): return dict(self._md)
        def set_meta_data(self, d): self._md = dict(d)
        def name(self): return self.objectName()

    class _FakeProvider:
        name = "FakeSpeasy"
        def python_snippet(self, ctx):
            return f"# snippet for {ctx.speasy_id}"

    g = _FakeGraph("g_menu")
    ctx = build_speasy_ctx(g, panel_name="P", plot_index=0,
                           speasy_id="a/b", graph_type="Line")
    ctx.provider_name = "FakeSpeasy"
    g.set_meta_data(ctx.to_meta_data())

    providers["FakeSpeasy"] = _FakeProvider()
    try:
        menu = QMenu()
        add_graph_context_actions(menu, [g])
        labels = [a.text() for a in menu.actions()]
        assert any("Copy Python code" in lbl for lbl in labels)
    finally:
        providers.pop("FakeSpeasy", None)


def test_add_graph_context_actions_omits_when_no_snippet(qtbot, monkeypatch):
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QMenu
    from SciQLop.components.plotting.ui.graph_context_menu import (
        add_graph_context_actions,
    )
    from SciQLop.core.graph_context import build_static_ctx

    class _FakeGraph(QObject):
        def __init__(self, name):
            super().__init__(); self.setObjectName(name)
        _md = {}
        def meta_data(self): return dict(self._md)
        def set_meta_data(self, d): self._md = dict(d)
        def name(self): return self.objectName()

    g = _FakeGraph("g_static")
    ctx = build_static_ctx(g, panel_name="P", plot_index=0,
                            graph_type="Line")
    g.set_meta_data(ctx.to_meta_data())

    menu = QMenu()
    add_graph_context_actions(menu, [g])
    labels = [a.text() for a in menu.actions()]
    assert not any("Copy Python code" in lbl for lbl in labels)


def test_add_graph_context_actions_clipboard(qtbot, monkeypatch):
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QMenu, QApplication
    from SciQLop.components.plotting.ui.graph_context_menu import (
        add_graph_context_actions,
    )
    from SciQLop.core.graph_context import build_speasy_ctx
    from SciQLop.components.plotting.backend.data_provider import providers

    class _FakeGraph(QObject):
        def __init__(self, name):
            super().__init__(); self.setObjectName(name)
        _md = {}
        def meta_data(self): return dict(self._md)
        def set_meta_data(self, d): self._md = dict(d)
        def name(self): return self.objectName()

    class _FakeProvider:
        name = "FakeSpeasy2"
        def python_snippet(self, ctx):
            return "PASTE_ME"

    g = _FakeGraph("g_clip")
    ctx = build_speasy_ctx(g, panel_name="P", plot_index=0,
                           speasy_id="x/y", graph_type="Line")
    ctx.provider_name = "FakeSpeasy2"
    g.set_meta_data(ctx.to_meta_data())
    providers["FakeSpeasy2"] = _FakeProvider()
    try:
        menu = QMenu()
        add_graph_context_actions(menu, [g])
        for a in menu.actions():
            if "Copy Python code" in a.text():
                a.trigger()
                break
        assert QApplication.clipboard().text() == "PASTE_ME"
    finally:
        providers.pop("FakeSpeasy2", None)


def test_show_context_menu_wires_add_graph_context_actions():
    """The _show_context_menu method invokes add_graph_context_actions on
    the panel's graphs.

    We don't drive the menu live — QMenu.exec() enters a native modal loop
    that pytest can't unblock (Shiboken dispatches it through the C++ vtable,
    bypassing any Python-level monkeypatch). Verifying the wiring via source
    inspection is sufficient: both add_graph_context_actions and _all_graphs
    have their own behavioral tests.
    """
    import inspect
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    src = inspect.getsource(TimeSyncPanel._show_context_menu)
    assert "add_graph_context_actions" in src
    assert "_all_graphs(self)" in src


def test_all_graphs_returns_meta_data_capable_children(qtbot):
    """_all_graphs walks panel.plots() children and returns those with both
    meta_data() and set_meta_data() — i.e., SciQLopPlots' graph interfaces.
    """
    from PySide6.QtCore import QObject
    from SciQLop.components.plotting.ui.time_sync_panel import _all_graphs

    class _GraphLike(QObject):
        def meta_data(self): return {}
        def set_meta_data(self, d): pass

    class _NotAGraph(QObject):
        pass

    class _FakePlot(QObject):
        def __init__(self):
            super().__init__()
            self.setObjectName("plot0")
            self._g1 = _GraphLike(parent=self)
            self._g2 = _NotAGraph(parent=self)
            self._g3 = _GraphLike(parent=self)

    class _FakePanel:
        def __init__(self):
            self._plot = _FakePlot()
        def plots(self):
            return [self._plot]

    graphs = _all_graphs(_FakePanel())
    assert len(graphs) == 2
    for g in graphs:
        assert hasattr(g, "meta_data") and hasattr(g, "set_meta_data")


def test_graph_context_section_renders_with_speasy_ctx(qtbot, monkeypatch):
    """GraphContextSection builds, fills labels, and exposes working buttons."""
    from PySide6.QtCore import QObject
    from SciQLop.core.graph_context import attach_context, build_speasy_ctx
    from SciQLop.components.plotting.ui.graph_context_inspector.section import (
        GraphContextSection,
    )
    from SciQLop.components.plotting.backend.data_provider import providers

    class _FakeGraph(QObject):
        def __init__(self, name):
            super().__init__(); self.setObjectName(name); self._md = {}
        def meta_data(self): return dict(self._md)
        def set_meta_data(self, d): self._md = dict(d)
        def name(self): return self.objectName()

    class _FakeProvider:
        name = "FakeSpeasy3"
        def python_snippet(self, ctx):
            return "import speasy as spz"
        def extended_metadata(self, ctx):
            return {"speasy_id": ctx.speasy_id, "inventory": {"x": 1}}

    g = _FakeGraph("g_sec")
    ctx = build_speasy_ctx(g, panel_name="P", plot_index=0,
                           speasy_id="x/y", graph_type="Line")
    ctx.provider_name = "FakeSpeasy3"
    g.set_meta_data(ctx.to_meta_data())
    providers["FakeSpeasy3"] = _FakeProvider()
    try:
        section = GraphContextSection(g)
        qtbot.addWidget(section)
        assert "Speasy" in section._labels["Source"].text()
        assert "x/y" in section._labels["Source"].text()
        assert section._copy_btn.isEnabled()
        assert section._show_btn.isEnabled()
    finally:
        providers.pop("FakeSpeasy3", None)


def test_graph_context_section_no_context_disables_buttons(qtbot):
    from PySide6.QtCore import QObject
    from SciQLop.components.plotting.ui.graph_context_inspector.section import (
        GraphContextSection,
    )

    class _FakeGraph(QObject):
        def __init__(self, name):
            super().__init__(); self.setObjectName(name); self._md = {}
        def meta_data(self): return dict(self._md)

    g = _FakeGraph("g_sec_empty")
    section = GraphContextSection(g)
    qtbot.addWidget(section)
    assert not section._copy_btn.isEnabled()
    assert not section._show_btn.isEnabled()
