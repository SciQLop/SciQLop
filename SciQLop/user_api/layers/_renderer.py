"""Manages C++ annotation items on a SciQLopPlot for a single layer."""
import numpy as np
import re
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QColor, QPen
from SciQLopPlots import (SciQLopVerticalSpan, SciQLopPlotRange,
                          SciQLopHorizontalLine, GraphMarkerShape,
                          SciQLopGraphInterface, SciQLopColorMapInterface,
                          MultiPlotsVerticalSpan, SciQLopMultiPlotPanel)

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


def _find_panel(plot) -> Optional["SciQLopMultiPlotPanel"]:
    node = plot
    while node is not None:
        if isinstance(node, SciQLopMultiPlotPanel):
            return node
        try:
            node = node.parent()
        except RuntimeError:
            return None
    return None


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


_CSS_RGB = re.compile(
    r"^\s*rgba?\(\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)\s*"
    r"(?:,\s*([0-9.]+)\s*)?\)\s*$", re.IGNORECASE)


def _css_rgb(text: str) -> Optional[QColor]:
    """QColor from a CSS ``rgb()``/``rgba()`` string, or None if it is not one.

    QColor does not accept these: it returns an *invalid* colour, which paints
    nothing, so the annotation simply vanishes with no error anywhere.
    """
    m = _CSS_RGB.match(text)
    if not m:
        return None
    r, g, b, a = m.groups()
    c = QColor(int(float(r)), int(float(g)), int(float(b)))
    if a is not None:
        # CSS writes alpha 0..1; accept 0..255 too, since Qt users reach for it
        av = float(a)
        c.setAlpha(round(av * 255) if av <= 1.0 else round(av))
    return c


def _parse_color(color_str: Optional[str], default: str, alpha: int = 255):
    """Colour from a Qt name, ``#RRGGBB``/``#AARRGGBB``, or CSS ``rgb()``/``rgba()``.

    ``alpha`` is a *default*: a colour that carries its own opacity keeps it.
    An unparseable string falls back to ``default`` and says so, rather than
    painting nothing.
    """
    text = (color_str or default).strip()
    c = _css_rgb(text)
    carries_alpha = c is not None and c.alpha() < 255
    if c is None:
        c = QColor(text)
        # #AARRGGBB is the Qt spelling for an explicit alpha
        carries_alpha = c.isValid() and len(text) == 9 and text.startswith("#")
    if not c.isValid():
        log.warning("layer: unrecognised colour %r, falling back to %r",
                    color_str, default)
        c = QColor(default)
        carries_alpha = False
    if alpha < 255 and not carries_alpha:
        c.setAlpha(alpha)
    return c


def _callback_name(callback) -> str:
    inner = getattr(callback, "callback", callback)   # unwrap MutableCallback
    return getattr(inner, "__qualname__", None) or getattr(inner, "__name__", repr(inner))


class LayerRenderer(QObject):

    #: Emitted with "<callback>: <error>" when a layer callback raises. The
    #: plot cannot show the exception itself, so this is how a caller or a UI
    #: can tell a failure from a layer that legitimately found nothing.
    callback_failed = Signal(str)

    def __init__(self, plot, callback, knob_state=None, data_type=None,
                 scope: str = "plot", panel=None, parent=None):
        super().__init__(parent or plot)
        self._plot = plot
        self._callback = callback
        self._knob_state = knob_state
        self._data_type: Optional[DataTypeInfo] = data_type
        self._scope = scope
        self._panel = panel if panel is not None else _find_panel(plot)
        if self._scope == "panel" and self._panel is None:
            log.debug("scope=panel but no panel found in parent chain; falling back to plot-scoped spans")
            self._scope = "plot"
        self._data_source = None
        self._data_slot = None
        self._pending_connections: list = []
        self._graph_list_connection = None
        self._range_slot = None
        self._knobs_slot = None
        self._spans: list = []
        self._hlines: list = []
        self._marker_graph = None
        self._disposed = False
        self._last_error: Optional[BaseException] = None

    @property
    def last_error(self) -> Optional[BaseException]:
        """What the last callback invocation raised, or None if it succeeded."""
        return self._last_error

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
            try:
                self._plot.graph_list_changed.disconnect(self._on_graph_list_changed)
            except (RuntimeError, TypeError):
                pass
            self._graph_list_connection = None
        self._clear_pending_connections()

    def _try_bind(self) -> bool:
        source = _find_data_source(
            self._plot, self._data_type, exclude=self._marker_graph)
        if source is None:
            return False
        self._data_source = source
        self._data_slot = lambda *_: self._on_data_changed()
        source.data_changed.connect(self._data_slot)
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
        except Exception as error:
            # Rendering [] here is why a broken detector reads as "no events
            # found": the failure and the empty result look identical on the
            # plot. Keep the plot consistent, but record it and say which
            # callback it was, so the difference is recoverable.
            self._last_error = error
            log.error("layer callback %s failed", _callback_name(self._callback),
                      exc_info=True)
            self.callback_failed.emit(f"{_callback_name(self._callback)}: {error}")
            self._render([])
            return
        self._last_error = None
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
            color = _parse_color(s.color, _DEFAULT_SPAN_COLOR, _DEFAULT_SPAN_ALPHA)
            label = s.label or ""
            if self._scope == "panel":
                vs = MultiPlotsVerticalSpan(
                    self._panel, SciQLopPlotRange(s.start, s.stop),
                    color, True, True, label,
                )
            else:
                vs = SciQLopVerticalSpan(self._plot, SciQLopPlotRange(s.start, s.stop))
                vs.set_color(color)
                vs.set_read_only(True)
                if label:
                    vs.set_tool_tip(label)
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

    def dispose(self):
        """Tear down all visual items and signal connections.

        Idempotent. After dispose(), no further updates will fire and the
        renderer schedules its own deletion.

        Note
        ----
        ``ext.destroyed`` fires while the parent plot is mid ~QWidget
        (its child InspectorExtensions are being deleted by ~QObject's
        deleteChildren). Going through ``self._plot.x_axis()`` then
        segfaults inside ``QWidget::sharedPainter()``. We use the
        ``_x_axis`` reference cached at connect time so we never hit
        the wrapper during teardown, and only attempt the disconnect at
        all when a ``range_changed`` slot was actually connected
        (data-aware layers don't connect it).
        """
        if self._disposed:
            return
        self._disposed = True
        self._disconnect_watchers()
        self._safe_disconnect(self._data_source, "data_changed", self._data_slot)
        self._data_slot = None
        if self._range_slot is not None:
            self._safe_disconnect(getattr(self, "_x_axis", None),
                                  "range_changed", self._range_slot)
            self._range_slot = None
        if self._knob_state is not None:
            self._safe_disconnect(self._knob_state, "knobs_changed", self._knobs_slot)
            self._knobs_slot = None
        self.clear()
        if self._marker_graph is not None:
            try:
                self._marker_graph.deleteLater()
            except RuntimeError:
                pass
            self._marker_graph = None
        self.deleteLater()

    @staticmethod
    def _safe_disconnect(emitter, signal_name, slot):
        if emitter is None or slot is None:
            return
        try:
            getattr(emitter, signal_name).disconnect(slot)
        except (RuntimeError, TypeError):
            pass
