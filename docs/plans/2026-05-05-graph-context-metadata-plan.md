# Graph Context Metadata — Implementation Plan (P1 + P2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the per-graph context envelope end-to-end with the first user-visible feature: right-click "Copy Python code" on speasy and VP graphs.

**Architecture:** A Pydantic `GraphContext` written to the existing `SciQLopPlots.SciQLopPlottableInterface.meta_data` slot at graph creation, plus a Python-only `_RICH` sidecar `dict[str, GraphRichRefs]` for callback / knobs_model refs. Providers gain two new methods (`python_snippet`, `extended_metadata`) with safe defaults; speasy and `EasyProvider` override them. The context menu helper iterates panel graphs and conditionally adds a per-graph "Copy Python code" action.

**Tech Stack:** Python 3.13, Pydantic 2, PySide6, SciQLopPlots (already exposes `meta_data` / `set_meta_data`), pytest, pytest-qt, pytest-xvfb.

**Spec:** `docs/plans/2026-05-05-graph-context-metadata.md` (committed `d753e9ff`).

**Scope:** This plan implements **P1** (schema + storage + producers) and **P2** (provider methods + right-click snippet). P3 (hover tooltip) and P4 (inspector extension) are deferred to a separate plan.

---

## File Structure

**Created:**
- `SciQLop/core/graph_context.py` — schema, storage helpers, builder helpers (~250 LOC).
- `SciQLop/components/plotting/ui/graph_context_menu.py` — `add_graph_context_actions` helper (~30 LOC).
- `tests/test_graph_context.py` — unit tests for schema / storage / `_is_importable`.
- `tests/test_provider_snippets.py` — unit tests for speasy + EasyProvider overrides.
- `tests/test_graph_context_integration.py` — pytest-qt integration tests (producers + menu).

**Modified:**
- `SciQLop/components/plotting/backend/data_provider.py` — add default `python_snippet` / `extended_metadata` to `DataProvider`.
- `SciQLop/plugins/speasy_provider/speasy_provider.py` — override both methods on `SpeasyPlugin`.
- `SciQLop/components/plotting/backend/easy_provider.py` — override both methods on `EasyProvider` (handles VPs).
- `SciQLop/components/plotting/ui/time_sync_panel.py` — call `attach_context` from `_post_plot` (speasy + VP), `plot_static_data`, `plot_function`; call `add_graph_context_actions` from `_show_context_menu`; wire knob-change refresh.

---

## Task 1: `GraphContext` schema + `GraphRichRefs`

**Files:**
- Create: `SciQLop/core/graph_context.py`
- Test: `tests/test_graph_context.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_graph_context.py
import pytest
from SciQLop.core.graph_context import GraphContext, GraphRichRefs


def test_speasy_context_minimal():
    ctx = GraphContext(
        kind="speasy", graph_id="g1", panel_name="P", plot_index=0,
        graph_type="Line", speasy_id="amda/imf", provider_name="Speasy",
    )
    assert ctx.kind == "speasy"
    assert ctx.knobs == {}
    assert ctx.vp_path is None


def test_vp_context_with_knobs():
    ctx = GraphContext(
        kind="vp", graph_id="g2", panel_name="P", plot_index=1,
        graph_type="Line", vp_path="my/vp", provider_name="vp_callback-1",
        callback_qualname="my_callback", callback_module="my_module",
        knobs={"k": 0.5, "name": "x"},
    )
    assert ctx.knobs == {"k": 0.5, "name": "x"}


def test_extra_field_rejected_at_write():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        GraphContext(
            kind="speasy", graph_id="g", panel_name="P", plot_index=0,
            graph_type="Line", typo_field="oops",
        )


def test_to_meta_data_drops_none_fields():
    ctx = GraphContext(
        kind="speasy", graph_id="g", panel_name="P", plot_index=0,
        graph_type="Line", speasy_id="amda/imf", provider_name="Speasy",
    )
    md = ctx.to_meta_data()
    assert md["kind"] == "speasy"
    assert md["speasy_id"] == "amda/imf"
    assert "vp_path" not in md  # was None, dropped


def test_to_meta_data_round_trip():
    ctx = GraphContext(
        kind="vp", graph_id="g", panel_name="P", plot_index=0,
        graph_type="Line", vp_path="my/vp", provider_name="my_vp-1",
        callback_qualname="cb", callback_module="m",
        knobs={"a": 1},
    )
    assert GraphContext.model_validate(ctx.to_meta_data()) == ctx


def test_graph_rich_refs_defaults_none():
    refs = GraphRichRefs()
    assert refs.callback is None
    assert refs.knobs_model is None
```

- [ ] **Step 2: Run tests to verify failure**

```
uv run pytest tests/test_graph_context.py -v
```
Expected: ImportError — `SciQLop.core.graph_context` does not exist.

- [ ] **Step 3: Create the module with the schema**

```python
# SciQLop/core/graph_context.py
"""Per-graph metadata envelope. See docs/plans/2026-05-05-graph-context-metadata.md."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal, Optional

from pydantic import BaseModel, Field

GraphKind = Literal["speasy", "vp", "static", "function"]


class GraphContext(BaseModel):
    """Per-graph metadata envelope. Single schema, two stores."""

    kind: GraphKind
    graph_id: str
    panel_name: str
    plot_index: int
    graph_type: str

    speasy_id: Optional[str] = None
    vp_path: Optional[str] = None
    callback_qualname: Optional[str] = None
    callback_module: Optional[str] = None

    provider_name: Optional[str] = None
    knobs: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}

    def to_meta_data(self) -> dict:
        return self.model_dump(exclude_none=True)


@dataclass(slots=True)
class GraphRichRefs:
    """Python-only references that can't go in the C++ meta_data slot."""
    callback: Optional[Callable] = None
    knobs_model: Optional[type] = None
```

- [ ] **Step 4: Run tests to verify pass**

```
uv run pytest tests/test_graph_context.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```
git add SciQLop/core/graph_context.py tests/test_graph_context.py
git commit -m "feat(graph-context): GraphContext schema + GraphRichRefs"
```

---

## Task 2: `_is_importable` helper

**Files:**
- Modify: `SciQLop/core/graph_context.py`
- Test: `tests/test_graph_context.py`

- [ ] **Step 1: Write the failing tests**

```python
# Add to tests/test_graph_context.py
from SciQLop.core.graph_context import _is_importable


def _module_level_function():
    return 42


def test_is_importable_module_level_true():
    assert _is_importable(_module_level_function.__module__,
                          _module_level_function.__qualname__,
                          _module_level_function) is True


def test_is_importable_lambda_false():
    f = lambda: 0
    assert _is_importable(f.__module__, f.__qualname__, f) is False


def test_is_importable_closure_false():
    def outer():
        def inner(): return 0
        return inner
    f = outer()
    # qualname contains '<locals>'
    assert "<locals>" in f.__qualname__
    assert _is_importable(f.__module__, f.__qualname__, f) is False


def test_is_importable_aliased_false():
    # Function that resolves to a different object via the qualname path:
    other = lambda: 1
    assert _is_importable(_module_level_function.__module__,
                          _module_level_function.__qualname__,
                          other) is False


def test_is_importable_unknown_module_false():
    assert _is_importable("definitely_not_a_module", "x", lambda: 0) is False
```

- [ ] **Step 2: Run tests to verify failure**

```
uv run pytest tests/test_graph_context.py::test_is_importable_module_level_true -v
```
Expected: ImportError on `_is_importable`.

- [ ] **Step 3: Add the helper**

Append to `SciQLop/core/graph_context.py`:

```python
import importlib


def _is_importable(module_name: str, qualname: str, obj: object) -> bool:
    """Return True iff `qualname` resolves from `module_name` to exactly `obj`.

    Used by VP snippet generation to decide whether the callback can be
    imported by name in a fresh Python session.
    """
    try:
        mod = importlib.import_module(module_name)
        target = mod
        for part in qualname.split("."):
            if part == "<locals>":
                return False
            target = getattr(target, part, None)
            if target is None:
                return False
        return target is obj
    except Exception:
        return False
```

- [ ] **Step 4: Run tests to verify pass**

```
uv run pytest tests/test_graph_context.py -v
```
Expected: 11 passed.

- [ ] **Step 5: Commit**

```
git add SciQLop/core/graph_context.py tests/test_graph_context.py
git commit -m "feat(graph-context): _is_importable helper"
```

---

## Task 3: Storage helpers — `attach_context`, `context_of`, `rich_of`, `provider_for`

**Files:**
- Modify: `SciQLop/core/graph_context.py`
- Test: `tests/test_graph_context.py`

- [ ] **Step 1: Write the failing tests**

```python
# Add to tests/test_graph_context.py
from PySide6.QtCore import QObject, Signal


class _FakeGraph(QObject):
    destroyed_proxy = Signal()  # we use real QObject.destroyed

    def __init__(self, name="fakegraph"):
        super().__init__()
        self._md = {}
        self.setObjectName(name)

    def meta_data(self):
        return dict(self._md)

    def set_meta_data(self, d):
        self._md = dict(d)


def test_attach_context_writes_meta_data(qtbot):
    from SciQLop.core.graph_context import attach_context, context_of
    g = _FakeGraph("g1")
    ctx = GraphContext(
        kind="speasy", graph_id="g1", panel_name="P", plot_index=0,
        graph_type="Line", speasy_id="amda/imf", provider_name="Speasy",
    )
    attach_context(g, ctx)
    assert g.meta_data()["kind"] == "speasy"
    assert g.meta_data()["speasy_id"] == "amda/imf"


def test_context_of_round_trip(qtbot):
    from SciQLop.core.graph_context import attach_context, context_of
    g = _FakeGraph("g2")
    ctx = GraphContext(
        kind="vp", graph_id="g2", panel_name="P", plot_index=0,
        graph_type="Line", vp_path="my/vp", provider_name="my_vp-1",
        callback_qualname="cb", callback_module="m",
    )
    attach_context(g, ctx)
    out = context_of(g)
    assert out is not None
    assert out.kind == "vp"
    assert out.vp_path == "my/vp"


def test_context_of_empty_returns_none(qtbot):
    from SciQLop.core.graph_context import context_of
    g = _FakeGraph("g3")
    assert context_of(g) is None


def test_context_of_garbage_returns_none(qtbot):
    from SciQLop.core.graph_context import context_of
    g = _FakeGraph("g4")
    g.set_meta_data({"kind": "speasy", "graph_id": "x",
                      "panel_name": "P", "plot_index": "not-an-int",  # type error
                      "graph_type": "Line"})
    assert context_of(g) is None


def test_context_of_filters_unknown_fields_for_forward_compat(qtbot):
    from SciQLop.core.graph_context import context_of
    g = _FakeGraph("g5")
    g.set_meta_data({
        "kind": "speasy", "graph_id": "g5", "panel_name": "P",
        "plot_index": 0, "graph_type": "Line", "speasy_id": "x/y",
        "future_field_we_dont_know": "value",
    })
    out = context_of(g)
    assert out is not None
    assert out.speasy_id == "x/y"


def test_rich_of_returns_refs(qtbot):
    from SciQLop.core.graph_context import attach_context, rich_of
    g = _FakeGraph("g6")
    ctx = GraphContext(
        kind="vp", graph_id="g6", panel_name="P", plot_index=0,
        graph_type="Line", vp_path="x", provider_name="vp-1",
    )
    cb = lambda s, e: None
    refs = GraphRichRefs(callback=cb)
    attach_context(g, ctx, refs)
    out = rich_of("g6")
    assert out is refs


def test_destroy_evicts_rich_refs(qtbot):
    from SciQLop.core.graph_context import attach_context, rich_of
    g = _FakeGraph("g7")
    ctx = GraphContext(
        kind="vp", graph_id="g7", panel_name="P", plot_index=0,
        graph_type="Line", vp_path="x", provider_name="vp-1",
    )
    attach_context(g, ctx, GraphRichRefs(callback=lambda s, e: None))
    assert rich_of("g7") is not None
    g.deleteLater()
    qtbot.wait(50)  # let destroyed signal fire
    assert rich_of("g7") is None
```

- [ ] **Step 2: Run tests to verify failure**

```
uv run pytest tests/test_graph_context.py -v
```
Expected: ImportError on `attach_context`.

- [ ] **Step 3: Add the storage helpers**

Append to `SciQLop/core/graph_context.py`:

```python
from SciQLop.components import sciqlop_logging

log = sciqlop_logging.getLogger(__name__)

_RICH: dict[str, GraphRichRefs] = {}


def attach_context(graph, ctx: GraphContext,
                   rich: Optional[GraphRichRefs] = None) -> None:
    """Write the lean envelope to the C++ meta_data slot and stash rich refs.

    Connects to graph.destroyed to auto-evict the rich entry when the graph
    is gone.
    """
    try:
        graph.set_meta_data(ctx.to_meta_data())
    except Exception:
        log.debug("set_meta_data failed for %s", ctx.graph_id, exc_info=True)
    if rich is not None:
        _RICH[ctx.graph_id] = rich
        graph.destroyed.connect(
            lambda _=None, gid=ctx.graph_id: _RICH.pop(gid, None)
        )


def context_of(graph) -> Optional[GraphContext]:
    """Reconstruct GraphContext from graph.meta_data, filtering unknown fields
    so a newer SciQLop's extra fields don't blow up older readers.
    """
    raw = graph.meta_data() or {}
    if not raw or "kind" not in raw:
        return None
    known = {k: v for k, v in raw.items() if k in GraphContext.model_fields}
    try:
        return GraphContext.model_validate(known)
    except Exception:
        log.debug("context_of: validation failed for %s", known, exc_info=True)
        return None


def rich_of(graph_id: str) -> Optional[GraphRichRefs]:
    return _RICH.get(graph_id)


def provider_for(ctx: GraphContext):
    """Return the DataProvider instance for ctx, or None."""
    if not ctx.provider_name:
        return None
    from SciQLop.components.plotting.backend.data_provider import providers
    return providers.get(ctx.provider_name)
```

- [ ] **Step 4: Run tests to verify pass**

```
uv run pytest tests/test_graph_context.py -v
```
Expected: 18 passed.

- [ ] **Step 5: Commit**

```
git add SciQLop/core/graph_context.py tests/test_graph_context.py
git commit -m "feat(graph-context): attach_context / context_of / rich_of / provider_for"
```

---

## Task 4: Builder helpers — `_build_speasy_ctx`, `_build_vp_ctx`, `_build_function_ctx`, `_build_static_ctx`

**Files:**
- Modify: `SciQLop/core/graph_context.py`
- Test: `tests/test_graph_context.py`

- [ ] **Step 1: Write the failing tests**

```python
# Add to tests/test_graph_context.py
def test_build_speasy_ctx():
    from SciQLop.core.graph_context import _build_speasy_ctx
    g = _FakeGraph("g_speasy")
    ctx = _build_speasy_ctx(g, panel_name="P", plot_index=2,
                             speasy_id="amda/imf", graph_type="Line",
                             knobs={"k": 1})
    assert ctx.kind == "speasy"
    assert ctx.graph_id == "g_speasy"
    assert ctx.panel_name == "P"
    assert ctx.plot_index == 2
    assert ctx.speasy_id == "amda/imf"
    assert ctx.provider_name == "Speasy"
    assert ctx.knobs == {"k": 1}


def test_build_vp_ctx():
    from SciQLop.core.graph_context import _build_vp_ctx
    g = _FakeGraph("g_vp")

    def my_cb(start, stop): return None

    ctx = _build_vp_ctx(g, panel_name="P", plot_index=0,
                         vp_path=["root", "x"], provider_name="my_vp-1",
                         callback=my_cb, graph_type="Line", knobs={})
    assert ctx.kind == "vp"
    assert ctx.vp_path == "root/x"
    assert ctx.callback_qualname == my_cb.__qualname__
    assert ctx.callback_module == my_cb.__module__
    assert ctx.provider_name == "my_vp-1"


def test_build_function_ctx():
    from SciQLop.core.graph_context import _build_function_ctx
    g = _FakeGraph("g_fn")

    def fn(start, stop): return None

    ctx = _build_function_ctx(g, panel_name="P", plot_index=1,
                                callback=fn, graph_type="Line")
    assert ctx.kind == "function"
    assert ctx.provider_name is None
    assert ctx.callback_qualname == fn.__qualname__


def test_build_static_ctx():
    from SciQLop.core.graph_context import _build_static_ctx
    g = _FakeGraph("g_static")
    ctx = _build_static_ctx(g, panel_name="P", plot_index=0,
                             graph_type="Line")
    assert ctx.kind == "static"
    assert ctx.provider_name is None
    assert ctx.speasy_id is None
```

- [ ] **Step 2: Run tests to verify failure**

```
uv run pytest tests/test_graph_context.py -v
```
Expected: ImportError on the four builders.

- [ ] **Step 3: Add the builders**

Append to `SciQLop/core/graph_context.py`:

```python
def _build_speasy_ctx(graph, *, panel_name: str, plot_index: int,
                       speasy_id: str, graph_type: str,
                       knobs: Optional[dict] = None) -> GraphContext:
    return GraphContext(
        kind="speasy",
        graph_id=graph.objectName(),
        panel_name=panel_name,
        plot_index=plot_index,
        graph_type=graph_type,
        speasy_id=speasy_id,
        provider_name="Speasy",
        knobs=knobs or {},
    )


def _build_vp_ctx(graph, *, panel_name: str, plot_index: int,
                   vp_path, provider_name: str, callback: Callable,
                   graph_type: str,
                   knobs: Optional[dict] = None) -> GraphContext:
    if isinstance(vp_path, (list, tuple)):
        vp_path_str = "/".join(vp_path)
    else:
        vp_path_str = str(vp_path)
    return GraphContext(
        kind="vp",
        graph_id=graph.objectName(),
        panel_name=panel_name,
        plot_index=plot_index,
        graph_type=graph_type,
        vp_path=vp_path_str,
        provider_name=provider_name,
        callback_qualname=getattr(callback, "__qualname__", None),
        callback_module=getattr(callback, "__module__", None),
        knobs=knobs or {},
    )


def _build_function_ctx(graph, *, panel_name: str, plot_index: int,
                         callback: Callable, graph_type: str) -> GraphContext:
    return GraphContext(
        kind="function",
        graph_id=graph.objectName(),
        panel_name=panel_name,
        plot_index=plot_index,
        graph_type=graph_type,
        provider_name=None,
        callback_qualname=getattr(callback, "__qualname__", None),
        callback_module=getattr(callback, "__module__", None),
    )


def _build_static_ctx(graph, *, panel_name: str, plot_index: int,
                       graph_type: str) -> GraphContext:
    return GraphContext(
        kind="static",
        graph_id=graph.objectName(),
        panel_name=panel_name,
        plot_index=plot_index,
        graph_type=graph_type,
        provider_name=None,
    )
```

- [ ] **Step 4: Run tests to verify pass**

```
uv run pytest tests/test_graph_context.py -v
```
Expected: 22 passed.

- [ ] **Step 5: Commit**

```
git add SciQLop/core/graph_context.py tests/test_graph_context.py
git commit -m "feat(graph-context): builder helpers (speasy / vp / function / static)"
```

---

## Task 5: Wire `_post_plot` to attach context for speasy/VP graphs

**Files:**
- Modify: `SciQLop/components/plotting/ui/time_sync_panel.py:404-410`
- Test: `tests/test_graph_context_integration.py`

- [ ] **Step 1: Write the failing integration test**

```python
# tests/test_graph_context_integration.py
"""End-to-end tests for graph context attachment via the producer paths.

Heavier than test_graph_context.py — these go through the real
SciQLopMultiPlotPanel + plot_product / plot_static_data / plot_function paths.
"""
import pytest

from tests.fixtures import sciqlop_main_window  # existing fixture


def _resolve_graph(plot_or_pair):
    """plot_product returns either (plot, graph) or graph alone depending on type."""
    if hasattr(plot_or_pair, "__iter__"):
        return plot_or_pair[1]
    return plot_or_pair


def test_plot_product_attaches_speasy_context(sciqlop_main_window, qtbot):
    """plot_product on a speasy product attaches a kind='speasy' context."""
    from SciQLop.user_api.plot import create_plot_panel
    from SciQLop.core.graph_context import context_of

    panel = create_plot_panel()
    qtbot.wait(50)
    # Use a known-static product to avoid network — use a virtual product
    # registered for testing instead. (See test_vp_attaches_context below for
    # the speasy path; this test stub is a placeholder until we have a
    # mockable speasy fixture.)
    pytest.skip("speasy attachment covered by VP test until mockable fixture exists")
```

Note: full speasy integration testing requires mocking `spz.get_data` — handled in Task 9. Use the VP path as the integration smoke for now (Task 6 covers `plot_function`).

A focused unit-style integration test that exercises `_post_plot` directly:

```python
# Continue tests/test_graph_context_integration.py
def test_post_plot_attaches_context_for_speasy_provider(qtbot):
    """_post_plot writes a kind='speasy' context for a SpeasyPlugin provider."""
    from SciQLop.components.plotting.ui.time_sync_panel import _post_plot
    from SciQLop.core.graph_context import context_of
    from PySide6.QtCore import QObject

    class _FakeNode:
        def name(self): return "imf"
        def metadata(self, key=None):
            return {"speasy_id": "amda/imf"} if key is None else "amda/imf"

    class _FakeProvider:
        name = "Speasy"
        def labels(self, node): return ["Bx", "By", "Bz"]

    class _FakeGraph(QObject):
        def __init__(self, name): super().__init__(); self.setObjectName(name)
        _md = {}
        def meta_data(self): return dict(self._md)
        def set_meta_data(self, d): self._md = dict(d)
        def set_name(self, n): self.setObjectName(n)
        def name(self): return self.objectName()

    class _FakePlot(QObject):
        def __init__(self): super().__init__(); self.setObjectName("plot0")
        def objectName(self): return super().objectName() or "plot0"

    class _FakeTarget:
        def plots(self): return [_FakePlot()]
        def windowTitle(self): return "PanelX"

    plot, graph = _FakePlot(), _FakeGraph("g_post_plot")
    target = _FakeTarget()
    _post_plot((plot, graph), _FakeProvider(), _FakeNode(),
               callback=type("C", (), {"_post_fetch": None})(),  # callback stub
               target=target, product_path_str="amda//imf",
               existing_plot=None)

    ctx = context_of(graph)
    assert ctx is not None
    assert ctx.kind == "speasy"
    assert ctx.speasy_id == "amda/imf"
    assert ctx.provider_name == "Speasy"
```

This test will fail because `_post_plot` doesn't call `attach_context` yet. (The fake objects substitute for the real plumbing — `_register_graph_hints` and `_attach_knob_state` will need stubbing or the code will fail before reaching `attach_context`. See Step 3 — we add a try/except guard around the existing calls so they no-op on stubs.)

Adjustment: keep the test simpler by calling `attach_context` directly from a harness that mimics what `_post_plot` should do, rather than calling `_post_plot`. **Rewrite the test:**

```python
# tests/test_graph_context_integration.py — replace the test above with this:
def test_post_plot_invokes_attach_context_for_speasy(qtbot, monkeypatch):
    """When _post_plot runs on a speasy provider, attach_context is called
    with kind='speasy'."""
    from SciQLop.components.plotting.ui import time_sync_panel as tsp
    from SciQLop.core import graph_context as gc
    from PySide6.QtCore import QObject

    captured = {}
    def _capture_attach(graph, ctx, rich=None):
        captured["graph"] = graph
        captured["ctx"] = ctx
        captured["rich"] = rich
    monkeypatch.setattr(gc, "attach_context", _capture_attach)
    monkeypatch.setattr(tsp, "attach_context", _capture_attach)
    monkeypatch.setattr(tsp, "_set_product_path", lambda *a, **kw: None)
    monkeypatch.setattr(tsp, "_register_graph_hints", lambda *a, **kw: None)
    monkeypatch.setattr(tsp, "_attach_knob_state", lambda *a, **kw: None)

    class _FakeNode:
        def name(self): return "imf"
        def metadata(self, key=None):
            if key == "speasy_id": return "amda/imf"
            return {}

    class _FakeProvider:
        name = "Speasy"

    class _FakeGraph(QObject):
        def __init__(self, name): super().__init__(); self.setObjectName(name)
        def set_name(self, n): self.setObjectName(n)
        def name(self): return self.objectName()

    class _FakePlot(QObject):
        def __init__(self): super().__init__(); self.setObjectName("plot0")

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
```

- [ ] **Step 2: Run test to verify failure**

```
uv run pytest tests/test_graph_context_integration.py -v
```
Expected: AssertionError — `attach_context` not called (captured dict empty), or AttributeError on `tsp.attach_context` (not yet imported).

- [ ] **Step 3: Wire `_post_plot` to call `attach_context`**

Edit `SciQLop/components/plotting/ui/time_sync_panel.py`:

Add at the top of the file (with other imports):

```python
from SciQLop.core.graph_context import (
    attach_context, _build_speasy_ctx, _build_vp_ctx,
    _build_static_ctx, _build_function_ctx,
    GraphRichRefs,
)
from SciQLop.components.plotting.backend.easy_provider import EasyProvider
```

Replace `_post_plot` (currently lines 404-410) with:

```python
def _post_plot(r, provider, node, callback, target, product_path_str, existing_plot):
    if not hasattr(r, '__iter__') and existing_plot is not None:
        r = (existing_plot, r)
    _set_product_path(r, product_path_str)
    callback._post_fetch = _register_graph_hints(provider, node, r, target)
    _attach_knob_state(provider, node, callback, r, target)
    _attach_graph_context(r, provider, node, target)
    return r


def _attach_graph_context(r, provider, node, target):
    """Attach a GraphContext + rich refs to the graph just produced.

    Only acts on recognized provider types (SpeasyPlugin, EasyProvider).
    Unknown DataProvider subclasses are skipped — better to attach no
    context than mislabel one.
    """
    try:
        plot, graph = r
        panel_name = target.windowTitle() if hasattr(target, "windowTitle") else ""
        plots = target.plots() if hasattr(target, "plots") else []
        plot_index = next((i for i, p in enumerate(plots)
                           if p.objectName() == plot.objectName()), -1)
        graph_type = type(graph).__name__
        # Knob value capture is intentionally minimal in v1 — empty dict.
        # The inspector wiring (P4) will keep ctx.knobs in sync via
        # update_knobs() when a user changes a knob.
        knobs = {}
        if isinstance(provider, EasyProvider):
            ctx = _build_vp_ctx(
                graph, panel_name=panel_name, plot_index=plot_index,
                vp_path=provider._path, provider_name=provider.name,
                callback=provider._callback, graph_type=graph_type,
                knobs=knobs,
            )
            rich = GraphRichRefs(callback=provider._callback,
                                 knobs_model=provider._knobs_model)
            attach_context(graph, ctx, rich)
            return
        if getattr(provider, "name", None) == "Speasy":
            speasy_id = ""
            if hasattr(node, "metadata"):
                speasy_id = node.metadata("speasy_id") or ""
            ctx = _build_speasy_ctx(
                graph, panel_name=panel_name, plot_index=plot_index,
                speasy_id=speasy_id, graph_type=graph_type,
                knobs=knobs,
            )
            attach_context(graph, ctx)
            return
        log.debug("graph_context: unknown provider %r — skipping attach",
                  type(provider).__name__)
    except Exception:
        log.debug("attach_graph_context failed", exc_info=True)
```

- [ ] **Step 4: Run test to verify pass**

```
uv run pytest tests/test_graph_context_integration.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Commit**

```
git add SciQLop/components/plotting/ui/time_sync_panel.py tests/test_graph_context_integration.py
git commit -m "feat(graph-context): attach context from _post_plot for speasy/VP"
```

---

## Task 6: Wire `plot_static_data` and `plot_function` to attach context

**Files:**
- Modify: `SciQLop/components/plotting/ui/time_sync_panel.py:446-462`
- Test: `tests/test_graph_context_integration.py`

- [ ] **Step 1: Write the failing tests**

```python
# Add to tests/test_graph_context_integration.py
def test_plot_static_data_attaches_static_context(qtbot, monkeypatch):
    from SciQLop.components.plotting.ui import time_sync_panel as tsp
    from PySide6.QtCore import QObject

    captured = []
    monkeypatch.setattr(tsp, "attach_context",
                        lambda g, ctx, rich=None: captured.append(ctx))

    class _FakeGraph(QObject):
        def __init__(self): super().__init__(); self.setObjectName("sg")

    class _FakePlot(QObject):
        def __init__(self): super().__init__(); self.setObjectName("plot0")

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
        def __init__(self): super().__init__(); self.setObjectName("fg")

    class _FakePlot(QObject):
        def __init__(self): super().__init__(); self.setObjectName("plot0")

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
    assert ctx.callback_qualname == "test_plot_function_attaches_function_context.<locals>.my_func"
    assert rich is not None
    assert rich.callback is my_func
```

- [ ] **Step 2: Run tests to verify failure**

```
uv run pytest tests/test_graph_context_integration.py::test_plot_static_data_attaches_static_context tests/test_graph_context_integration.py::test_plot_function_attaches_function_context -v
```
Expected: AssertionError — captured list empty.

- [ ] **Step 3: Wire `plot_static_data` and `plot_function`**

Replace `plot_static_data` (lines 446-454):

```python
def plot_static_data(p: Union[SciQLopPlot, SciQLopMultiPlotPanel, SciQLopNDProjectionPlot], x, y, z=None, **kwargs):
    target, existing_plot = _resolve_plot_target(p, kwargs)
    if z is not None:
        r = target.plot(x, y, z, **kwargs)
    else:
        r = target.plot(x, y, **kwargs)
    if not hasattr(r, '__iter__') and existing_plot is not None:
        r = (existing_plot, r)
    try:
        plot, graph = r
        panel_name = target.windowTitle() if hasattr(target, "windowTitle") else ""
        plots = target.plots() if hasattr(target, "plots") else []
        plot_index = next((i for i, _p in enumerate(plots)
                           if _p.objectName() == plot.objectName()), -1)
        ctx = _build_static_ctx(graph, panel_name=panel_name,
                                plot_index=plot_index,
                                graph_type=type(graph).__name__)
        attach_context(graph, ctx)
    except Exception:
        log.debug("attach_context for static data failed", exc_info=True)
    return r
```

Replace `plot_function` (lines 457-462):

```python
def plot_function(p: Union[SciQLopPlot, SciQLopMultiPlotPanel, SciQLopNDProjectionPlot], f, **kwargs):
    target, existing_plot = _resolve_plot_target(p, kwargs)
    r = target.plot(f, **kwargs)
    if not hasattr(r, '__iter__') and existing_plot is not None:
        r = (existing_plot, r)
    try:
        plot, graph = r
        panel_name = target.windowTitle() if hasattr(target, "windowTitle") else ""
        plots = target.plots() if hasattr(target, "plots") else []
        plot_index = next((i for i, _p in enumerate(plots)
                           if _p.objectName() == plot.objectName()), -1)
        ctx = _build_function_ctx(graph, panel_name=panel_name,
                                   plot_index=plot_index,
                                   callback=f,
                                   graph_type=type(graph).__name__)
        attach_context(graph, ctx, GraphRichRefs(callback=f))
    except Exception:
        log.debug("attach_context for function plot failed", exc_info=True)
    return r
```

- [ ] **Step 4: Run tests to verify pass**

```
uv run pytest tests/test_graph_context_integration.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```
git add SciQLop/components/plotting/ui/time_sync_panel.py tests/test_graph_context_integration.py
git commit -m "feat(graph-context): attach context from plot_static_data and plot_function"
```

---

## Task 7: Knob-update slot to refresh `meta_data`

**Files:**
- Modify: `SciQLop/core/graph_context.py` (extend `attach_context`)
- Test: `tests/test_graph_context.py`

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_graph_context.py
def test_update_knobs_refreshes_meta_data(qtbot):
    from SciQLop.core.graph_context import (
        attach_context, context_of, update_knobs, GraphContext, GraphRichRefs,
    )
    g = _FakeGraph("g_knob")
    ctx = GraphContext(
        kind="vp", graph_id="g_knob", panel_name="P", plot_index=0,
        graph_type="Line", vp_path="x", provider_name="vp-1",
        knobs={"a": 1},
    )
    attach_context(g, ctx, GraphRichRefs(callback=lambda s, e: None))

    update_knobs(g, {"a": 99, "b": "x"})

    refreshed = context_of(g)
    assert refreshed.knobs == {"a": 99, "b": "x"}


def test_update_knobs_no_op_when_no_context(qtbot):
    from SciQLop.core.graph_context import update_knobs
    g = _FakeGraph("g_no_ctx")
    # No attach_context — calling update_knobs should not raise
    update_knobs(g, {"a": 1})
    assert g.meta_data() == {}
```

- [ ] **Step 2: Run tests to verify failure**

```
uv run pytest tests/test_graph_context.py::test_update_knobs_refreshes_meta_data -v
```
Expected: ImportError on `update_knobs`.

- [ ] **Step 3: Add `update_knobs`**

Append to `SciQLop/core/graph_context.py`:

```python
def update_knobs(graph, knobs: dict) -> None:
    """Refresh the knobs dict on a graph's meta_data slot.

    Called when the user changes knob values in the inspector. No-op if no
    context was attached to this graph.
    """
    ctx = context_of(graph)
    if ctx is None:
        return
    ctx.knobs = dict(knobs)
    try:
        graph.set_meta_data(ctx.to_meta_data())
    except Exception:
        log.debug("update_knobs set_meta_data failed", exc_info=True)
```

- [ ] **Step 4: Run tests to verify pass**

```
uv run pytest tests/test_graph_context.py -v
```
Expected: 24 passed.

- [ ] **Step 5: Commit**

```
git add SciQLop/core/graph_context.py tests/test_graph_context.py
git commit -m "feat(graph-context): update_knobs slot to refresh meta_data"
```

**Note:** Wiring `update_knobs` into the actual knob-change signal is deferred — the existing `_attach_knob_state` flow in `time_sync_panel.py` is where it lives, and a minimal hook there is mechanical (one extra signal connection inside `_attach_knob_state`). Add it when needed for the inspector phase; for snippet copy purposes, the *current creation-time* knob values already make the snippet useful.

---

## Task 8: `DataProvider.python_snippet` + `extended_metadata` defaults

**Files:**
- Modify: `SciQLop/components/plotting/backend/data_provider.py`
- Test: `tests/test_provider_snippets.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_provider_snippets.py
from SciQLop.components.plotting.backend.data_provider import DataProvider, DataOrder
from SciQLop.core.graph_context import GraphContext


def test_data_provider_default_snippet_returns_none():
    p = DataProvider("test", DataOrder.X_FIRST)
    ctx = GraphContext(kind="speasy", graph_id="g", panel_name="P",
                       plot_index=0, graph_type="Line",
                       speasy_id="x/y", provider_name="test")
    assert p.python_snippet(ctx) is None


def test_data_provider_default_extended_metadata_empty():
    p = DataProvider("test", DataOrder.X_FIRST)
    ctx = GraphContext(kind="speasy", graph_id="g", panel_name="P",
                       plot_index=0, graph_type="Line",
                       speasy_id="x/y", provider_name="test")
    assert p.extended_metadata(ctx) == {}
```

- [ ] **Step 2: Run tests to verify failure**

```
uv run pytest tests/test_provider_snippets.py -v
```
Expected: AttributeError on `python_snippet` / `extended_metadata`.

- [ ] **Step 3: Add the default methods to `DataProvider`**

Append to the `DataProvider` class in `SciQLop/components/plotting/backend/data_provider.py`:

```python
    def python_snippet(self, ctx) -> Optional[str]:
        """Return a Python snippet that reproduces this graph's fetch, or None."""
        return None

    def extended_metadata(self, ctx) -> dict:
        """Return rich metadata about the graph's source. Format is per-provider."""
        return {}
```

(Add `from typing import Optional` if not already imported.)

- [ ] **Step 4: Run tests to verify pass**

```
uv run pytest tests/test_provider_snippets.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```
git add SciQLop/components/plotting/backend/data_provider.py tests/test_provider_snippets.py
git commit -m "feat(graph-context): DataProvider defaults for python_snippet and extended_metadata"
```

---

## Task 9: SpeasyPlugin overrides

**Files:**
- Modify: `SciQLop/plugins/speasy_provider/speasy_provider.py`
- Test: `tests/test_provider_snippets.py`

- [ ] **Step 1: Write the failing tests**

```python
# Add to tests/test_provider_snippets.py
from unittest.mock import MagicMock, patch


def test_speasy_python_snippet_basic():
    from SciQLop.plugins.speasy_provider.speasy_provider import SpeasyPlugin
    p = SpeasyPlugin.__new__(SpeasyPlugin)  # bypass __init__ (heavy)
    p._name = "Speasy"
    ctx = GraphContext(kind="speasy", graph_id="g", panel_name="P",
                       plot_index=0, graph_type="Line",
                       speasy_id="amda/imf", provider_name="Speasy")
    snippet = p.python_snippet(ctx)
    assert snippet is not None
    assert "import speasy as spz" in snippet
    assert "amda/imf" in snippet
    assert "spz.get_data" in snippet
    assert "product_inputs" not in snippet  # no knobs


def test_speasy_python_snippet_with_knobs():
    from SciQLop.plugins.speasy_provider.speasy_provider import SpeasyPlugin
    p = SpeasyPlugin.__new__(SpeasyPlugin)
    p._name = "Speasy"
    ctx = GraphContext(kind="speasy", graph_id="g", panel_name="P",
                       plot_index=0, graph_type="Line",
                       speasy_id="cda/mms", provider_name="Speasy",
                       knobs={"resolution": "high"})
    snippet = p.python_snippet(ctx)
    assert "product_inputs={'resolution': 'high'}" in snippet


def test_speasy_python_snippet_returns_none_for_non_speasy_kind():
    from SciQLop.plugins.speasy_provider.speasy_provider import SpeasyPlugin
    p = SpeasyPlugin.__new__(SpeasyPlugin)
    p._name = "Speasy"
    ctx = GraphContext(kind="vp", graph_id="g", panel_name="P",
                       plot_index=0, graph_type="Line",
                       vp_path="x", provider_name="vp-1")
    assert p.python_snippet(ctx) is None


def test_speasy_extended_metadata_unknown_id():
    from SciQLop.plugins.speasy_provider.speasy_provider import SpeasyPlugin
    p = SpeasyPlugin.__new__(SpeasyPlugin)
    p._name = "Speasy"
    ctx = GraphContext(kind="speasy", graph_id="g", panel_name="P",
                       plot_index=0, graph_type="Line",
                       speasy_id="bogus/id", provider_name="Speasy")
    with patch.object(p, "_resolve_index", return_value=None):
        assert p.extended_metadata(ctx) == {}


def test_speasy_extended_metadata_known_id():
    from SciQLop.plugins.speasy_provider.speasy_provider import SpeasyPlugin
    p = SpeasyPlugin.__new__(SpeasyPlugin)
    p._name = "Speasy"
    ctx = GraphContext(kind="speasy", graph_id="g", panel_name="P",
                       plot_index=0, graph_type="Line",
                       speasy_id="amda/imf", provider_name="Speasy")
    fake_index = MagicMock()
    fake_index.parameter_type = "Vector"
    with patch.object(p, "_resolve_index", return_value=fake_index):
        out = p.extended_metadata(ctx)
    assert out["speasy_id"] == "amda/imf"
    assert out["parameter_type"] == "Vector"
    assert "inventory" in out
```

- [ ] **Step 2: Run tests to verify failure**

```
uv run pytest tests/test_provider_snippets.py -v
```
Expected: AttributeError — `SpeasyPlugin` inherits the no-op defaults.

- [ ] **Step 3: Add the SpeasyPlugin overrides**

Append to the `SpeasyPlugin` class in `SciQLop/plugins/speasy_provider/speasy_provider.py`:

```python
    def python_snippet(self, ctx) -> Optional[str]:
        if ctx.kind != "speasy" or not ctx.speasy_id:
            return None
        knobs_arg = (
            f", product_inputs={ctx.knobs!r}" if ctx.knobs else ""
        )
        return (
            "import speasy as spz\n"
            'start = "2020-01-01T00:00:00"  # adjust\n'
            'stop  = "2020-01-02T00:00:00"  # adjust\n'
            f'data = spz.get_data("{ctx.speasy_id}", start, stop{knobs_arg})\n'
        )

    def extended_metadata(self, ctx) -> dict:
        if ctx.kind != "speasy" or not ctx.speasy_id:
            return {}
        index = self._resolve_index(ctx.speasy_id)
        if index is None:
            return {}
        return {
            "speasy_id": ctx.speasy_id,
            "inventory": _index_to_dict(index),
            "parameter_type": (str(getattr(index, "parameter_type", ""))
                                or None),
        }
```

Add at module level (above the `SpeasyPlugin` class):

```python
from typing import Optional


def _index_to_dict(index) -> dict:
    """Best-effort flatten of a speasy ParameterIndex into a dict.

    Walks public attributes; skips callables and underscore-prefixed names.
    Falls back to {'__repr__': repr(index)} if attribute access raises.
    """
    out = {}
    try:
        for attr in dir(index):
            if attr.startswith("_"):
                continue
            try:
                value = getattr(index, attr)
            except Exception:
                continue
            if callable(value):
                continue
            try:
                # Only keep JSON-friendly values
                if isinstance(value, (str, int, float, bool, list, dict, type(None))):
                    out[attr] = value
            except Exception:
                continue
    except Exception:
        out["__repr__"] = repr(index)
    return out
```

- [ ] **Step 4: Run tests to verify pass**

```
uv run pytest tests/test_provider_snippets.py -v
```
Expected: 7 passed.

- [ ] **Step 5: Commit**

```
git add SciQLop/plugins/speasy_provider/speasy_provider.py tests/test_provider_snippets.py
git commit -m "feat(graph-context): SpeasyPlugin python_snippet + extended_metadata"
```

---

## Task 10: EasyProvider overrides (three-tier snippet)

**Files:**
- Modify: `SciQLop/components/plotting/backend/easy_provider.py`
- Test: `tests/test_provider_snippets.py`

- [ ] **Step 1: Write the failing tests**

```python
# Add to tests/test_provider_snippets.py — module-level callbacks for the
# importable case
def _tested_module_level_vp_callback(start, stop, knobs=None):
    return None


def test_easy_provider_snippet_module_level_callback():
    from SciQLop.components.plotting.backend.easy_provider import EasyProvider
    p = EasyProvider.__new__(EasyProvider)
    p._path = ["root", "my_vp"]
    p._callback = _tested_module_level_vp_callback
    p._knobs_kwarg_name = "knobs"
    ctx = GraphContext(kind="vp", graph_id="g", panel_name="P",
                       plot_index=0, graph_type="Line",
                       vp_path="root/my_vp", provider_name="my_vp-1",
                       callback_qualname=_tested_module_level_vp_callback.__qualname__,
                       callback_module=_tested_module_level_vp_callback.__module__,
                       knobs={"k": 0.5})
    snippet = p.python_snippet(ctx)
    assert snippet is not None
    assert f"from {_tested_module_level_vp_callback.__module__} import" in snippet
    assert _tested_module_level_vp_callback.__qualname__ in snippet
    assert "knobs={'k': 0.5}" in snippet


def test_easy_provider_snippet_lambda_returns_stub():
    from SciQLop.components.plotting.backend.easy_provider import EasyProvider
    p = EasyProvider.__new__(EasyProvider)
    p._path = ["root", "my_vp"]
    p._callback = lambda s, e: None
    p._knobs_kwarg_name = "knobs"
    ctx = GraphContext(kind="vp", graph_id="g", panel_name="P",
                       plot_index=0, graph_type="Line",
                       vp_path="root/my_vp", provider_name="my_vp-1",
                       callback_qualname=p._callback.__qualname__,
                       callback_module=p._callback.__module__)
    snippet = p.python_snippet(ctx)
    assert snippet is not None
    assert "not importable" in snippet
    assert "root/my_vp" in snippet


def test_easy_provider_snippet_kind_mismatch_returns_none():
    from SciQLop.components.plotting.backend.easy_provider import EasyProvider
    p = EasyProvider.__new__(EasyProvider)
    p._callback = _tested_module_level_vp_callback
    p._path = ["x"]
    ctx = GraphContext(kind="speasy", graph_id="g", panel_name="P",
                       plot_index=0, graph_type="Line",
                       speasy_id="x/y", provider_name="Speasy")
    assert p.python_snippet(ctx) is None


def test_easy_provider_extended_metadata_with_model():
    from SciQLop.components.plotting.backend.easy_provider import EasyProvider
    from pydantic import BaseModel

    class Knobs(BaseModel):
        k: float = 0.0

    p = EasyProvider.__new__(EasyProvider)
    p._path = ["root", "x"]
    p._callback = _tested_module_level_vp_callback
    p._knobs_model = Knobs
    p._knob_specs = []

    ctx = GraphContext(kind="vp", graph_id="g", panel_name="P",
                       plot_index=0, graph_type="Line",
                       vp_path="root/x", provider_name="x-1")
    out = p.extended_metadata(ctx)
    assert out["vp_path"] == "root/x"
    assert out["callback"]["qualname"] == _tested_module_level_vp_callback.__qualname__
    assert "k" in out["knobs_schema"]["properties"]
    assert out["knob_specs"] == []


def test_easy_provider_extended_metadata_without_model():
    from SciQLop.components.plotting.backend.easy_provider import EasyProvider
    p = EasyProvider.__new__(EasyProvider)
    p._path = ["root", "y"]
    p._callback = _tested_module_level_vp_callback
    p._knobs_model = None
    p._knob_specs = []

    ctx = GraphContext(kind="vp", graph_id="g", panel_name="P",
                       plot_index=0, graph_type="Line",
                       vp_path="root/y", provider_name="y-1")
    out = p.extended_metadata(ctx)
    assert out["knobs_schema"] is None
```

- [ ] **Step 2: Run tests to verify failure**

```
uv run pytest tests/test_provider_snippets.py -v
```
Expected: AttributeError or wrong return values — `EasyProvider` inherits no-op defaults.

- [ ] **Step 3: Add EasyProvider overrides**

Add to the `EasyProvider` class in `SciQLop/components/plotting/backend/easy_provider.py`:

```python
    def python_snippet(self, ctx) -> Optional[str]:
        if ctx.kind != "vp" or self._callback is None:
            return None
        cb = self._callback
        mod_name = getattr(cb, "__module__", None)
        qualname = getattr(cb, "__qualname__", None)
        if not (mod_name and qualname):
            return None
        from SciQLop.core.graph_context import _is_importable
        if _is_importable(mod_name, qualname, cb):
            knobs_kw = (
                f", {self._knobs_kwarg_name}={ctx.knobs!r}"
                if ctx.knobs else ""
            )
            return (
                f"from {mod_name} import {qualname}\n"
                "start = ...  # datetime or float\n"
                "stop  = ...\n"
                f"data = {qualname}(start, stop{knobs_kw})\n"
            )
        return (
            f"# Virtual product '{'/'.join(self._path)}'\n"
            f"# callback '{mod_name}.{qualname}' is not importable from this module.\n"
            f"# Re-execute the cell that registered it before fetching.\n"
        )

    def extended_metadata(self, ctx) -> dict:
        return {
            "vp_path": "/".join(self._path),
            "callback": {
                "module": getattr(self._callback, "__module__", None),
                "qualname": getattr(self._callback, "__qualname__", None),
            },
            "knobs_schema": (
                self._knobs_model.model_json_schema()
                if self._knobs_model is not None else None
            ),
            "knob_specs": [s.model_dump() if hasattr(s, "model_dump") else s
                           for s in self._knob_specs],
        }
```

(Add `from typing import Optional` if not already imported.)

- [ ] **Step 4: Run tests to verify pass**

```
uv run pytest tests/test_provider_snippets.py -v
```
Expected: 12 passed.

- [ ] **Step 5: Commit**

```
git add SciQLop/components/plotting/backend/easy_provider.py tests/test_provider_snippets.py
git commit -m "feat(graph-context): EasyProvider three-tier snippet + extended_metadata"
```

---

## Task 11: `add_graph_context_actions` helper

**Files:**
- Create: `SciQLop/components/plotting/ui/graph_context_menu.py`
- Test: `tests/test_graph_context_integration.py`

- [ ] **Step 1: Write the failing tests**

```python
# Add to tests/test_graph_context_integration.py
def test_add_graph_context_actions_shows_copy_for_speasy(qtbot, monkeypatch):
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QMenu
    from SciQLop.components.plotting.ui.graph_context_menu import (
        add_graph_context_actions,
    )
    from SciQLop.core.graph_context import (
        attach_context, _build_speasy_ctx,
    )
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
    ctx = _build_speasy_ctx(g, panel_name="P", plot_index=0,
                             speasy_id="a/b", graph_type="Line")
    # provider_name in ctx must match the registered provider:
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
    from SciQLop.core.graph_context import _build_static_ctx

    class _FakeGraph(QObject):
        def __init__(self, name):
            super().__init__(); self.setObjectName(name)
        _md = {}
        def meta_data(self): return dict(self._md)
        def set_meta_data(self, d): self._md = dict(d)
        def name(self): return self.objectName()

    g = _FakeGraph("g_static")
    ctx = _build_static_ctx(g, panel_name="P", plot_index=0,
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
    from SciQLop.core.graph_context import _build_speasy_ctx
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
    ctx = _build_speasy_ctx(g, panel_name="P", plot_index=0,
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
```

- [ ] **Step 2: Run tests to verify failure**

```
uv run pytest tests/test_graph_context_integration.py -v
```
Expected: ImportError on `add_graph_context_actions`.

- [ ] **Step 3: Create the helper**

```python
# SciQLop/components/plotting/ui/graph_context_menu.py
"""Menu helper that adds per-graph 'Copy Python code' actions to a panel-level
context menu.
"""
from typing import Iterable

from PySide6.QtGui import QGuiApplication

from SciQLop.core.graph_context import context_of, provider_for


def add_graph_context_actions(menu, graphs: Iterable) -> None:
    """For each graph that has both a context and a provider that can produce
    a snippet, add a 'Copy Python code: <name>' (or just 'Copy Python code'
    when there is only one graph) action to `menu`.
    """
    eligible = []
    for g in graphs:
        ctx = context_of(g)
        if ctx is None:
            continue
        provider = provider_for(ctx)
        if provider is None:
            continue
        snippet = None
        try:
            snippet = provider.python_snippet(ctx)
        except Exception:
            continue
        if not snippet:
            continue
        eligible.append((g, snippet))
    if not eligible:
        return
    menu.addSeparator()
    if len(eligible) == 1:
        g, snippet = eligible[0]
        act = menu.addAction("Copy Python code")
        act.triggered.connect(
            lambda _checked=False, s=snippet: QGuiApplication.clipboard().setText(s)
        )
        return
    for g, snippet in eligible:
        label = g.name() if hasattr(g, "name") else g.objectName()
        act = menu.addAction(f"Copy Python code: {label}")
        act.triggered.connect(
            lambda _checked=False, s=snippet: QGuiApplication.clipboard().setText(s)
        )
```

- [ ] **Step 4: Run tests to verify pass**

```
uv run pytest tests/test_graph_context_integration.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```
git add SciQLop/components/plotting/ui/graph_context_menu.py tests/test_graph_context_integration.py
git commit -m "feat(graph-context): add_graph_context_actions menu helper"
```

---

## Task 12: Wire context-menu into `_show_context_menu`

**Files:**
- Modify: `SciQLop/components/plotting/ui/time_sync_panel.py:705-718`
- Test: `tests/test_graph_context_integration.py`

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_graph_context_integration.py
def test_show_context_menu_calls_graph_context_actions(qtbot, monkeypatch):
    from SciQLop.components.plotting.ui import time_sync_panel as tsp

    captured = {"called": False}
    def _capture_add(menu, graphs):
        captured["called"] = True
        captured["graphs"] = list(graphs)
    monkeypatch.setattr(tsp, "add_graph_context_actions", _capture_add)

    # Build a TimeSyncPanel and call _show_context_menu
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.core import TimeRange
    panel = TimeSyncPanel(parent=None, name="ContextMenuPanel",
                          time_range=TimeRange(0.0, 1.0))
    qtbot.addWidget(panel)
    panel._show_context_menu(panel.mapToGlobal(panel.rect().center()))
    assert captured["called"]
```

- [ ] **Step 2: Run test to verify failure**

```
uv run pytest tests/test_graph_context_integration.py::test_show_context_menu_calls_graph_context_actions -v
```
Expected: AssertionError — `add_graph_context_actions` not called.

- [ ] **Step 3: Wire `_show_context_menu`**

Edit `SciQLop/components/plotting/ui/time_sync_panel.py`. Add to imports:

```python
from SciQLop.components.plotting.ui.graph_context_menu import add_graph_context_actions
```

Add a helper at module level:

```python
def _all_graphs(panel) -> list:
    """Return all SciQLopGraph children of all plots in the panel."""
    out = []
    for plot in panel.plots():
        for child in plot.children():
            if hasattr(child, "set_meta_data") and hasattr(child, "meta_data"):
                out.append(child)
    return out
```

Replace `_show_context_menu` (lines 705-718) with:

```python
    def _show_context_menu(self, global_pos):
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        self._catalog_manager.build_catalogs_menu(menu)
        menu.addSeparator()
        menu.addAction("Export as PNG…", self._export_png)
        menu.addAction("Export as PDF…", self._export_pdf)
        menu.addSeparator()
        if self._template_source_path:
            menu.addAction("Update template", self._update_template)
        menu.addAction("Save as template…", self._quick_save_template)
        menu.addAction("Export template…", self._export_template)
        self._append_knob_reset_actions(menu)
        add_graph_context_actions(menu, _all_graphs(self))
        menu.exec(global_pos)
```

- [ ] **Step 4: Run test to verify pass**

```
uv run pytest tests/test_graph_context_integration.py::test_show_context_menu_calls_graph_context_actions -v
```
Expected: 1 passed.

- [ ] **Step 5: Commit**

```
git add SciQLop/components/plotting/ui/time_sync_panel.py tests/test_graph_context_integration.py
git commit -m "feat(graph-context): wire add_graph_context_actions into TimeSyncPanel context menu"
```

---

## Task 13: End-to-end smoke test (full suite)

**Files:**
- (none — runs the existing suite)

- [ ] **Step 1: Run the full test suite**

```
uv run pytest tests/ --ignore=tests/fuzzing -q
```
Expected: all tests pass, plus the new ones added in Tasks 1–12.

- [ ] **Step 2: Verify no regressions in producer paths**

```
uv run pytest tests/test_creating_plots.py tests/test_virtual_products.py -v
```
Expected: existing producer tests still pass.

- [ ] **Step 3: Manual smoke (recorded as a checklist; no automation)**

- [ ] Launch SciQLop: `uv run sciqlop`
- [ ] Drag a speasy product onto a panel
- [ ] Right-click on the panel → "Copy Python code" appears
- [ ] Click it → paste into a terminal — snippet contains `import speasy as spz` and the product id
- [ ] Create a virtual product via the embedded Jupyter console using a module-level callable
- [ ] Right-click → "Copy Python code" appears with `from <module> import <qualname>`
- [ ] Create a VP using a lambda — right-click "Copy Python code" still appears but contains the "not importable" stub comment
- [ ] Plot static data via `panel.plot([1,2,3], [4,5,6])` — right-click does **not** show "Copy Python code"

- [ ] **Step 4: Commit any final adjustments**

If the manual smoke surfaces any issues, fix and:

```
git commit -am "fix(graph-context): <issue from manual smoke>"
```

---

## Self-review notes

**Spec coverage:**
- ✅ Schema (Task 1)
- ✅ Storage helpers (Task 3)
- ✅ Builder helpers (Task 4)
- ✅ `_is_importable` (Task 2)
- ✅ Producer wiring — `_post_plot` (speasy + VP) (Task 5)
- ✅ Producer wiring — `plot_static_data` (Task 6)
- ✅ Producer wiring — `plot_function` (Task 6)
- ✅ Knob update slot (Task 7) — slot exists; full inspector wiring deferred to P4 plan
- ✅ DataProvider defaults (Task 8)
- ✅ SpeasyPlugin overrides (Task 9)
- ✅ EasyProvider overrides — three-tier (Task 10)
- ✅ Menu helper (Task 11)
- ✅ Menu wiring (Task 12)
- ✅ End-to-end smoke (Task 13)

**Deferred to follow-up plan (P3 + P4):**
- Hover tooltip on graphs.
- Inspector node `GraphContextExtension` and *Show full metadata…* dialog.
- Live wiring of `update_knobs` to the inspector knob-change signal (the slot exists; the connect call belongs in P4 since the inspector is the consumer).

**Type / signature consistency check:**
- `attach_context(graph, ctx, rich=None)` — defined in Task 3, used in Tasks 5/6/7/11.
- `context_of(graph) -> Optional[GraphContext]` — Task 3, used Tasks 5/7/11.
- `_build_speasy_ctx`, `_build_vp_ctx`, `_build_function_ctx`, `_build_static_ctx` — Task 4, used Tasks 5/6.
- `python_snippet(self, ctx) -> Optional[str]` — Task 8 default; Tasks 9/10 overrides; consumer Task 11.
- `extended_metadata(self, ctx) -> dict` — Task 8 default; Tasks 9/10 overrides. Consumer in P4.
- `add_graph_context_actions(menu, graphs)` — Task 11, used Task 12.
- `provider_for(ctx) -> Optional[DataProvider]` — Task 3, used Task 11.
