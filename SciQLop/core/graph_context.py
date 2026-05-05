"""Per-graph metadata envelope. See docs/plans/2026-05-05-graph-context-metadata.md."""
from __future__ import annotations

import importlib
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
