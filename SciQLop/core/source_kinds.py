"""Where a graph's data comes from: the sciqlop.source_kinds extension point (spec §4.2)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from SciQLop.core.extensions import ExtensionPoint, declare

if TYPE_CHECKING:
    from SciQLop.core.graph_context import GraphContext

SPEASY, VP, FUNCTION, STATIC, PROVIDER = (
    "sciqlop.speasy", "sciqlop.vp", "sciqlop.function", "sciqlop.static", "sciqlop.provider")
# Values written before source kinds were contributions; saved workspaces and templates still hold them.
LEGACY_IDS = {"speasy": SPEASY, "vp": VP, "function": FUNCTION, "static": STATIC}


def _nothing(ctx: GraphContext) -> str:
    return ""


@dataclass(frozen=True)
class SourceKind:
    id: str
    tooltip: Callable[[GraphContext], str]                 # after "<graph name>: " in the inspector tree tooltip
    inspector_line: Callable[[GraphContext], str]          # the source line of the graph inspector
    product_path: Callable[[GraphContext], str] = _nothing  # "a//b//c" to re-plot from (templates), "" if none
    shareable: bool = False                                # Export & Share can send it to the Speasy proxy


SOURCE_KINDS = declare(ExtensionPoint("sciqlop.source_kinds", SourceKind, what="source kind",
                                      doc="Where a graph's data comes from: tooltip, inspector line, template path."))


def canonical_id(kind: str) -> str:
    return LEGACY_IDS.get(kind, kind)


def _missing(kid: str) -> SourceKind:
    text = f"{kid} (plugin not loaded)"
    return SourceKind(kid, tooltip=lambda ctx: text, inspector_line=lambda ctx: text)


def source_kind(kind: str) -> SourceKind:
    """The registered kind, or a stand-in naming it when the plugin that provides it is not loaded."""
    kid = canonical_id(kind)
    return SOURCE_KINDS.get(kid) if kid in SOURCE_KINDS else _missing(kid)


def _path(parts) -> str:
    from SciQLop.core.snippets import format_product_path
    return format_product_path(parts) if parts else ""


def _callback(ctx: GraphContext) -> str:
    return f"{ctx.callback_module}.{ctx.callback_qualname}".strip(".")


def _speasy_path(ctx: GraphContext) -> str:
    return _path(ctx.product_path) or (ctx.speasy_id or "")


def _vp_path(ctx: GraphContext) -> str:
    return _path(ctx.product_path) or (_path(ctx.vp_path.split("/")) if ctx.vp_path else "")


def _provider_path(ctx: GraphContext) -> str:
    return _path(ctx.product_path)


_CORE = (
    SourceKind(SPEASY, lambda c: f"{c.speasy_id} — Speasy", lambda c: f"Speasy: {c.speasy_id}", _speasy_path,
               shareable=True),
    SourceKind(VP, lambda c: f"{c.vp_path} — Virtual", lambda c: f"Virtual: {c.vp_path}", _vp_path),
    SourceKind(FUNCTION, lambda c: f"function {_callback(c)}", lambda c: f"Function: {_callback(c)}"),
    SourceKind(STATIC, lambda c: "static data", lambda c: "Static data"),
    SourceKind(PROVIDER, lambda c: f"{_provider_path(c) or c.graph_id} — {c.provider_name}",
               lambda c: f"{c.provider_name}: {_provider_path(c) or c.graph_id}", _provider_path),
)

for _kind in _CORE:
    SOURCE_KINDS.contribute(_kind, owner="sciqlop")
