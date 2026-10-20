"""Views of a comparison: how its sides are drawn (sciqlop.comparison_views)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

from SciQLop.components.comparison.backend.dimensions import resolve_sides
from SciQLop.components.comparison.backend.model import Comparison, Side
from SciQLop.core.extensions import ExtensionPoint, declare

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


@dataclass(frozen=True)
class ComparisonView:
    id: str
    label: str
    applies: Callable[[Comparison, list[Side]], str | None]
    build: Callable[[Comparison, list[Side], dict, tuple[float, float] | None, QWidget], QWidget]
    default_options: dict = field(default_factory=dict)
    option_choices: dict[str, tuple[str, ...]] = field(default_factory=dict)  # option key -> its choices in the header
    choice_labels: dict[str, str] = field(default_factory=dict)  # choice -> the text the header shows for it
    order: int = 0


COMPARISON_VIEWS = declare(ExtensionPoint(
    "sciqlop.comparison_views", ComparisonView, what="comparison view",
    doc="Renderers of a comparison's sides, such as overlay or difference."))


def available_views(comparison: Comparison, sides: list[Side]) -> list[tuple[ComparisonView, str | None]]:
    views = sorted(COMPARISON_VIEWS.list(), key=lambda v: (v.order, v.id))
    return [(v, v.applies(comparison, sides)) for v in views]


def options_for(comparison: Comparison, view: ComparisonView) -> dict:
    return {**view.default_options, **comparison.view_options.get(view.id, {})}


def find_view(view_id: str) -> ComparisonView:
    view = COMPARISON_VIEWS.find(view_id)
    if view is None:
        raise ValueError(f"unknown comparison view {view_id!r}; installed: {', '.join(COMPARISON_VIEWS.keys())}")
    return view


def check_view(comparison: Comparison, view_id: str) -> None:
    reason = find_view(view_id).applies(comparison, resolve_sides(comparison))
    if reason is not None:
        raise ValueError(f"cannot show {view_id!r}: {reason}")


def _checked_options(view: ComparisonView, values: dict) -> dict:
    known = {**view.default_options, **view.option_choices}
    for key, value in values.items():
        if key not in known:
            raise ValueError(f"{view.id!r} has no option {key!r}; options: {', '.join(known)}")
        choices = view.option_choices.get(key)
        if choices is not None and value not in choices:
            raise ValueError(f"{key!r} must be one of {', '.join(choices)}, got {value!r}")
    return values


def with_options(comparison: Comparison, view_id: str, values: dict) -> Comparison:
    view = find_view(view_id)
    checked = _checked_options(view, values)
    current = comparison.view_options.get(view.id, {})
    return comparison.model_copy(update={"view_options": {**comparison.view_options, view.id: {**current, **checked}}})


def showing(comparison: Comparison, view_id: str, options: dict) -> Comparison:
    """The comparison switched to a view with these options; ValueError, before any change, when it cannot."""
    updated = with_options(comparison, view_id, options).model_copy(update={"view": view_id})
    check_view(updated, view_id)
    return updated
