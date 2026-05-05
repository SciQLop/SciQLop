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


def provider_for(ctx: GraphContext) -> Optional[DataProvider]:
    """Return the DataProvider instance for ctx, or None."""
    if not ctx.provider_name:
        return None
    from SciQLop.components.plotting.backend.data_provider import providers
    return providers.get(ctx.provider_name)
