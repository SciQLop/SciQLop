"""Views of a comparison: how its sides are drawn (sciqlop.comparison_views)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

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
    order: int = 0


COMPARISON_VIEWS = declare(ExtensionPoint(
    "sciqlop.comparison_views", ComparisonView, what="comparison view",
    doc="Renderers of a comparison's sides, such as overlay or difference."))


def available_views(comparison: Comparison, sides: list[Side]) -> list[tuple[ComparisonView, str | None]]:
    views = sorted(COMPARISON_VIEWS.list(), key=lambda v: (v.order, v.id))
    return [(v, v.applies(comparison, sides)) for v in views]


def options_for(comparison: Comparison, view: ComparisonView) -> dict:
    return {**view.default_options, **comparison.view_options.get(view.id, {})}
