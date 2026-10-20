"""Pure data model of a plot comparison: a base panel snapshot, the one dimension
that changes, and the variants; views render the resulting sides."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Literal, Optional

from pydantic import BaseModel

from SciQLop.components.plotting.panel_template import PanelTemplate, TIMESERIES, TimeRangeModel

Anchor = Literal["start", "center", "end"]
Key = tuple[int, int]


class Variant(BaseModel):
    label: str
    params: dict[str, Any] = {}


class GraphSpec(BaseModel):
    plot_index: int
    product_index: int
    path: str
    knobs: dict[str, Any] = {}
    time_offset: float = 0.0
    is_colormap: bool = False
    y_axis: str | None = None

    @property
    def key(self) -> Key:
        return (self.plot_index, self.product_index)


class Side(BaseModel):
    label: str
    specs: list[GraphSpec]
    t0: float | None = None
    duration: float | None = None


class Comparison(BaseModel):
    base: dict
    dimension: str
    variants: list[Variant]
    view: str = "overlay"
    anchor: Anchor = "start"
    view_options: dict[str, dict] = {}

    def template(self) -> PanelTemplate:
        return PanelTemplate.from_tree(self.base)


def _iso(t: float) -> str:
    return datetime.fromtimestamp(t, tz=timezone.utc).isoformat()


def template_at_range(template: PanelTemplate, time_range: Optional[tuple[float, float]]) -> PanelTemplate:
    """The template showing `time_range` (epoch seconds) instead of its own; unchanged when None."""
    if time_range is None:
        return template
    return template.model_copy(update={"time_range": TimeRangeModel(start=_iso(time_range[0]),
                                                                    stop=_iso(time_range[1]))})


def base_specs(template: PanelTemplate) -> list[GraphSpec]:
    return [GraphSpec(plot_index=i, product_index=j, path=p.path, knobs=p.knobs, time_offset=p.time_offset,
                      is_colormap=p.is_colormap, y_axis=p.y_axis)
            for i, plot in enumerate(template.plots) if plot.kind == TIMESERIES
            for j, p in enumerate(plot.products) if p.path]


def sides(comparison: Comparison,
          base_side: Callable[[list[GraphSpec], Comparison], Side],
          apply: Callable[[list[GraphSpec], Variant, Comparison], Side]) -> list[Side]:
    specs = base_specs(comparison.template())
    return [base_side(specs, comparison)] + [apply(specs, v, comparison) for v in comparison.variants]


def changed_keys(sides: list[Side]) -> set[Key]:
    by_key = [{s.key: s for s in side.specs} for side in sides]
    keys = set().union(*by_key) if by_key else set()
    return {k for k in keys if len({m.get(k) and m[k].model_dump_json() for m in by_key}) > 1}
