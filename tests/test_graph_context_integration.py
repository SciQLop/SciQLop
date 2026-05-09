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


def test_add_graph_context_actions_builds_hierarchical_submenu(qtbot, monkeypatch):
    """The right-click submenu has a single 'Copy Python code' entry that
    contains panel/plot/per-graph items underneath.
    """
    import numpy as np
    from PySide6.QtWidgets import QMenu
    from SciQLop.components.plotting.ui.time_sync_panel import (
        TimeSyncPanel, plot_static_data,
    )
    from SciQLop.components.plotting.ui.graph_context_menu import (
        add_graph_context_actions,
    )
    from SciQLop.core.graph_context import build_speasy_ctx, attach_context
    from SciQLop.components.plotting.backend.data_provider import providers

    class _FakeProvider:
        name = "FakeProv"
        def python_snippets(self, ctx, graph=None):
            return {"Reproduce in SciQLop": f"# {ctx.speasy_id}",
                    "Notebook (matplotlib)": f"# nb {ctx.speasy_id}"}

    providers["FakeProv"] = _FakeProvider()
    panel = TimeSyncPanel('hier', show_search_overlay=False)
    qtbot.addWidget(panel)
    _, graph = plot_static_data(panel, np.array([0.0, 1.0]), np.array([0.0, 1.0]))
    ctx = build_speasy_ctx(graph, panel_name='hier', plot_index=0,
                           speasy_id='x/y', graph_type='Line',
                           product_path=['x', 'y'])
    ctx.provider_name = "FakeProv"
    attach_context(graph, ctx)
    try:
        menu = QMenu()
        add_graph_context_actions(menu, panel)
        # Expect exactly one submenu titled "Copy Python code"
        copy_actions = [a for a in menu.actions()
                        if a.menu() and a.text() == "Copy Python code"]
        assert len(copy_actions) == 1
        sub = copy_actions[0].menu()
        labels = [a.text() for a in sub.actions() if a.text()]
        # Direct items: Panel "<title>" and Plot 0 (...)
        assert any('Panel "hier"' in l for l in labels)
        assert any(l.startswith("Plot 0") for l in labels)
        # Per-graph submenu titled with the graph name
        graph_subs = [a for a in sub.actions() if a.menu() and a.menu().actions()]
        assert graph_subs, "expected per-graph submenu"
        graph_sub = graph_subs[0].menu()
        graph_labels = [a.text() for a in graph_sub.actions()]
        assert "Reproduce in SciQLop" in graph_labels
        assert "Notebook (matplotlib)" in graph_labels
    finally:
        providers.pop("FakeProv", None)


def test_add_graph_context_actions_omits_when_no_snippets(qtbot):
    """No source-bound graphs and no per-graph snippets → no submenu added."""
    import numpy as np
    from PySide6.QtWidgets import QMenu
    from SciQLop.components.plotting.ui.time_sync_panel import (
        TimeSyncPanel, plot_static_data,
    )
    from SciQLop.components.plotting.ui.graph_context_menu import (
        add_graph_context_actions,
    )

    panel = TimeSyncPanel('empty', show_search_overlay=False)
    qtbot.addWidget(panel)
    plot_static_data(panel, np.array([0.0, 1.0]), np.array([0.0, 1.0]))
    menu = QMenu()
    add_graph_context_actions(menu, panel)
    titles = [a.text() for a in menu.actions()]
    assert "Copy Python code" not in titles


def test_add_graph_context_actions_clipboard(qtbot):
    """Triggering a per-graph variant action puts the snippet on the clipboard."""
    import numpy as np
    from PySide6.QtWidgets import QApplication, QMenu
    from SciQLop.components.plotting.ui.time_sync_panel import (
        TimeSyncPanel, plot_static_data,
    )
    from SciQLop.components.plotting.ui.graph_context_menu import (
        add_graph_context_actions,
    )
    from SciQLop.core.graph_context import build_speasy_ctx, attach_context
    from SciQLop.components.plotting.backend.data_provider import providers

    class _FakeProvider:
        name = "ClipProv"
        def python_snippets(self, ctx, graph=None):
            return {"Reproduce in SciQLop": "PASTE_ME"}

    providers["ClipProv"] = _FakeProvider()
    panel = TimeSyncPanel('clip', show_search_overlay=False)
    qtbot.addWidget(panel)
    _, graph = plot_static_data(panel, np.array([0.0, 1.0]), np.array([0.0, 1.0]))
    ctx = build_speasy_ctx(graph, panel_name='clip', plot_index=0,
                           speasy_id='x/y', graph_type='Line',
                           product_path=['x', 'y'])
    ctx.provider_name = "ClipProv"
    attach_context(graph, ctx)
    try:
        menu = QMenu(panel)  # parent keeps the submenu graph alive across the test
        add_graph_context_actions(menu, panel)
        sub_actions = list(menu.actions())
        sub = next(a.menu() for a in sub_actions
                   if a.menu() and a.text() == "Copy Python code")
        sub_inner_actions = list(sub.actions())
        graph_sub = next(a.menu() for a in sub_inner_actions
                         if a.menu() and a.menu().actions())
        graph_sub.actions()[0].trigger()
        assert QApplication.clipboard().text() == "PASTE_ME"
    finally:
        providers.pop("ClipProv", None)


def test_show_context_menu_wires_add_graph_context_actions():
    """_show_context_menu calls add_graph_context_actions(menu, self).

    Verified via source inspection — QMenu.exec() enters a native modal loop
    we can't unblock from Python.
    """
    import inspect
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    src = inspect.getsource(TimeSyncPanel._show_context_menu)
    assert "add_graph_context_actions(menu, self)" in src


def test_inspector_tree_tooltip_renders_on_graph_row(qtbot):
    """The tree's tooltip filter consumes the ToolTip event for graph rows
    (which have an attached context) and lets it through for non-graph rows
    (panels, plots, axes) that have no per-graph context.
    """
    import numpy as np
    from PySide6.QtCore import QModelIndex, QEvent
    from PySide6.QtGui import QHelpEvent
    from SciQLop.components.plotting.ui.time_sync_panel import (
        TimeSyncPanel, plot_static_data,
    )
    from SciQLopPlots import PropertiesPanel, PlotsTreeView
    from SciQLop.components.plotting.ui.graph_context_inspector import (
        install_inspector_tree_tooltips,
    )

    panel = TimeSyncPanel('tree_tt', show_search_overlay=False)
    qtbot.addWidget(panel); panel.show()
    plot_static_data(panel, np.array([0.0, 1.0, 2.0]),
                     np.array([0.0, 1.0, 2.0]))
    prop = PropertiesPanel(); qtbot.addWidget(prop); prop.show()
    install_inspector_tree_tooltips(prop)
    tree = prop.findChild(PlotsTreeView)
    tree.expandAll()
    qtbot.waitExposed(tree)

    flt = tree.viewport()._graph_context_tooltip_filter

    def fire(name) -> bool:
        m = tree.model()
        def find(parent=QModelIndex()):
            for r in range(m.rowCount(parent)):
                idx = m.index(r, 0, parent)
                if idx.data() == name:
                    return idx
                sub = find(idx)
                if sub.isValid():
                    return sub
            return QModelIndex()
        idx = find()
        center = tree.visualRect(idx).center()
        ev = QHelpEvent(QEvent.Type.ToolTip, center,
                        tree.viewport().mapToGlobal(center))
        return flt.eventFilter(tree.viewport(), ev)

    assert fire('Line') is True, "graph row consumed by filter"
    assert fire('X Axis') is False, "axis row passes through"


def test_install_graph_context_ui_keeps_extension_alive(qtbot):
    """The GraphContextExtension must survive Python GC after being added.

    Regression: ``parent=graph`` alone is insufficient for Python subclasses of
    Shiboken-bound types — see shiboken-python-subclass-gc-pitfall.md.
    """
    import gc
    import numpy as np
    from SciQLop.components.plotting.ui.time_sync_panel import (
        TimeSyncPanel, plot_static_data,
    )
    from SciQLop.components.plotting.ui.graph_context_inspector import (
        GraphContextExtension,
    )

    panel = TimeSyncPanel('gc_keepalive', show_search_overlay=False)
    qtbot.addWidget(panel)
    _, graph = plot_static_data(panel, np.array([0.0, 1.0, 2.0]),
                                 np.array([0.0, 1.0, 2.0]))
    gc.collect()
    exts = [e for e in graph.inspector_extensions()
            if isinstance(e, GraphContextExtension)]
    assert len(exts) == 1
    assert exts[0].build_widget(None) is not None


def test_extension_survives_graph_wrapper_recreation(qtbot):
    """The GraphContextExtension must keep working after Shiboken recreates
    its Python wrapper — i.e. when the user holds no Python ref to the graph.

    Regression: storing state in Python instance attributes (``self._graph``,
    ``self._title``) silently broke the inspector section. PySide6 doesn't
    keep a parent's *Python wrapper* alive just because C++ holds the QObject;
    the graph wrapper got GC'd, taking ``graph._graph_context_ext`` with it,
    and the fresh wrapper PropertyDelegateBase saw later had an empty
    ``__dict__`` — ``build_widget`` raised ``AttributeError``, the QGroupBox
    rendered empty. Mirrors the live "metadata node not showing" symptom.
    """
    import gc
    import numpy as np
    from SciQLop.components.plotting.ui.time_sync_panel import (
        TimeSyncPanel, plot_static_data,
    )
    from SciQLop.components.plotting.ui.graph_context_inspector import (
        GraphContextExtension,
    )
    from SciQLopPlots import SciQLopGraphInterface, SciQLopPlot

    panel = TimeSyncPanel('wrapper_recreation', show_search_overlay=False)
    qtbot.addWidget(panel)
    plot_static_data(panel, np.array([0.0, 1.0, 2.0]),
                     np.array([0.0, 1.0, 2.0]))
    for _ in range(3):
        gc.collect()

    plot_ptr = panel.plots()[0]
    real_plot = next(c for c in panel.findChildren(SciQLopPlot)
                     if c.objectName() == plot_ptr.objectName())
    graph = real_plot.findChildren(SciQLopGraphInterface)[0]
    assert "_graph_context_ext" not in graph.__dict__, (
        "test must exercise the wrapper-recreation path — got the original "
        "wrapper back, GC didn't run on it"
    )

    exts = [e for e in graph.inspector_extensions()
            if isinstance(e, GraphContextExtension)]
    assert len(exts) == 1
    assert exts[0].section_title() == "Graph"
    widget = exts[0].build_widget(None)
    assert widget is not None
    qtbot.addWidget(widget)


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
        def python_snippets(self, ctx, graph=None):
            return {"Reproduce in SciQLop": "import speasy as spz"}
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


def test_copy_python_snippets_emit_slash_path():
    """End-to-end: SpeasyPlugin's 'Notebook (matplotlib)' + 'Reproduce in
    SciQLop' snippets must emit the slash-joined product path (no list
    literal, no implicit 'root' prefix). Mirrors the live "Copy Python
    code → ..." menu actions.
    """
    from SciQLop.plugins.speasy_provider.speasy_provider import SpeasyPlugin
    from SciQLop.core.graph_context import GraphContext

    p = SpeasyPlugin.__new__(SpeasyPlugin)
    p._name = "Speasy"
    ctx = GraphContext(
        kind="speasy", graph_id="g", panel_name="P", plot_index=0,
        graph_type="Line", speasy_id="amda/ACE/b_gsm",
        provider_name="Speasy",
        product_path=["root", "speasy", "amda", "ACE", "b_gsm"],
    )
    snippets = p.python_snippets(ctx, graph=None)
    notebook = snippets["Notebook (matplotlib)"]
    assert "['root'" not in notebook
    sciqlop_repro = snippets["Reproduce in SciQLop"]
    assert "['root'" not in sciqlop_repro
    assert 'panel.plot_product("speasy//amda//ACE//b_gsm")' in sciqlop_repro
