"""Per-graph metadata envelope. See docs/plans/2026-05-05-graph-context-metadata.md."""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Literal, Optional

from pydantic import BaseModel, Field

from SciQLop.components import sciqlop_logging

if TYPE_CHECKING:
    from SciQLop.components.plotting.backend.data_provider import DataProvider

log = sciqlop_logging.getLogger(__name__)

_RICH: dict[str, GraphRichRefs] = {}

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
    product_path: Optional[list[str]] = None

    provider_name: Optional[str] = None
    knobs: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}

    def to_meta_data(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


@dataclass(slots=True)
class GraphRichRefs:
    """Python-only references that can't go in the C++ meta_data slot."""
    callback: Optional[Callable] = None
    knobs_model: Optional[type] = None


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
        try:
            graph.destroyed.connect(
                lambda _=None, gid=ctx.graph_id: _RICH.pop(gid, None)
            )
        except (AttributeError, RuntimeError):
            log.debug("attach_context: no destroyed signal for %s; "
                      "rich ref will leak", ctx.graph_id)


def context_of(graph) -> Optional[GraphContext]:
    """Reconstruct GraphContext from graph.meta_data, filtering unknown fields
    so a newer SciQLop's extra fields don't blow up older readers.
    """
    try:
        raw = graph.meta_data() or {}
    except AttributeError:
        return None
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


def provider_for(ctx: GraphContext) -> Optional[DataProvider]:
    """Return the DataProvider instance for ctx, or None."""
    if not ctx.provider_name:
        return None
    from SciQLop.components.plotting.backend.data_provider import providers
    return providers.get(ctx.provider_name)


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


def build_speasy_ctx(graph, *, panel_name: str, plot_index: int,
                     speasy_id: str, graph_type: str,
                     product_path: Optional[list] = None,
                     knobs: Optional[dict] = None) -> GraphContext:
    return GraphContext(
        kind="speasy",
        graph_id=graph.objectName(),
        panel_name=panel_name,
        plot_index=plot_index,
        graph_type=graph_type,
        speasy_id=speasy_id,
        provider_name="Speasy",
        product_path=list(product_path) if product_path else None,
        knobs=knobs or {},
    )


def build_vp_ctx(graph, *, panel_name: str, plot_index: int,
                 vp_path: "str | list[str] | tuple[str, ...]",
                 provider_name: str, callback: Callable,
                 graph_type: str,
                 product_path: Optional[list] = None,
                 knobs: Optional[dict] = None) -> GraphContext:
    vp_path_list = list(vp_path) if isinstance(vp_path, (list, tuple)) else [str(vp_path)]
    vp_path_str = "/".join(vp_path_list)
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
        product_path=list(product_path) if product_path else vp_path_list,
        knobs=knobs or {},
    )


def build_function_ctx(graph, *, panel_name: str, plot_index: int,
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


def build_static_ctx(graph, *, panel_name: str, plot_index: int,
                     graph_type: str) -> GraphContext:
    return GraphContext(
        kind="static",
        graph_id=graph.objectName(),
        panel_name=panel_name,
        plot_index=plot_index,
        graph_type=graph_type,
        provider_name=None,
    )


def graph_name(graph) -> str:
    """Display name for a graph. Real SciQLopPlots graphs expose ``name`` as a
    string property; legacy/test stand-ins expose it as a method. Falls back to
    ``objectName()`` when neither yields anything usable.
    """
    n = getattr(graph, "name", None)
    if callable(n):
        try:
            n = n()
        except Exception:
            n = None
    return n or graph.objectName()


def graph_time_range(graph) -> Optional[tuple]:
    """Best-effort read of the live (start, stop) epoch-second range from the
    graph's owning SciQLopPlot's time axis. Returns None if unavailable.

    Graphs are NOT direct Qt children of SciQLopPlot — they parent to its
    inner QRhiWidget render surface (see ``sciqlopplots-plot-widget-
    composition.md``). Walk ancestors until we find one that exposes
    ``time_axis``.
    """
    try:
        node = graph.parent() if hasattr(graph, "parent") else None
        while node is not None and not hasattr(node, "time_axis"):
            node = node.parent() if hasattr(node, "parent") else None
        if node is None:
            return None
        r = node.time_axis().range()
        return float(r.start()), float(r.stop())
    except Exception:
        return None


def _last_fetch_line(graph) -> str:
    """Best-effort 'N points · dtype' from graph.data() for the tooltip."""
    try:
        d = graph.data()
        if d is None:
            return ""
        if hasattr(d, "__len__") and len(d) > 0 and hasattr(d[0], "__len__"):
            arr = d[0]
            n = len(arr)
            dtype = getattr(arr, "dtype", "")
            return f"{n} points · {dtype}".rstrip(" ·")
    except Exception:
        pass
    return ""


def graph_tooltip(graph) -> str:
    """Multi-line summary of a graph's attached context: title, knobs, last
    fetch volume. Used by the inspector tree's hover tooltip. Returns "" when
    the graph has no context attached so the caller can leave the existing
    tooltip untouched.
    """
    ctx = context_of(graph)
    if ctx is None:
        return ""
    name = graph_name(graph)
    if ctx.kind == "speasy":
        title = f"{name}: {ctx.speasy_id} — Speasy"
    elif ctx.kind == "vp":
        title = f"{name}: {ctx.vp_path} — Virtual"
    elif ctx.kind == "function":
        cb = f"{ctx.callback_module}.{ctx.callback_qualname}".strip(".")
        title = f"{name}: function {cb}"
    else:
        title = f"{name}: static data"
    lines = [title]
    if ctx.knobs:
        knob_str = ", ".join(f"{k}={v!r}" for k, v in ctx.knobs.items())
        lines.append(f"Knobs: {knob_str}")
    last = _last_fetch_line(graph)
    if last:
        lines.append(last)
    return "\n".join(lines)


