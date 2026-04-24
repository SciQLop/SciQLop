"""Manages C++ annotation items on a SciQLopPlot for a single layer."""
import numpy as np
from typing import Optional

from PySide6.QtGui import QColor
from SciQLopPlots import (SciQLopVerticalSpan, SciQLopPlotRange,
                          SciQLopHorizontalLine, GraphType)

from SciQLop.user_api.layers.types import Marker, Span, HLine, Annotation
from SciQLop.components.sciqlop_logging import getLogger as _getLogger

log = _getLogger(__name__)

_DEFAULT_SPAN_ALPHA = 60
_DEFAULT_MARKER_COLOR = "#e74c3c"
_DEFAULT_SPAN_COLOR = "#3498db"
_DEFAULT_HLINE_COLOR = "#2ecc71"


def _partition(items: list[Annotation]) -> dict[str, list]:
    groups: dict[str, list] = {"marker": [], "span": [], "hline": []}
    for item in items:
        if isinstance(item, Marker):
            groups["marker"].append(item)
        elif isinstance(item, Span):
            groups["span"].append(item)
        elif isinstance(item, HLine):
            groups["hline"].append(item)
    return groups


def _parse_color(color_str: Optional[str], default: str, alpha: int = 255):
    c = QColor(color_str or default)
    if alpha < 255:
        c.setAlpha(alpha)
    return c


class LayerRenderer:

    def __init__(self, plot, callback, knob_state=None):
        self._plot = plot
        self._callback = callback
        self._knob_state = knob_state
        self._spans: list = []
        self._hlines: list = []
        self._marker_graph = None

    def update(self, start: float, stop: float):
        knobs = self._knob_state.values if self._knob_state is not None else {}
        try:
            items = self._callback(start, stop, **knobs)
        except Exception:
            log.error("layer callback failed", exc_info=True)
            items = []
        self._render(items or [])

    def _render(self, items: list[Annotation]):
        groups = _partition(items)
        self._render_spans(groups["span"])
        self._render_hlines(groups["hline"])
        self._render_markers(groups["marker"])

    def _render_spans(self, spans: list[Span]):
        for old in self._spans:
            old.deleteLater()
        self._spans.clear()
        for s in spans:
            vs = SciQLopVerticalSpan(self._plot, SciQLopPlotRange(s.start, s.stop))
            vs.set_color(_parse_color(s.color, _DEFAULT_SPAN_COLOR, _DEFAULT_SPAN_ALPHA))
            vs.set_read_only(True)
            if s.label:
                vs.set_tool_tip(s.label)
            self._spans.append(vs)

    def _render_hlines(self, hlines: list[HLine]):
        for old in self._hlines:
            old.deleteLater()
        self._hlines.clear()
        for h in hlines:
            hl = SciQLopHorizontalLine(self._plot, h.value)
            hl.set_color(_parse_color(h.color, _DEFAULT_HLINE_COLOR))
            self._hlines.append(hl)

    def _render_markers(self, markers: list[Marker]):
        if not markers:
            if self._marker_graph is not None:
                self._marker_graph.set_data(
                    np.empty(0, dtype=np.float64),
                    np.empty(0, dtype=np.float64),
                )
            return
        times = np.array([m.time for m in markers], dtype=np.float64)
        values = np.array([m.value for m in markers], dtype=np.float64)
        if self._marker_graph is None:
            self._marker_graph = self._create_marker_graph()
        if self._marker_graph is not None:
            self._marker_graph.set_data(times, values)

    def _create_marker_graph(self):
        try:
            return self._plot.plot(
                np.empty(0, dtype=np.float64),
                np.empty(0, dtype=np.float64),
                graph_type=GraphType.Scatter,
                name="layer_markers",
            )
        except Exception:
            log.warning("scatter graph creation failed, falling back to line graph")
            try:
                return self._plot.plot(
                    np.empty(0, dtype=np.float64),
                    np.empty(0, dtype=np.float64),
                    name="layer_markers",
                )
            except Exception:
                log.error("marker graph creation failed entirely", exc_info=True)
                return None

    def clear(self):
        for s in self._spans:
            s.deleteLater()
        self._spans.clear()
        for h in self._hlines:
            h.deleteLater()
        self._hlines.clear()
        if self._marker_graph is not None:
            self._marker_graph.set_data(
                np.empty(0, dtype=np.float64),
                np.empty(0, dtype=np.float64),
            )
