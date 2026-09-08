from dataclasses import dataclass
from typing import Callable, Any

TargetResolver = Callable[[Any, dict], object | None]
CompletionResolver = Callable[[Any, dict], object | None]


@dataclass(frozen=True)
class TourStep:
    """One coach mark.

    `resolver(main_window, context)` returns the widget to spotlight, or a
    `(widget, local QRect)` pair to spotlight part of it. No resolver means
    a centered tip without spotlight; a step whose target is missing or
    hidden is skipped. `completion(main_window, context)` returns a Signal,
    or a `(Signal, predicate)` pair, whose firing advances the tour and
    stores the signal's payload in `context[step_id]`. Next always works.
    """
    step_id: str
    title: str
    body: str
    resolver: TargetResolver | None = None
    completion: CompletionResolver | None = None


@dataclass(frozen=True)
class Tour:
    id: str
    title: str
    description: str
    steps: list[TourStep]
