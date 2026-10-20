"""Compare a plot panel with itself across events, products or settings.

>>> from SciQLop.user_api.comparison import compare
>>> h = compare(panel, over="time", variants=[event_a, event_b])
>>> h.view = "difference"
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, List, Optional, Tuple

from PySide6.QtWidgets import QWidget

from SciQLop.components.comparison.backend.dimensions import COMPARISON_DIMENSIONS, resolve_sides
from SciQLop.components.comparison.backend.model import Comparison, GraphSpec, Variant, base_specs
from SciQLop.components.comparison.backend.views import check_view, find_view, options_for, showing, with_options
from SciQLop.components.comparison.ui.panel_kind import COMPARISON_PANEL
from SciQLop.components.comparison.ui.pickers import is_spectrogram, knobs_label, product_node
from SciQLop.components.plotting.panel_template import PanelTemplate
from SciQLop.core import as_time_range
from .gui import get_main_window as _get_main_window
from .plot._thread_safety import GuardedImpl
from .threading import on_main_thread

__all__ = ["compare", "ComparisonHandle"]

Target = Optional[Tuple[int, int]]


def _iso_minutes(t: float) -> str:
    return datetime.fromtimestamp(t, tz=timezone.utc).isoformat(timespec="minutes")


def _time_pair(value) -> Any:
    """A speasy Event or a CatalogEvent as a (start, stop) pair; anything else as given."""
    if hasattr(value, "start_time"):
        return value.start_time, value.stop_time
    if isinstance(getattr(value, "start", None), datetime):
        return value.start, value.stop
    return value


def _time_variant(value) -> Variant:
    try:
        rng = as_time_range(_time_pair(value))
    except TypeError as e:
        raise ValueError(f"not a time variant: {value!r} ({e})") from e
    return Variant(label=_iso_minutes(rng.start()), params={"start": rng.start(), "stop": rng.stop()})


def _target_spec(specs: List[GraphSpec], target: Target) -> GraphSpec:
    if not specs:
        raise ValueError("the base panel has no product graph to change")
    if target is None:
        return specs[0]
    found = next((s for s in specs if s.key == tuple(target)), None)
    if found is None:
        raise ValueError(f"no product graph at target {tuple(target)}; the base has {[s.key for s in specs]}")
    return found


def _product_variant(value, specs: List[GraphSpec], target: Target) -> Variant:
    from .plot._plots import to_product_path
    path = "//".join(to_product_path(value))
    node = product_node(path) if path else None
    if node is None:
        raise ValueError(f"{value!r} is not in the products tree")
    spec = _target_spec(specs, target)
    colormap = is_spectrogram(node)
    return Variant(label=path.split("//")[-1], params={
        "target": list(spec.key), "path": path, "is_colormap": spec.is_colormap if colormap is None else colormap})


def _settings_variant(value, specs: List[GraphSpec], target: Target) -> Variant:
    if not isinstance(value, dict):
        raise ValueError(f"a settings variant is a dict of knob values, got {type(value).__name__}")
    spec = _target_spec(specs, target)
    return Variant(label=knobs_label(value), params={"target": list(spec.key), "knobs": dict(value)})


def _plain_variant(value, specs: List[GraphSpec], target: Target) -> Variant:
    if not isinstance(value, dict):
        raise ValueError(f"give this dimension's variants as dicts of parameters, got {type(value).__name__}")
    return Variant(label=knobs_label(value), params=dict(value))


_VARIANT_BUILDERS: dict[str, Callable[[Any, List[GraphSpec], Target], Variant]] = {
    "time": lambda value, specs, target: _time_variant(value),
    "product": _product_variant,
    "settings": _settings_variant,
}


def _variant(over: str, value, specs: List[GraphSpec], target: Target) -> Variant:
    if isinstance(value, Variant):
        return value
    return _VARIANT_BUILDERS.get(over, _plain_variant)(value, specs, target)


def _check_dimension(over: str) -> None:
    if COMPARISON_DIMENSIONS.find(over) is None:
        registered = ", ".join(COMPARISON_DIMENSIONS.keys())
        raise ValueError(f"unknown comparison dimension {over!r}; registered: {registered}")


def _base_template(panel) -> PanelTemplate:
    if isinstance(panel, str):
        impl = _get_main_window().plot_panel(panel)
        if impl is None:
            raise ValueError(f"no plot panel named {panel!r}")
        panel = impl
    elif hasattr(panel, "_get_impl_or_raise"):
        panel = panel._get_impl_or_raise()
    return PanelTemplate.from_panel(panel)


def _labelled(variants: List[Variant], labels: Optional[List[str]]) -> List[Variant]:
    if labels is None:
        return variants
    if len(labels) != len(variants):
        raise ValueError(f"got {len(labels)} labels for {len(variants)} variants")
    return [v.model_copy(update={"label": str(label)}) for v, label in zip(variants, labels)]


class ComparisonHandle(GuardedImpl):
    """A Comparison panel opened by :func:`compare`."""

    def __init__(self, impl: QWidget):
        self._impl = impl
        self._impl.destroyed.connect(self._on_destroyed)

    def _on_destroyed(self):
        self._impl = None

    def _get_impl_or_raise(self):
        if self._impl is None:
            raise ValueError("The comparison panel does not exist anymore.")
        return self._impl

    def _comparison(self) -> Comparison:
        return self._get_impl_or_raise().comparison

    @property
    @on_main_thread
    def name(self) -> str:
        """The comparison panel's name."""
        return self._get_impl_or_raise().objectName()

    @property
    def panel(self) -> QWidget:
        """The comparison panel widget; off the GUI thread, a proxy that runs every call on it."""
        return self._get_impl_or_raise()

    @property
    @on_main_thread
    def view(self) -> str:
        """The id of the view drawn: ``"overlay"``, ``"difference"`` or a plugin's.

        Setting a view that cannot show these sides raises ``ValueError`` with the reason."""
        return self._comparison().view

    @view.setter
    @on_main_thread
    def view(self, view_id: str) -> None:
        check_view(self._comparison(), view_id)
        self._get_impl_or_raise().set_view(view_id)

    @property
    @on_main_thread
    def variants(self) -> List[str]:
        """The labels of the variants compared with the base panel."""
        return [v.label for v in self._comparison().variants]

    @on_main_thread
    def options(self, view: Optional[str] = None) -> dict:
        """The options of a view (the current one by default), defaults included."""
        return options_for(self._comparison(), find_view(view or self._comparison().view))

    @on_main_thread
    def set_options(self, view: str, **values) -> None:
        """Set options of a view, e.g. ``set_options("difference", operation="ratio")``.

        Raises ``ValueError`` for an unknown option or a value outside its choices."""
        self._get_impl_or_raise().set_comparison(with_options(self._comparison(), view, values))

    @on_main_thread
    def show(self, view: str, **options) -> None:
        """Switch to a view and set its options at once, e.g. ``show("difference", operation="ratio")``.

        Everything is checked first: on ``ValueError`` nothing changes."""
        self._get_impl_or_raise().set_comparison(showing(self._comparison(), view, options))


@on_main_thread
def compare(panel, *, over: str, variants: list, view: str = "overlay", labels: Optional[List[str]] = None,
            target: Target = None) -> ComparisonHandle:
    """Open a Comparison panel showing a plot panel next to variants of itself.

    Parameters
    ----------
    panel : PlotPanel or str
        The base panel, or its name. Its current content and time range are copied: closing it later
        leaves the comparison unchanged.
    over : str
        What changes: ``"time"``, ``"product"``, ``"settings"`` or a plugin's dimension id.
    variants : list
        What to compare with. ``time``: speasy ``Event``, catalog events, ``TimeRange`` or ``(start, stop)``
        pairs of datetimes, date strings or epoch seconds. ``product``: product paths or ``VirtualProduct``.
        ``settings``: dicts of knob values. Other dimensions: dicts of their parameters.
    view : str
        The view drawn first, ``"overlay"`` by default.
    labels : list of str, optional
        One label per variant, replacing the generated ones.
    target : (int, int), optional
        ``(plot_index, product_index)`` of the graph a product or settings variant changes; the first product
        graph of the base panel by default.

    Returns
    -------
    ComparisonHandle

    Raises
    ------
    ValueError
        Unknown dimension or view, no variants, an invalid variant, or a view that cannot show these sides.
    """
    _check_dimension(over)
    if not variants:
        raise ValueError("compare needs at least one variant")
    template = _base_template(panel)
    specs = base_specs(template)
    built = _labelled([_variant(over, v, specs, target) for v in variants], labels)
    for v in built:
        COMPARISON_DIMENSIONS.get(over).validate(v.params)
    comparison = Comparison(base=template.to_tree(), dimension=over, variants=built, view=view)
    check_view(comparison, view)
    return ComparisonHandle(_get_main_window().open_panel(COMPARISON_PANEL, **comparison.model_dump(mode="json")))
