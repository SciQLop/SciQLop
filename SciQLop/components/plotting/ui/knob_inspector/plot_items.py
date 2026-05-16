"""Creates interactive plot items (VSpan, HLine) for visual knobs and
wires them bidirectionally with GraphKnobState."""

import math

from PySide6.QtGui import QColor
from SciQLopPlots import (
    SciQLopHorizontalLine, SciQLopPlotRange,
    MultiPlotsVerticalSpan, SciQLopMultiPlotPanel,
)

from SciQLop.user_api.knobs.specs import TimeRangeKnob, ThresholdKnob
from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
from SciQLop.components import sciqlop_logging

log = sciqlop_logging.getLogger(__name__)

_DEFAULT_SPAN_ALPHA = 80


def _resolve_fraction(default: SciQLopPlotRange, axis_range: SciQLopPlotRange) -> SciQLopPlotRange:
    lo, hi = axis_range.start(), axis_range.stop()
    lo_frac, hi_frac = default.start(), default.stop()
    return SciQLopPlotRange(
        lo + lo_frac * (hi - lo),
        lo + hi_frac * (hi - lo),
    )


def _is_fractional(r: SciQLopPlotRange) -> bool:
    lo, hi = r.start(), r.stop()
    return 0.0 <= lo <= 1.0 and 0.0 <= hi <= 1.0


def _is_valid_time_range(r: SciQLopPlotRange) -> bool:
    lo, hi = r.start(), r.stop()
    return not (math.isnan(lo) or math.isnan(hi)) and hi > lo


def _find_panel(plot) -> SciQLopMultiPlotPanel | None:
    node = plot
    while node is not None:
        if isinstance(node, SciQLopMultiPlotPanel):
            return node
        try:
            node = node.parent()
        except RuntimeError:
            return None
    return None


class _DataSpan:
    """Panel-wide VSpan synced with a TimeRangeKnob.

    Always rendered as a `MultiPlotsVerticalSpan` so the analysis window
    appears on every plot in the panel — the user can position it against
    ANY signal, not just the VP's own (often transformed) output. The panel
    is auto-derived from the plot's parent chain when not passed explicitly.

    For a fractional default (e.g. (0.3, 0.7)) the span is **anchored to the
    visible window**: it sits at that fraction of the panel's current time
    range and is re-resolved on every `time_range_changed` so it stays in
    view as the user pans or zooms. Dragging the span re-records the fraction
    relative to the current view, so subsequent pans preserve the user's
    placement. An absolute default is left in data coords and never moves."""

    def __init__(self, plot, spec: TimeRangeKnob, state: GraphKnobState, panel=None):
        panel = panel if panel is not None else _find_panel(plot)
        if panel is None:
            raise ValueError("TimeRangeKnob requires a SciQLopMultiPlotPanel "
                             "in the plot's parent chain")
        self._spec = spec
        self._state = state
        self._panel = panel
        self._reentry = False
        self._fraction = spec.default if _is_fractional(spec.default) else None

        color = QColor(spec.color)
        color.setAlpha(_DEFAULT_SPAN_ALPHA)
        initial = self._resolve_initial(spec.default, panel)

        self._span = MultiPlotsVerticalSpan(
            panel, initial, color, False, True, spec.label or spec.name,
        )
        self._state.set_value(spec.name, initial)
        self._span.range_changed.connect(self._on_span_dragged)

        # Cache the signal at connect time so cleanup() can disconnect without
        # going through the panel's Shiboken wrapper — cleanup runs from
        # ext.destroyed during the panel-destroy cascade, when `self._panel`
        # is mid-destruction and a wrapper call would segfault inside
        # QWidget::sharedPainter (see docs/qt-lifetime-patterns.md).
        self._panel_time_range_changed = None
        if self._fraction is not None:
            self._panel_time_range_changed = panel.time_range_changed
            self._panel_time_range_changed.connect(self._on_panel_range_changed)

    @staticmethod
    def _resolve_initial(default: SciQLopPlotRange, panel) -> SciQLopPlotRange:
        if not _is_fractional(default):
            return default
        axis = panel.time_axis_range()
        return _resolve_fraction(default, axis) if _is_valid_time_range(axis) else default

    def _on_panel_range_changed(self, new_range: SciQLopPlotRange):
        if self._reentry or self._fraction is None or not _is_valid_time_range(new_range):
            return
        resolved = _resolve_fraction(self._fraction, new_range)
        self._reentry = True
        try:
            self._span.set_range(resolved)
            self._state.set_value(self._spec.name, resolved)
        finally:
            self._reentry = False

    def _on_span_dragged(self, new_range: SciQLopPlotRange):
        if self._reentry:
            return
        if self._fraction is not None:
            self._record_fraction_from_view(new_range)
        self._reentry = True
        try:
            self._state.set_value(self._spec.name, new_range)
        finally:
            self._reentry = False

    def _record_fraction_from_view(self, span_range: SciQLopPlotRange):
        view = self._panel.time_axis_range()
        if not _is_valid_time_range(view):
            return
        vlo, vhi = view.start(), view.stop()
        size = vhi - vlo
        self._fraction = SciQLopPlotRange(
            (span_range.start() - vlo) / size,
            (span_range.stop() - vlo) / size,
        )

    def update_from_state(self, values: dict):
        if self._reentry:
            return
        value = values.get(self._spec.name)
        if value is not None and isinstance(value, SciQLopPlotRange):
            self._reentry = True
            try:
                self._span.set_range(value)
            finally:
                self._reentry = False

    def cleanup(self):
        if self._panel_time_range_changed is not None:
            try:
                self._panel_time_range_changed.disconnect(self._on_panel_range_changed)
            except (RuntimeError, TypeError):
                pass
            self._panel_time_range_changed = None
        self._span.deleteLater()


class _MovableHLine:
    """Movable horizontal line synced with a ThresholdKnob."""

    def __init__(self, plot, spec: ThresholdKnob, state: GraphKnobState):
        self._plot = plot
        self._spec = spec
        self._state = state
        self._suppress = False

        self._line = SciQLopHorizontalLine(plot, spec.default, True)
        self._line.set_color(QColor(spec.color))
        self._line.set_line_width(2.0)
        if spec.min is not None:
            self._line.set_min_value(spec.min)
        if spec.max is not None:
            self._line.set_max_value(spec.max)

        self._line.position_changed.connect(self._on_line_moved)

    def _on_line_moved(self, new_pos: float):
        self._suppress = True
        try:
            self._state.set_value(self._spec.name, new_pos)
        finally:
            self._suppress = False

    def update_from_state(self, values: dict):
        if self._suppress:
            return
        value = values.get(self._spec.name)
        if value is not None:
            self._line.set_position(float(value))

    def cleanup(self):
        self._line.deleteLater()


def create_plot_items(plot, state: GraphKnobState, panel=None):
    """Scan specs for visual knobs, create plot items, wire bidirectional sync.
    When `panel` is provided, TimeRangeKnobs become panel-wide spans visible
    on every plot in the panel. Returns a `dispose` callable that tears down
    the items AND disconnects them from `state.knobs_changed`."""
    items = []
    for spec in state.specs:
        if isinstance(spec, TimeRangeKnob):
            items.append(_DataSpan(plot, spec, state, panel=panel))
        elif isinstance(spec, ThresholdKnob):
            items.append(_MovableHLine(plot, spec, state))

    slot = None
    if items:
        def _on_state_changed(values):
            for item in items:
                item.update_from_state(values)
        slot = _on_state_changed
        state.knobs_changed.connect(slot)

    def dispose():
        if slot is not None:
            try:
                state.knobs_changed.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        for item in items:
            try:
                item.cleanup()
            except Exception:
                log.debug("plot item cleanup failed", exc_info=True)
        items.clear()

    return dispose
