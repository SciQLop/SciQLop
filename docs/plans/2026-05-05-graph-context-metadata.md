# Graph Context Metadata

**Status:** Design (draft)
**Date:** 2026-05-05
**Owner:** Alexis Jeandet
**Related:** runtime tracer (already shipped), suspected-races doc, inspector extensions

## Background

SciQLop graphs carry a lot of implicit context — which speasy product they
plot, which virtual product callback drives them, what knobs they're
parameterised with, what range they were last fetched on. Today this context
is scattered across the producers (`plot_product`, `plot_function`,
`plot_data`, `create_virtual_product`), the providers (`SpeasyPlugin`,
`EasyProvider`), and the SciQLopPlots C++ side. There is no single,
addressable view of "what is this graph".

Several features want that view:

- **Tracer** thread-naming benefits from product context (already partly
  wired via zone args; an envelope formalises it).
- **Inspector** — currently shows knobs and layers; could show the source
  identity, last-fetch shape, units.
- **Right-click → "Copy Python code"** — let the user paste a snippet that
  reproduces the graph's data fetch in Jupyter.
- **Hover tooltips** with the speasy uid, components, last fetch shape.

Each feature alone is small. Building them one by one means each invents a
local slice of the same metadata. This spec proposes a unified per-graph
**context envelope** so all four readers share one schema and one storage
mechanism.

## Goals

1. One canonical schema for per-graph metadata, used by tracer (where
   helpful), inspector, context menu, tooltip.
2. Each provider owns its source-specific extensions (snippet generation,
   extended metadata) — no special-casing in core.
3. Best-effort everywhere: missing fields → consumers degrade gracefully.
4. No new threading or lifecycle complexity. Single-threaded write path
   (main thread only). Reads from the main thread only.
5. Backwards-compatible: graphs created without going through our `plot_*`
   helpers (e.g. plugin code talking directly to `SciQLopPlots`) still work,
   they just don't get an envelope and consumers hide the corresponding UI.

## Non-goals

- No persistence. The envelope is rebuilt at graph creation each session.
  Workspace save/reload re-creates the graph through the same producers, so
  the envelope re-populates automatically.
- No cross-graph queries (no "list all graphs of provider X"). A registry
  of graphs already exists indirectly through SciQLopPlots; we don't
  duplicate it.
- No serialization to YAML / JSON files. The envelope lives in-process.
- No cross-language consumers in v1. The C++ slot is populated and could be
  read from C++ later, but no C++ reader is planned.
- No mutation of envelope fields from worker threads. Post-fetch shape /
  dtype / units are *derived on demand* from `graph.data()` at read time.

## Architecture

```
┌───────────────────────────────────────────────────────────────────────┐
│ SciQLop                                                               │
│                                                                       │
│  ┌─────────────────┐                       ┌────────────────────┐     │
│  │ Producers       │      writes once      │ graph.meta_data    │     │
│  │ - plot_product  ├──────────────────────▶│ (C++ QVariantMap)  │     │
│  │ - plot_function │                       │ — lean stringly    │     │
│  │ - plot_data     │                       └─────────┬──────────┘     │
│  │ - VP creation   │                                 │                │
│  └────────┬────────┘                                 │                │
│           │                                          │                │
│           │ stashes rich refs by graph_id            │                │
│           ▼                                          │                │
│  ┌─────────────────────────┐                         │                │
│  │ _RICH: dict[gid, Refs]  │                         │                │
│  │ - callback ref          │                         │                │
│  │ - knobs_model class     │                         │                │
│  └────────────┬────────────┘                         │                │
│               │                                      │                │
│  ┌── consumers ──────────────────────────────────────┴─────────────┐  │
│  │                                                                 │  │
│  │  context_menu  →  provider.python_snippet(ctx)  → clipboard     │  │
│  │  inspector     →  provider.extended_metadata(ctx) + ctx fields  │  │
│  │  tooltip       →  ctx fields + graph.data() shape on demand     │  │
│  │  tracer        →  zone args (independent of registry)           │  │
│  │                                                                 │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────┘
```

**Two stores realise one schema:**
- The **C++ `graph.meta_data` slot** carries the stringly-typed subset
  (everything QVariantMap can represent).
- A **module-level Python sidecar** (`_RICH`, a `dict[str, GraphRichRefs]`
  keyed by `graph.objectName()`) carries Python-only references — callback
  refs, the `knobs_model` Pydantic class.

Eviction is per-graph: each `attach_context(...)` call connects a slot to
the graph's `destroyed` signal that pops the corresponding `_RICH` entry.

**No central registry class, no lock.** All writes happen on the main
thread (graph creation, knob change). All reads happen on the main thread
(menu, inspector, tooltip).

## Data model

`SciQLop/core/graph_context.py`

```python
from typing import Any, Literal, Optional, Callable
from pydantic import BaseModel, Field

GraphKind = Literal["speasy", "vp", "static", "function"]


class GraphContext(BaseModel):
    """Per-graph metadata envelope. Single schema, two stores."""

    # Identity (set at creation, not mutated post-creation except for knobs)
    kind: GraphKind
    graph_id: str
    panel_name: str
    plot_index: int
    graph_type: str

    # Source identification — exactly one set per kind
    speasy_id: Optional[str] = None
    vp_path: Optional[str] = None
    callback_qualname: Optional[str] = None
    callback_module: Optional[str] = None

    provider_name: Optional[str] = None  # None for static/function
    knobs: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}

    def to_meta_data(self) -> dict:
        return self.model_dump(exclude_none=True)


from dataclasses import dataclass


@dataclass(slots=True)
class GraphRichRefs:
    """Python-only references that can't go in the C++ meta_data slot."""
    callback: Optional[Callable] = None
    knobs_model: Optional[type] = None
```

**Mutable post-fetch state** (`last_n_points`, `last_dtype`, `last_units`,
`last_components`, `last_range`) is intentionally **not** in the model.
Tooltip and inspector derive these on demand:

- `last_n_points`, `last_dtype` → from `graph.data()` (length and ndarray
  dtype of the live data).
- `last_range`, `last_units`, `last_components` → from the provider's
  `extended_metadata(ctx)` call (which can consult speasy / VP knobs / etc.).

This avoids any worker-thread write path. The cost is one `graph.data()`
call when the inspector/tooltip refreshes — cheap; the data is already in
memory C++ side.

**Schema choices:**
- `extra="forbid"` at *write* — typos at the producer fail fast.
- The *read* helper `context_of(graph)` validates with try/except so
  cross-version reads degrade gracefully (returns `None` on schema
  mismatch).
- Discriminated union via `kind` rather than a `Source = Speasy | VP |
  Static | Function` sum type — keeps the model flat for QVariantMap
  serialisation.
- `graph_id = graph.objectName()` — already used as cross-reference key
  elsewhere (`SciQLop/user_api/plot/_panel.py:262`).

## Storage

```python
# SciQLop/core/graph_context.py

_RICH: dict[str, GraphRichRefs] = {}


def attach_context(graph, ctx: GraphContext,
                   rich: Optional[GraphRichRefs] = None) -> None:
    """Write the lean envelope to the C++ slot and stash rich refs."""
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
    """Reconstruct GraphContext from graph.meta_data.

    Filters to known model fields before validating so a newer SciQLop
    that wrote extra fields can still be read by an older one — `extra=
    "forbid"` on the model is for catching typos at *write* (producers),
    not for blocking forward-compat reads.
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


def provider_for(ctx: GraphContext) -> Optional["DataProvider"]:
    if not ctx.provider_name:
        return None
    from SciQLop.components.plotting.backend.data_provider import providers
    return providers.get(ctx.provider_name)
```

That's the entirety of the storage layer — three module-level functions
plus one global dict. ~40 lines of Python.

## Producer side

Four creation paths in `SciQLop/components/plotting/ui/time_sync_panel.py`
each call `attach_context` exactly once after the graph is built:

| Producer entry | What it builds |
|---|---|
| `_plot_product` (speasy product) | `kind="speasy"`, `speasy_id=<resolved id>`, `provider_name="Speasy"`, `panel_name`, `plot_index`, `graph_type`. `rich=None`. |
| `_plot_product` (VP) | `kind="vp"`, `vp_path=<EasyProvider._path>`, `provider_name=<EasyProvider.name>`, `callback_qualname/module`, `knobs={current values}`. `rich=GraphRichRefs(callback=cb, knobs_model=cls)`. |
| `_plot_function` | `kind="function"`, `provider_name=None`, callback module/qualname. `rich=GraphRichRefs(callback=cb, knobs_model=None)`. |
| `_plot_static_data` | `kind="static"`, no source identifier, `rich=None`. |

Four small builder helpers live in `graph_context.py`:

```python
def _build_speasy_ctx(graph, plot, panel_name, plot_index, speasy_id,
                       graph_type, knobs) -> GraphContext: ...
def _build_vp_ctx(graph, plot, panel_name, plot_index, easy_provider,
                   graph_type, knobs) -> GraphContext: ...
def _build_function_ctx(graph, plot, panel_name, plot_index, callback,
                         graph_type) -> GraphContext: ...
def _build_static_ctx(graph, plot, panel_name, plot_index,
                       graph_type) -> GraphContext: ...
```

Each producer calls one of these and then `attach_context(graph, ctx, rich)`.

**Knob updates.** When a user changes a knob in the inspector, the existing
knob system fires a per-graph signal. `attach_context` connects a slot
that re-reads the current knob values and re-writes `graph.meta_data` with
the updated `knobs` dict. The slot is a no-op if the rich entry has been
evicted (graph destroyed before signal delivered).

## Provider interface

`SciQLop/components/plotting/backend/data_provider.py` — extend
`DataProvider` with two methods, both with safe defaults:

```python
class DataProvider:
    # existing methods unchanged

    def python_snippet(self, ctx: GraphContext) -> Optional[str]:
        """Return a self-contained Python snippet that reproduces this
        graph's data fetch, or None if the source isn't reproducible by
        snippet. Default: None."""
        return None

    def extended_metadata(self, ctx: GraphContext) -> dict:
        """Return rich metadata about this graph's source. Format is
        free-form per provider. Default: empty."""
        return {}
```

`ctx` is the full `GraphContext` so providers can reach knob values, etc.,
without re-deriving them.

### SpeasyPlugin overrides

`SciQLop/plugins/speasy_provider/speasy_provider.py`:

```python
def python_snippet(self, ctx: GraphContext) -> Optional[str]:
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

def extended_metadata(self, ctx: GraphContext) -> dict:
    if ctx.kind != "speasy" or not ctx.speasy_id:
        return {}
    index = self._resolve_index(ctx.speasy_id)
    if index is None:
        return {}
    return {
        "speasy_id": ctx.speasy_id,
        "inventory": _index_to_dict(index),
        "parameter_type": str(getattr(index, "parameter_type", "")) or None,
    }
```

(Time-range substitution into the snippet is left as a follow-up if
desired — for now placeholders are clearer than a stale "last range" that
may not match what the user wants to fetch.)

### EasyProvider overrides

`SciQLop/components/plotting/backend/easy_provider.py` — three-tier
snippet:

```python
def python_snippet(self, ctx: GraphContext) -> Optional[str]:
    if ctx.kind != "vp" or self._callback is None:
        return None
    cb = self._callback
    mod_name = getattr(cb, "__module__", None)
    qualname = getattr(cb, "__qualname__", None)
    if not (mod_name and qualname):
        return None
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

def extended_metadata(self, ctx: GraphContext) -> dict:
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
        "knob_specs": [s.model_dump() for s in self._knob_specs],
    }
```

Helper:

```python
def _is_importable(module_name: str, qualname: str, obj) -> bool:
    """Return True iff `qualname` resolves from `module_name` to exactly `obj`."""
    try:
        import importlib
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

## Consumers

### Tracer thread naming

Already implemented in `SciQLop/core/tracing.py`. Reads zone args (we
already pass `product=...` in `provider._get_data`, `speasy.get_data`,
`vp.callback`). No change required for v1; the design is forward-
compatible if we later want richer names like `provider[amda/imf]`.

### Right-click "Copy Python code"

Lives in a small new helper:

`SciQLop/components/plotting/ui/graph_context_menu.py`:

```python
from PySide6.QtGui import QGuiApplication

def add_graph_context_actions(menu, graph) -> None:
    ctx = context_of(graph)
    if ctx is None:
        return
    provider = provider_for(ctx)
    snippet = provider.python_snippet(ctx) if provider else None
    if snippet:
        act = menu.addAction("Copy Python code")
        act.triggered.connect(
            lambda: QGuiApplication.clipboard().setText(snippet)
        )
```

`time_sync_panel.py` `_show_context_menu` calls
`add_graph_context_actions(menu, graph)` for the targeted graph.

When the snippet is `None`, the action is **omitted** — not greyed out.
We do not advertise a feature that won't deliver.

### Hover tooltip

`SciQLop/core/graph_context.py`:

```python
def graph_tooltip(graph) -> str:
    ctx = context_of(graph)
    if ctx is None:
        return ""
    lines = []
    if ctx.kind == "speasy":
        lines.append(f"{ctx.speasy_id} — Speasy")
    elif ctx.kind == "vp":
        lines.append(f"{ctx.vp_path} — Virtual")
    elif ctx.kind == "function":
        cb = f"{ctx.callback_module}.{ctx.callback_qualname}".strip(".")
        lines.append(f"function: {cb}")
    elif ctx.kind == "static":
        lines.append("static data")
    last = _last_fetch_line_from_graph(graph)
    if last:
        lines.append(last)
    return "\n".join(lines)


def _last_fetch_line_from_graph(graph) -> str:
    """Derive 'N points · dtype' from graph.data() if available."""
    try:
        d = graph.data()
        if d is None:
            return ""
        # graph.data() shape varies by graph type; we just want first array len
        if hasattr(d, "__len__") and len(d) > 0 and hasattr(d[0], "__len__"):
            arr = d[0]
            n = len(arr)
            dtype = getattr(arr, "dtype", "")
            return f"{n} points · {dtype}".rstrip(" ·")
    except Exception:
        pass
    return ""
```

**Tooltip plumbing — exact hook TBD at P3 implementation time.**
`SciQLopPlottableInterface` exposes `meta_data` / `set_meta_data` (verified)
but the introspection at design time did not confirm a `set_tooltip` /
`setToolTip` accessor on graphs themselves. P3's first task is to confirm
which of the following is available:

1. **`graph.set_tooltip(text)`** if exposed by SciQLopPlots — preferred.
2. **`plot.setToolTip(text)`** on the parent `SciQLopPlot` — coarser
   (one tooltip per plot, not per graph) but works today.
3. **Hover-event capture** on the plot, popping a `QToolTip` at cursor
   position with the targeted-graph's text — heaviest, most flexible.

If (1) isn't available, fall back to (2) for v1 and revisit (3) only if
multi-graph plots become the common case.

Refresh hooks (independent of which tooltip-mechanism wins): on creation,
on knob change (existing knob-system per-graph signal), and on
post-`set_data` (the SciQLopPlots signal that lands data — exact name
identified during P3).

The `_last_fetch_line_from_graph` heuristic above handles line/multiline
graphs cleanly. ColorMaps have a different `graph.data()` shape; v1 just
omits the line for them. A second pass for colormap-aware shape reporting
is listed in *Out of scope*.

### Inspector node

A new inspector extension at
`SciQLop/components/plotting/ui/graph_context_inspector/extension.py`,
following the existing `KnobInspectorExtension` /
`LayerExtension` shape (`components/plotting/ui/knob_inspector/extension.py`).

**Scope vs `KnobInspectorExtension`.** This new extension is a *read-only
identity panel*. The "Knobs" line shows current values as a comma-joined
summary (or "(none)"); the existing `KnobInspectorExtension` continues to
own knob *editing* UI. The two extensions appear next to each other in
the inspector dock; no duplication of editor widgets.

Renders:

```
Source     Speasy: amda/imf
Plot       Panel "FGM" / plot 0 (Line)
Knobs      (none)
Last fetch 1.2M points · float32
[ Show full metadata… ]   [ Copy Python code ]
```

Two buttons:
- **Copy Python code** — same path as the right-click action.
- **Show full metadata…** — opens a small dialog whose content is
  `provider.extended_metadata(ctx)` rendered as a tree (`QTreeView` with a
  small `dict → tree` model — same pattern used by
  `catalog-event-metadata-edition` per the existing component).

## Error handling

| Failure mode | Behaviour |
|---|---|
| `graph.set_meta_data(...)` raises | Log at DEBUG; rich entry still alive; readers fall through to "no envelope". |
| `graph.meta_data()` empty / unknown | `context_of` returns None; consumers hide their UI. |
| `GraphContext.model_validate(raw)` fails | Caught; returns None; logged at DEBUG. |
| Provider's `python_snippet` raises | Treated as None; action hidden; logged at WARNING (provider bug). |
| Provider's `extended_metadata` raises | Returns `{}`; dialog still opens with one row "Error: <repr>"; logged at WARNING. |
| `provider_for(ctx)` returns None (provider unloaded) | Same as "no envelope" path. |
| Knob update slot fires after graph destroyed | `_RICH.get(gid)` returns None — no-op. |

**Threading rule:** writes only from main thread (creation, knob change
slots). Reads only from main thread (menu, inspector, tooltip refresh
fired by Qt signals). No worker-thread access to the envelope. The tracer
auto-namer is independent — it reads zone args, not the envelope.

## Testing

Three layers, mapping to the existing `tests/` structure with `pytest-qt`
+ `pytest-xvfb`.

### Unit (`tests/test_graph_context.py`)

- Schema accepts known fields, rejects extras at write.
- `context_of` returns None on empty / garbage / unknown-field inputs.
- `_is_importable` matrix: module-level fn (true), lambda (false),
  closure (false — `<locals>`), aliasing (false), decorated round-trip (true).
- `to_meta_data` round-trip equals original.
- `attach_context` connects to `graph.destroyed`; firing it pops the
  `_RICH` entry.

### Provider (`tests/test_provider_snippets.py`)

- `SpeasyPlugin.python_snippet` with full envelope produces a snippet
  containing `import speasy as spz`, the speasy_id, `product_inputs={...}`
  when knobs present. Returns None for `kind="vp"`.
- `SpeasyPlugin.extended_metadata` known id → populated dict; unknown
  id → empty.
- `EasyProvider.python_snippet` three-tier matrix (importable / closure /
  lambda).
- `EasyProvider.extended_metadata` returns vp_path, callback,
  knobs_schema (when model set), knob_specs.

### Integration (`tests/test_graph_context_integration.py`, `pytest-qt`)

- End-to-end: create panel, plot a fake speasy product, assert
  `context_of(graph)` returns populated context.
- C++ slot mirror: after `attach_context`, `graph.meta_data()` reflects
  the lean fields. After knob change, slot updated.
- Snippet copy action present for speasy graph, absent for `plot_data`
  static-array graph.
- Tooltip refresh: `graph.toolTip()` updates after a fetch (drives a fake
  `easy_provider` fetch).
- Graph destroyed → `_RICH` empty.

### Out of scope

- C++ QVariant marshalling — SciQLopPlots' responsibility.
- Inspector visual rendering — manual smoke.
- `spz.get_data` network paths.

## Phasing

Each phase is independently shippable. Phases compose; nothing in P2+
depends on changes outside its phase.

**P1 — schema + storage + producers.**
- Land `SciQLop/core/graph_context.py` with `GraphContext`,
  `GraphRichRefs`, `attach_context`, `context_of`, `rich_of`,
  `provider_for`, builder helpers.
- Wire the four producers in `time_sync_panel.py`.
- Tests: unit + the "C++ slot mirror" integration test.

**P2 — provider methods + right-click snippet.**
- Add `python_snippet` / `extended_metadata` to `DataProvider` (no-op
  defaults).
- Speasy plugin override.
- `EasyProvider` override (three-tier).
- `add_graph_context_actions` helper + wire into `_show_context_menu`.
- Tests: provider tests + "snippet copy action present" integration test.

**P3 — hover tooltip.**
- `graph_tooltip(graph)` and refresh hook on creation + knob change.
- Tests: tooltip-refresh integration test.

**P4 — inspector extension + extended-metadata dialog.**
- `graph_context_inspector/extension.py`.
- Dialog: `dict → tree` viewer (reuse the existing pattern from the
  catalog event-metadata edition).
- Manual smoke; no automated tests for visuals.

## Out of scope / future work

- **Cross-language consumers** of the C++ `meta_data` slot. The data is
  there; building C++/QML readers is left for when there's a concrete
  user.
- **Persistence.** Workspaces re-instantiate graphs through the producers,
  so the envelope re-populates. If we ever want offline analysis of
  workspace state, we revisit.
- **Time-range substitution in snippets.** Today's snippets emit
  placeholder ISO strings. We could capture the "last fetched range" from
  graph state at right-click time and substitute. Punt: placeholders are
  clearer for users who want to fetch a different range.
- **Tracer envelope integration.** Auto-namer could read `meta_data` on
  first zone instead of relying on zone args. Currently zone args already
  provide `product=...` so it works; this would be a refinement, not a fix.
- **Inline `plot_function` snippet generation.** These callables are
  fundamentally non-importable (REPL-defined); we don't pretend otherwise.
- **`plot_data(speasy_variable)`** today extracts arrays via
  `_speasy_variable_to_arrays` and the resulting graph is plain static
  data. We could promote this to `kind="speasy"` with a `_static_origin`
  marker that records the source speasy_id but disables snippet
  generation (since the original time range is implicit in the variable,
  not a fetch-able command). Punt: clean static-data semantics today are
  better than a half-true speasy origin.
- **Colormap-aware shape reporting in tooltips.** The line/multiline
  heuristic doesn't cover the `(time, freq, values)` shape of color maps.
  A second pass is straightforward but needs the graph_type discriminator
  in the tooltip builder.
- **Internal-consistency assertion in CI.** A producer test that exercises
  every `plot_*` path could verify that the resulting `context_of(graph)`
  has all required-by-kind fields populated. Listed for the test plan but
  not designed in detail here.
