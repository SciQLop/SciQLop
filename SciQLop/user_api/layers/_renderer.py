"""Manages C++ annotation items on a SciQLopPlot for a single layer."""
import numpy as np
from typing import Optional

from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QColor, QPen
from SciQLopPlots import (SciQLopVerticalSpan, SciQLopPlotRange,
                          SciQLopHorizontalLine, GraphMarkerShape,
                          SciQLopGraphInterface, SciQLopColorMapInterface)

from SciQLop.user_api.layers.types import Marker, Span, HLine, Annotation
from SciQLop.user_api.layers._introspection import DataTypeInfo
from SciQLop.user_api.data_types import wrap_graph_data, data_class_for_product_type
from SciQLop.components.sciqlop_logging import getLogger as _getLogger

log = _getLogger(__name__)

_DEFAULT_SPAN_ALPHA = 60
_DEFAULT_MARKER_COLOR = "#e74c3c"
_DEFAULT_SPAN_COLOR = "#3498db"
_DEFAULT_HLINE_COLOR = "#2ecc71"

_VP_TYPE_MATCHERS = {
    "scalar": lambda p: isinstance(p, SciQLopGraphInterface) and len(p.components()) == 1,
    # >= 3: real vector products often carry an extra magnitude column (e.g. Bx,By,Bz,|B|)
    "vector": lambda p: isinstance(p, SciQLopGraphInterface) and len(p.components()) >= 3,
    "multicomponent": lambda p: isinstance(p, SciQLopGraphInterface) and len(p.components()) > 1,
    "spectrogram": lambda p: isinstance(p, SciQLopColorMapInterface),
    "any": lambda p: True,
}


def _find_data_source(plot, type_info: DataTypeInfo, exclude=None):
    matcher = _VP_TYPE_MATCHERS.get(type_info.product_type, _VP_TYPE_MATCHERS["any"])
    for p in plot.plottables():
        if p is exclude:
            continue
        if matcher(p):
            return p
    return None


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


class LayerRenderer(QObject):

    def __init__(self, plot, callback, knob_state=None, data_type=None, parent=None):
        super().__init__(parent or plot)
        self._plot = plot
        self._callback = callback
        self._knob_state = knob_state
        self._data_type: Optional[DataTypeInfo] = data_type
        self._data_source = None
        self._data_connection = None
        self._pending_connections: list = []
        self._graph_list_connection = None
        self._spans: list = []
        self._hlines: list = []
        self._marker_graph = None

    @property
    def data_aware(self) -> bool:
        return self._data_type is not None

    def setup_data_binding(self):
        if not self.data_aware:
            return
        if self._try_bind():
            return
        log.info("No matching %s graph yet — watching for new graphs and data arrivals",
                 self._data_type.product_type)
        self._graph_list_connection = self._plot.graph_list_changed.connect(
            self._on_graph_list_changed)
        self._watch_existing_plottables()

    def _watch_existing_plottables(self):
        for p in self._plot.plottables():
            if hasattr(p, "data_changed"):
                p.data_changed.connect(self._on_pending_data_changed)
                self._pending_connections.append(p)

    def _on_pending_data_changed(self, *_args):
        self._deferred_try_bind()

    def _clear_pending_connections(self):
        for plottable in self._pending_connections:
            try:
                plottable.data_changed.disconnect(self._on_pending_data_changed)
            except (RuntimeError, TypeError):
                pass
        self._pending_connections.clear()

    def _on_graph_list_changed(self):
        if self._data_source is not None:
            return
        QTimer.singleShot(0, self._deferred_try_bind)

    def _deferred_try_bind(self):
        if self._data_source is not None:
            return
        if self._try_bind():
            self._disconnect_watchers()
            current_range = self._plot.x_axis().range()
            self.update(current_range.start(), current_range.stop())

    def _disconnect_watchers(self):
        if self._graph_list_connection is not None:
            self._plot.graph_list_changed.disconnect(self._on_graph_list_changed)
            self._graph_list_connection = None
        self._clear_pending_connections()

    def _try_bind(self) -> bool:
        source = _find_data_source(
            self._plot, self._data_type, exclude=self._marker_graph)
        if source is None:
            return False
        self._data_source = source
        self._data_connection = source.data_changed.connect(
            lambda *_: self._on_data_changed())
        return True

    def _on_data_changed(self):
        current_range = self._plot.x_axis().range()
        self.update(current_range.start(), current_range.stop())

    def update(self, start: float, stop: float):
        knobs = self._knob_state.values if self._knob_state is not None else {}
        try:
            if self.data_aware:
                if self._data_source is None:
                    self._render([])
                    return
                raw = self._data_source.data()
                cls = data_class_for_product_type(self._data_type.product_type)
                data = wrap_graph_data(raw, cls)
                if data is None:
                    self._render([])
                    return
                items = self._callback(data=data, **knobs)
            else:
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
            graph = self._plot.scatter(
                np.empty(0, dtype=np.float64),
                np.empty(0, dtype=np.float64),
                marker=GraphMarkerShape.FilledCircle,
            )
            for comp in graph.components():
                comp.set_marker_pen(QPen(comp.color(), 1.5))
            return graph
        except Exception:
            log.error("scatter graph creation failed", exc_info=True)
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
