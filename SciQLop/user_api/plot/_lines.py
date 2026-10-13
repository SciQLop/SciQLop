"""One line of a graph: what the Properties panel edits per line."""
from typing import Optional

from PySide6.QtCore import Qt as _Qt
from SciQLopPlots import GraphMarkerShape as _SqpMarkerShape

from SciQLop.core.colors import to_qcolor
from .enums import GraphLineStyle, MarkerShape
from ._thread_safety import on_main_thread, _qt_property

_LINE_STYLE_TO_QT = {
    GraphLineStyle.Solid: _Qt.PenStyle.SolidLine,
    GraphLineStyle.Dash: _Qt.PenStyle.DashLine,
    GraphLineStyle.Dot: _Qt.PenStyle.DotLine,
    GraphLineStyle.DashDot: _Qt.PenStyle.DashDotLine,
    GraphLineStyle.DashDotDot: _Qt.PenStyle.DashDotDotLine,
}

_MARKER_SHAPES = {shape: getattr(_SqpMarkerShape, shape.name) for shape in MarkerShape}


def _checked(value, enum):
    if not isinstance(value, enum):
        raise TypeError(f"expected a {enum.__name__}, got {type(value).__name__}")
    return value


def _to_sqp_marker(shape):
    return _MARKER_SHAPES[_checked(shape, MarkerShape)]


def _from_sqp_marker(sqp_shape) -> Optional[MarkerShape]:
    return next((s for s, sqp in _MARKER_SHAPES.items() if sqp == sqp_shape), None)


class Line:
    """One line of a graph; a graph of a 3-component vector has three.

    Looked up by index on each access rather than held, so a handle never
    outlives the line it points to.
    """

    def __init__(self, graph, index: int):
        self._graph = graph
        self._index = index

    def _get_impl_or_raise(self):
        components = self._graph._get_impl_or_raise().components()
        if self._index >= len(components):
            raise ValueError("The line does not exist anymore.")
        return components[self._index]

    @property
    @on_main_thread
    def name(self) -> str:
        return self._get_impl_or_raise().name()

    visible = _qt_property("visible", "set_visible", to_qt=bool)
    color = _qt_property("color", "set_color", to_qt=to_qcolor)
    line_width = _qt_property("line_width", "set_line_width", to_qt=float)
    marker = _qt_property("marker_shape", "set_marker_shape", to_qt=_to_sqp_marker,
                         from_qt=_from_sqp_marker)
    marker_size = _qt_property("marker_size", "set_marker_size", to_qt=float)

    @property
    @on_main_thread
    def line_style(self) -> Optional[GraphLineStyle]:
        """The dash pattern, or ``None`` for one SciQLop has no name for."""
        style = self._get_impl_or_raise().pen().style()
        return next((s for s, qt in _LINE_STYLE_TO_QT.items() if qt == style), None)

    @line_style.setter
    @on_main_thread
    def line_style(self, style: GraphLineStyle) -> None:
        impl = self._get_impl_or_raise()
        pen = impl.pen()
        pen.setStyle(_LINE_STYLE_TO_QT[_checked(style, GraphLineStyle)])
        impl.set_pen(pen)

    @property
    @on_main_thread
    def marker_color(self):
        return self._get_impl_or_raise().marker_pen().color()

    @marker_color.setter
    @on_main_thread
    def marker_color(self, color) -> None:
        impl = self._get_impl_or_raise()
        pen = impl.marker_pen()
        pen.setColor(to_qcolor(color))
        impl.set_marker_pen(pen)

    def _repr_pretty_(self, p, cycle):
        p.text(f"Line({self._index})")


def _over_lines(name: str, doc: str):
    """A Graph property setting *name* on every line; it reads ``None`` when
    the lines differ."""

    @on_main_thread
    def fget(self):
        values = [getattr(line, name) for line in self.lines]
        return values[0] if values and all(v == values[0] for v in values) else None

    @on_main_thread
    def fset(self, value):
        for line in self.lines:
            setattr(line, name, value)

    return property(fget, fset, doc=doc)
