"""Creates interactive plot items (VSpan, HLine) for visual knobs and
wires them bidirectionally with GraphKnobState."""

from PySide6.QtGui import QColor
from SciQLopPlots import (
    SciQLopVerticalSpan, SciQLopHorizontalLine, SciQLopPlotRange,
    Coordinates,
)

from SciQLop.user_api.knobs.specs import TimeRangeKnob, ThresholdKnob
from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
from SciQLop.components import sciqlop_logging

log = sciqlop_logging.getLogger(__name__)

_DEFAULT_SPAN_ALPHA = 80


class _DataSpan:
    """VSpan in data coordinates, synced with a TimeRangeKnob.

    A fractional default like (0.3, 0.7) is interpreted as fractions of the
    visible axis range. Because the plot's axis range is often set AFTER the
    knob is created (e.g. `%%vp --debug` builds the subplot first, then sets
    the panel's time range), fractional defaults are re-resolved on every
    axis range change UNTIL the user drags the span — which locks it in
    data coords."""

    def __init__(self, plot, spec: TimeRangeKnob, state: GraphKnobState):
        self._plot = plot
        self._spec = spec
        self._state = state
        self._reentry = False
        self._user_locked = False
        self._fractional_default = self._is_fractional(spec.default)

        color = QColor(spec.color)
        color.setAlpha(_DEFAULT_SPAN_ALPHA)
        initial = self._resolve_default(plot, spec.default)
        self._span = SciQLopVerticalSpan(
            plot, initial, color, False, True, spec.label or spec.name,
            Coordinates.Data,
        )

        self._state.set_value(spec.name, initial)
        self._span.range_changed.connect(self._on_span_dragged)
        if self._fractional_default:
            plot.x_axis().range_changed.connect(self._on_axis_changed)

    @staticmethod
    def _is_fractional(r: SciQLopPlotRange) -> bool:
        lo, hi = r.start(), r.stop()
        return 0.0 <= lo <= 1.0 and 0.0 <= hi <= 1.0

    @classmethod
    def _resolve_default(cls, plot, default: SciQLopPlotRange) -> SciQLopPlotRange:
        if not cls._is_fractional(default):
            return default
        axis = plot.x_axis().range()
        lo, hi = axis.start(), axis.stop()
        lo_frac, hi_frac = default.start(), default.stop()
        return SciQLopPlotRange(
            lo + lo_frac * (hi - lo),
            lo + hi_frac * (hi - lo),
        )

    def _on_axis_changed(self, new_range: SciQLopPlotRange):
        if self._user_locked or self._reentry:
            return
        lo, hi = new_range.start(), new_range.stop()
        if hi <= lo:
            return
        lo_frac, hi_frac = self._spec.default.start(), self._spec.default.stop()
        resolved = SciQLopPlotRange(
            lo + lo_frac * (hi - lo),
            lo + hi_frac * (hi - lo),
        )
        self._reentry = True
        try:
            self._span.set_range(resolved)
            self._state.set_value(self._spec.name, resolved)
        finally:
            self._reentry = False

    def _on_span_dragged(self, new_range: SciQLopPlotRange):
        if self._reentry:
            return
        self._user_locked = True
        self._reentry = True
        try:
            self._state.set_value(self._spec.name, new_range)
        finally:
            self._reentry = False

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


def create_plot_items(plot, state: GraphKnobState):
    """Scan specs for visual knobs, create plot items, wire bidirectional sync.
    Returns a list of items (for lifecycle management)."""
    items = []
    for spec in state.specs:
        if isinstance(spec, TimeRangeKnob):
            items.append(_DataSpan(plot, spec, state))
        elif isinstance(spec, ThresholdKnob):
            items.append(_MovableHLine(plot, spec, state))

    if items:
        def _on_state_changed(values):
            for item in items:
                item.update_from_state(values)
        state.knobs_changed.connect(_on_state_changed)

    return items
