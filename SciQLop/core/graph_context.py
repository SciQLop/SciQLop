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

    def to_meta_data(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


@dataclass(slots=True)
class GraphRichRefs:
    """Python-only references that can't go in the C++ meta_data slot."""
    callback: Optional[Callable] = None
    knobs_model: Optional[type] = None
