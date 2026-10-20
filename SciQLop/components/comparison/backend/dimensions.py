"""Dimensions of a comparison: the one thing that differs between the sides (sciqlop.comparison_dimensions)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from SciQLop.components.comparison.backend.model import Anchor, Comparison, GraphSpec, Side, Variant, sides
from SciQLop.core.extensions import ExtensionPoint, declare


@dataclass(frozen=True)
class ComparisonDimension:
    id: str
    label: str
    noun: str
    apply: Callable[[list[GraphSpec], Variant, Comparison], Side]
    validate: Callable[[dict], None]
    base_side: Callable[[list[GraphSpec], Comparison], Side]


COMPARISON_DIMENSIONS = declare(ExtensionPoint(
    "sciqlop.comparison_dimensions", ComparisonDimension, what="comparison dimension",
    doc="Kinds of change a comparison can show: each turns a variant into a side."))

ANCHOR_LABELS = {"start": "start", "center": "centre", "end": "end"}


def anchor_time(start: float, stop: float, anchor: Anchor) -> float:
    return {"start": start, "center": (start + stop) / 2, "end": stop}[anchor]


def base_range(comparison: Comparison) -> tuple[float, float]:
    rng = comparison.template().time_range
    if rng is None:
        raise ValueError("the base panel has no visible time range yet")
    return datetime.fromisoformat(rng.start).timestamp(), datetime.fromisoformat(rng.stop).timestamp()


def _require(params: dict, *keys: str) -> None:
    for key in keys:
        if key not in params:
            raise ValueError(f"missing {key!r}")


def _replace_target(specs: list[GraphSpec], params: dict, change: Callable[[GraphSpec], dict]) -> list[GraphSpec]:
    target = tuple(params["target"])
    return [s.model_copy(update=change(s)) if s.key == target else s for s in specs]


def validate_time(params: dict) -> None:
    _require(params, "start", "stop")
    if params["stop"] <= params["start"]:
        raise ValueError("stop must be after start")


def apply_time(specs: list[GraphSpec], variant: Variant, comparison: Comparison) -> Side:
    start, stop = variant.params["start"], variant.params["stop"]
    t0 = anchor_time(start, stop, comparison.anchor)
    offset = t0 - anchor_time(*base_range(comparison), comparison.anchor)
    return Side(label=variant.label, specs=[s.model_copy(update={"time_offset": s.time_offset + offset})
                                            for s in specs],
                t0=t0, duration=stop - start)


def base_time_side(specs: list[GraphSpec], comparison: Comparison) -> Side:
    start, stop = base_range(comparison)
    return Side(label=comparison.template().name, specs=specs,
                t0=anchor_time(start, stop, comparison.anchor), duration=stop - start)


def validate_product(params: dict) -> None:
    _require(params, "target", "path")


def apply_product(specs: list[GraphSpec], variant: Variant, comparison: Comparison) -> Side:
    params = variant.params
    new = _replace_target(specs, params, lambda s: {
        "path": params["path"], "is_colormap": params.get("is_colormap", s.is_colormap)})
    return Side(label=variant.label, specs=new)


def validate_settings(params: dict) -> None:
    _require(params, "target", "knobs")


def apply_settings(specs: list[GraphSpec], variant: Variant, comparison: Comparison) -> Side:
    params = variant.params
    new = _replace_target(specs, params, lambda s: {"knobs": {**s.knobs, **params["knobs"]}})
    return Side(label=variant.label, specs=new)


def base_plain_side(specs: list[GraphSpec], comparison: Comparison) -> Side:
    return Side(label=comparison.template().name, specs=specs)


CORE_DIMENSIONS = [
    ComparisonDimension("time", "Time", "events", apply_time, validate_time, base_time_side),
    ComparisonDimension("product", "Product", "products", apply_product, validate_product, base_plain_side),
    ComparisonDimension("settings", "Settings", "settings", apply_settings, validate_settings, base_plain_side),
]


def contribute_core_dimensions() -> None:
    for d in CORE_DIMENSIONS:
        COMPARISON_DIMENSIONS.contribute(d, owner="sciqlop", replace=True)


def dimension(id: str) -> ComparisonDimension:
    return COMPARISON_DIMENSIONS.get(id)


def resolve_sides(comparison: Comparison) -> list[Side]:
    d = dimension(comparison.dimension)
    return sides(comparison, d.base_side, d.apply)
