from typing import Optional, Tuple, Union
from SciQLopPlots import (SciQLopPixmapItem as _SciQLopPixmapItem,
                          SciQLopEllipseItem as _SciQLopEllipseItem,
                          SciQLopTextItem as _SciQLopTextItem,
                          SciQLopCurvedLineItem as _SciQLopCurvedLineItem,
                          SciQLopHorizontalLine as _SciQLopHorizontalLine,
                          SciQLopVerticalLine as _SciQLopVerticalLine,
                          SciQLopStraightLine as _SciQLopStraightLine,
                          SciQLopRectangularSpan as _SciQLopRectangularSpan,
                          SciQLopHorizontalSpan as _SciQLopHorizontalSpan,
                          )

from SciQLopPlots import (Coordinates as _Coordinates, LineTermination, SciQLopPlotRange as _SciQLopPlotRange)

from .protocol import Plot, Item
from .enums import CoordinateSystem
from .._annotations import experimental_api
from ._thread_safety import on_main_thread
from PySide6.QtCore import QRectF, QPointF
from PySide6.QtGui import QColor, QBrush, QFont, QPalette, QPixmap, Qt

__all__ = ['Pixmap', 'Ellipse', 'Text', 'CurvedLine', 'HorizontalLine', 'VerticalLine', 'StraightLine',
           'RectangularSpan', 'HorizontalSpan', 'LineTermination']


def _coordinate_system_to_sqp(coordinate_system: CoordinateSystem) -> _Coordinates:
    if coordinate_system == CoordinateSystem.Pixel:
        return _Coordinates.Pixels
    elif coordinate_system == CoordinateSystem.Data:
        return _Coordinates.Data
    else:
        raise ValueError(f"Unknown coordinate system {coordinate_system}")


def _default_foreground(plot_impl) -> QColor:
    """Pick a palette-aware default foreground color so primitives stay legible
    on both light and dark themes. Falls back to black if the plot widget has
    no palette for some reason."""
    try:
        return plot_impl.palette().color(QPalette.ColorRole.WindowText)
    except Exception:
        return QColor("black")


class _PlotItem(Item):
    """Shared concrete surface for plot items: visibility toggle, removal,
    and a friendly error once the underlying C++ item is gone."""

    _impl = None

    def _get_impl_or_raise(self):
        if self._impl is None:
            raise ValueError("The item does not exist anymore.")
        return self._impl

    @property
    @on_main_thread
    def visible(self) -> bool:
        # SciQLopPlots <= 0.27 leaves SciQLopItemInterface::visible() as an
        # unimplemented pure-virtual stub for all item classes: the getter
        # always returns False and the setter is a silent no-op. Raise instead
        # of lying; delegate to the C++ side once it is implemented upstream.
        self._get_impl_or_raise()
        raise NotImplementedError(
            "item visibility is not implemented in SciQLopPlots yet; "
            "use remove() to take the item off the plot")

    @visible.setter
    @on_main_thread
    def visible(self, visible: bool):
        self._get_impl_or_raise()
        raise NotImplementedError(
            "item visibility is not implemented in SciQLopPlots yet; "
            "use remove() to take the item off the plot")

    @on_main_thread
    def remove(self) -> None:
        """Remove this item from the plot and release C++ resources."""
        if self._impl is not None:
            self._impl.deleteLater()
            self._impl = None


class Pixmap(_PlotItem):
    """An image drawn on a plot.
    """
    @on_main_thread
    def __init__(self, plot: Plot, x: float, y: float, width: float, height: float,
                 image: Union[str, bytes, QPixmap],
                 coordinate_system: CoordinateSystem = CoordinateSystem.Data):
        """Initialize a Pixmap object.

        Parameters
        ----------
        plot : Plot
            The plot to which the pixmap belongs.
        x, y, width, height : float
            Bounding box of the pixmap.
        image : str | bytes | QPixmap
            The image to display: a file path, raw bytes, or an existing QPixmap.
        coordinate_system : CoordinateSystem
            ``Data`` (default) or ``Pixel``.
        """
        if isinstance(image, QPixmap):
            pixmap = image
        else:
            pixmap = QPixmap()
            if isinstance(image, str):
                pixmap.load(image)
            else:
                pixmap.loadFromData(image)

        bounding_box = QRectF(QPointF(x, y), QPointF(x + width, y + height))

        self._impl: _SciQLopPixmapItem = _SciQLopPixmapItem(
            plot._get_impl_or_raise(), pixmap, bounding_box,
            False, _coordinate_system_to_sqp(coordinate_system))

    @property
    @on_main_thread
    def position(self) -> Tuple[float, float]:
        p = self._get_impl_or_raise().position()
        return p.x(), p.y()

    @position.setter
    @on_main_thread
    def position(self, position: Tuple[float, float]):
        self._get_impl_or_raise().set_position(*position)


class Ellipse(_PlotItem):
    """An ellipse on a plot.

    The default line colour follows the plot's palette so the ellipse stays
    visible on both light and dark themes. The fill is transparent by default.
    """

    @on_main_thread
    def __init__(self, plot: Plot, x: float, y: float, width: float, height: float, *,
                 line_color: Optional[Union[str, QColor]] = None,
                 line_width: Optional[float] = None,
                 line_style: Optional[Qt.PenStyle] = None,
                 fill_color: Optional[Union[str, QColor]] = None,
                 coordinate_system: CoordinateSystem = CoordinateSystem.Data,
                 tool_tip: str = ""):
        """Initialize an Ellipse object.

        Parameters
        ----------
        plot : Plot
            The plot to which the ellipse belongs.
        x, y, width, height : float
            Bounding box of the ellipse.
        line_color : str | QColor, optional
            Border colour. Defaults to the plot's palette text colour.
        line_width : float, optional
            Border width.
        line_style : Qt.PenStyle, optional
            Border style (``Qt.SolidLine``, ``Qt.DashLine``, …).
        fill_color : str | QColor, optional
            Fill colour. Defaults to transparent.
        coordinate_system : CoordinateSystem
            ``Data`` (default) or ``Pixel``.
        tool_tip : str
            Tooltip text. Defaults to an empty string.
        """
        bounding_box = QRectF(QPointF(x, y), QPointF(x + width, y + height))

        impl = plot._get_impl_or_raise()
        self._impl: _SciQLopEllipseItem = _SciQLopEllipseItem(
            impl, bounding_box, False,
            _coordinate_system_to_sqp(coordinate_system), tool_tip)

        self.line_color = line_color if line_color is not None else _default_foreground(impl)
        if line_width is not None:
            self.line_width = line_width
        if line_style is not None:
            self.line_style = line_style
        self.fill_color = fill_color  # None → transparent

    @property
    @on_main_thread
    def position(self) -> Tuple[float, float]:
        p = self._get_impl_or_raise().position()
        return p.x(), p.y()

    @position.setter
    @on_main_thread
    def position(self, position: Tuple[float, float]):
        self._get_impl_or_raise().set_position(*position)

    @property
    @on_main_thread
    def line_width(self) -> float:
        return self._get_impl_or_raise().pen().width()

    @line_width.setter
    @on_main_thread
    def line_width(self, line_width: float):
        impl = self._get_impl_or_raise()
        pen = impl.pen()
        pen.setWidthF(line_width)
        impl.set_pen(pen)

    @property
    @on_main_thread
    def line_color(self) -> QColor:
        return self._get_impl_or_raise().pen().color()

    @line_color.setter
    @on_main_thread
    def line_color(self, line_color: Union[int, str, QColor]):
        impl = self._get_impl_or_raise()
        pen = impl.pen()
        pen.setColor(QColor(line_color))
        impl.set_pen(pen)

    @property
    @on_main_thread
    def fill_color(self) -> QColor:
        return self._get_impl_or_raise().brush().color()

    @fill_color.setter
    @on_main_thread
    def fill_color(self, fill_color: Union[int, str, QColor, None]):
        impl = self._get_impl_or_raise()
        brush: QBrush = impl.brush()
        if fill_color is None:
            brush.setStyle(Qt.NoBrush)
        else:
            brush.setColor(QColor(fill_color))
            brush.setStyle(Qt.SolidPattern)
        impl.set_brush(brush)

    @property
    @on_main_thread
    def line_style(self) -> Qt.PenStyle:
        return self._get_impl_or_raise().pen().style()

    @line_style.setter
    @on_main_thread
    def line_style(self, style: Qt.PenStyle):
        impl = self._get_impl_or_raise()
        pen = impl.pen()
        pen.setStyle(style)
        impl.set_pen(pen)


class Text(_PlotItem):
    """A text label on a plot.

    By default the text colour follows the plot's palette (``WindowText`` role)
    so labels stay legible on both light and dark themes. Pass ``color=`` to
    override.
    """

    @on_main_thread
    def __init__(self, plot: Plot, text: str, x: float, y: float, *,
                 color: Optional[Union[str, QColor]] = None,
                 font_size: Optional[float] = None,
                 font_family: Optional[str] = None,
                 coordinate_system: CoordinateSystem = CoordinateSystem.Data):
        """Initialize a Text object.

        Parameters
        ----------
        plot : Plot
            The plot to which the text belongs.
        text : str
            The text to display.
        x, y : float
            Position of the text.
        color : str | QColor, optional
            Text colour. Defaults to the plot's palette text colour.
        font_size : float, optional
            Point size of the font. Defaults to the current QCP font size.
        font_family : str, optional
            Font family. Defaults to the current QCP font family.
        coordinate_system : CoordinateSystem
            ``Data`` (default) or ``Pixel``.

        Examples
        --------
        >>> label = Text(plot, "shock crossing", x=0.5, y=0.9)
        """
        impl = plot._get_impl_or_raise()
        self._impl: _SciQLopTextItem = _SciQLopTextItem(
            impl, text, QPointF(x, y), False,
            _coordinate_system_to_sqp(coordinate_system))
        self._get_impl_or_raise().set_color(QColor(color) if color is not None else _default_foreground(impl))
        if font_size is not None:
            self._get_impl_or_raise().set_font_size(font_size)
        if font_family is not None:
            self._get_impl_or_raise().set_font_family(font_family)

    @property
    @on_main_thread
    def position(self) -> Tuple[float, float]:
        p = self._get_impl_or_raise().position()
        return p.x(), p.y()

    @position.setter
    @on_main_thread
    def position(self, position: Tuple[float, float]):
        self._get_impl_or_raise().set_position(QPointF(*position))

    @property
    @on_main_thread
    def text(self) -> str:
        return self._get_impl_or_raise().text()

    @text.setter
    @on_main_thread
    def text(self, text: str):
        self._get_impl_or_raise().set_text(text)

    @property
    @on_main_thread
    def color(self) -> QColor:
        return self._get_impl_or_raise().color()

    @color.setter
    @on_main_thread
    def color(self, c: Union[str, QColor]):
        self._get_impl_or_raise().set_color(QColor(c))

    @property
    @on_main_thread
    def font(self) -> QFont:
        return self._get_impl_or_raise().font()

    @font.setter
    @on_main_thread
    def font(self, f: QFont):
        self._get_impl_or_raise().set_font(f)

    @property
    @on_main_thread
    def font_size(self) -> float:
        return self._get_impl_or_raise().font_size()

    @font_size.setter
    @on_main_thread
    def font_size(self, size: float):
        self._get_impl_or_raise().set_font_size(size)

    @property
    @on_main_thread
    def font_family(self) -> str:
        return self._get_impl_or_raise().font().family()

    @font_family.setter
    @on_main_thread
    def font_family(self, family: str):
        self._get_impl_or_raise().set_font_family(family)


class CurvedLine(_PlotItem):
    """A curved line with optional terminators at each end (default: arrow at ``stop``).

    The default line colour follows the plot's palette so the line stays
    visible on both light and dark themes.
    """

    @on_main_thread
    def __init__(self, plot: Plot, start: Tuple[float, float], stop: Tuple[float, float], *,
                 color: Optional[Union[str, QColor]] = None,
                 line_width: Optional[float] = None,
                 line_style: Optional[Qt.PenStyle] = None,
                 start_termination: LineTermination = LineTermination.NoneTermination,
                 stop_termination: LineTermination = LineTermination.Arrow,
                 start_direction: Optional[Tuple[float, float]] = None,
                 stop_direction: Optional[Tuple[float, float]] = None,
                 coordinate_system: CoordinateSystem = CoordinateSystem.Data):
        """Initialize a CurvedLine object.

        Parameters
        ----------
        plot : Plot
            The plot to which the curved line belongs.
        start, stop : Tuple[float, float]
            The endpoints of the curved line.
        color : str | QColor, optional
            Line colour. Defaults to the plot's palette text colour.
        line_width : float, optional
            Line width.
        line_style : Qt.PenStyle, optional
            Line style (``Qt.SolidLine``, ``Qt.DashLine``, …).
        start_termination, stop_termination : LineTermination, optional
            Shape drawn at each endpoint.
            Defaults: no terminator at ``start``, arrow at ``stop``.
        start_direction, stop_direction : Tuple[float, float], optional
            Bezier control handles for the curve. Default places them
            at 1/3 and 2/3 along the straight ``start → stop`` segment,
            giving an almost-straight curve (override to add curvature).
        coordinate_system : CoordinateSystem
            ``Data`` (default) or ``Pixel``.

        Examples
        --------
        >>> arrow = CurvedLine(
        ...     plot, start=(0.0, 0.0), stop=(1.0, 1.0),
        ...     start_termination=LineTermination.NoneTermination,
        ...     stop_termination=LineTermination.Arrow,
        ... )
        """
        impl = plot._get_impl_or_raise()
        self._impl: _SciQLopCurvedLineItem = _SciQLopCurvedLineItem(
            impl, QPointF(*start), QPointF(*stop),
            start_termination, stop_termination,
            _coordinate_system_to_sqp(coordinate_system))

        # QCPItemCurve initialises both Bezier control handles at (0, 0) in
        # plot coordinates. On a time axis that's 1970 — the curve sweeps to
        # the year-1970 corner before doubling back, which looks insane. Put
        # the handles on the straight line between endpoints by default.
        if start_direction is None:
            start_direction = (start[0] + (stop[0] - start[0]) / 3.0,
                               start[1] + (stop[1] - start[1]) / 3.0)
        if stop_direction is None:
            stop_direction = (start[0] + 2.0 * (stop[0] - start[0]) / 3.0,
                              start[1] + 2.0 * (stop[1] - start[1]) / 3.0)
        self._get_impl_or_raise().set_start_dir_position(QPointF(*start_direction))
        self._get_impl_or_raise().set_stop_dir_position(QPointF(*stop_direction))

        self.color = color if color is not None else _default_foreground(impl)
        if line_width is not None:
            self.line_width = line_width
        if line_style is not None:
            self.line_style = line_style

    @property
    @on_main_thread
    def start(self) -> Tuple[float, float]:
        p = self._get_impl_or_raise().start_position()
        return p.x(), p.y()

    @start.setter
    @on_main_thread
    def start(self, start: Tuple[float, float]):
        self._get_impl_or_raise().set_start_position(QPointF(*start))

    @property
    @on_main_thread
    def stop(self) -> Tuple[float, float]:
        p = self._get_impl_or_raise().stop_position()
        return p.x(), p.y()

    @stop.setter
    @on_main_thread
    def stop(self, stop: Tuple[float, float]):
        self._get_impl_or_raise().set_stop_position(QPointF(*stop))

    @property
    @on_main_thread
    def start_direction(self) -> Tuple[float, float]:
        p = self._get_impl_or_raise().start_dir_position()
        return p.x(), p.y()

    @start_direction.setter
    @on_main_thread
    def start_direction(self, start_direction: Tuple[float, float]):
        self._get_impl_or_raise().set_start_dir_position(QPointF(*start_direction))

    @property
    @on_main_thread
    def stop_direction(self) -> Tuple[float, float]:
        p = self._get_impl_or_raise().stop_dir_position()
        return p.x(), p.y()

    @stop_direction.setter
    @on_main_thread
    def stop_direction(self, stop_direction: Tuple[float, float]):
        self._get_impl_or_raise().set_stop_dir_position(QPointF(*stop_direction))

    @property
    @on_main_thread
    def color(self) -> QColor:
        return self._get_impl_or_raise().color()

    @color.setter
    @on_main_thread
    def color(self, c: Union[str, QColor]):
        self._get_impl_or_raise().set_color(QColor(c))

    @property
    @on_main_thread
    def line_width(self) -> float:
        return self._get_impl_or_raise().line_width()

    @line_width.setter
    @on_main_thread
    def line_width(self, w: float):
        self._get_impl_or_raise().set_line_width(w)

    @property
    @on_main_thread
    def line_style(self) -> Qt.PenStyle:
        return self._get_impl_or_raise().line_style()

    @line_style.setter
    @on_main_thread
    def line_style(self, style: Qt.PenStyle):
        self._get_impl_or_raise().set_line_style(style)

    @property
    @on_main_thread
    def start_termination(self) -> LineTermination:
        return self._get_impl_or_raise().start_termination()

    @start_termination.setter
    @on_main_thread
    def start_termination(self, termination: LineTermination):
        self._get_impl_or_raise().set_start_termination(termination)

    @property
    @on_main_thread
    def stop_termination(self) -> LineTermination:
        return self._get_impl_or_raise().stop_termination()

    @stop_termination.setter
    @on_main_thread
    def stop_termination(self, termination: LineTermination):
        self._get_impl_or_raise().set_stop_termination(termination)


class HorizontalLine:
    """A horizontal line at a fixed Y value on a plot.

    Parameters
    ----------
    plot : Plot
        The plot to which the line belongs.
    value : float
        The Y-axis position of the line.
    color : str or QColor, optional
        Line color. Accepts CSS color strings (e.g. ``"#2ecc71"``)
        or ``QColor`` instances. Defaults to green.
    movable : bool
        Whether the user can drag the line. Defaults to False.
    """

    @experimental_api()
    @on_main_thread
    def __init__(self, plot: Plot, value: float, *,
                 color: Optional[Union[str, QColor]] = None,
                 movable: bool = False):
        self._impl: _SciQLopHorizontalLine = _SciQLopHorizontalLine(
            plot._get_impl_or_raise(), value, movable)
        if color is not None:
            self._impl.set_color(QColor(color))

    def _get_impl_or_raise(self):
        if self._impl is None:
            raise ValueError("The item does not exist anymore.")
        return self._impl

    @property
    @on_main_thread
    def value(self) -> float:
        return self._get_impl_or_raise().position

    @value.setter
    @on_main_thread
    def value(self, v: float):
        self._get_impl_or_raise().set_position(v)

    @property
    @on_main_thread
    def color(self) -> QColor:
        return self._get_impl_or_raise().color()

    @color.setter
    @on_main_thread
    def color(self, c: Union[str, QColor]):
        self._get_impl_or_raise().set_color(QColor(c))

    @property
    @on_main_thread
    def line_width(self) -> float:
        return self._get_impl_or_raise().line_width()

    @line_width.setter
    @on_main_thread
    def line_width(self, w: float):
        self._get_impl_or_raise().set_line_width(w)

    @on_main_thread
    def remove(self) -> None:
        """Remove this line from the plot and release C++ resources."""
        if self._impl is not None:
            self._impl.deleteLater()
            self._impl = None


class VerticalLine(_PlotItem):
    """A vertical line at a fixed X value on a plot.

    The default line colour follows the plot's palette so the line stays
    visible on both light and dark themes.

    Parameters
    ----------
    plot : Plot
        The plot to which the line belongs.
    value : float
        The X-axis position of the line.
    color : str or QColor, optional
        Line colour. Defaults to the plot's palette text colour.
    line_width : float, optional
        Line width.
    line_style : Qt.PenStyle, optional
        Line style (``Qt.SolidLine``, ``Qt.DashLine``, ...).
    coordinate_system : CoordinateSystem
        ``Data`` (default) or ``Pixel``.
    movable : bool
        Whether the user can drag the line. Defaults to False.
    """

    @on_main_thread
    def __init__(self, plot: Plot, value: float, *,
                 color: Optional[Union[str, QColor]] = None,
                 line_width: Optional[float] = None,
                 line_style: Optional[Qt.PenStyle] = None,
                 coordinate_system: CoordinateSystem = CoordinateSystem.Data,
                 movable: bool = False):
        impl = plot._get_impl_or_raise()
        self._impl: _SciQLopVerticalLine = _SciQLopVerticalLine(
            impl, value, movable, _coordinate_system_to_sqp(coordinate_system))
        self.color = color if color is not None else _default_foreground(impl)
        if line_width is not None:
            self.line_width = line_width
        if line_style is not None:
            self.line_style = line_style

    @property
    @on_main_thread
    def value(self) -> float:
        return self._get_impl_or_raise().position

    @value.setter
    @on_main_thread
    def value(self, v: float):
        self._get_impl_or_raise().set_position(v)

    @property
    @on_main_thread
    def color(self) -> QColor:
        return self._get_impl_or_raise().color()

    @color.setter
    @on_main_thread
    def color(self, c: Union[str, QColor]):
        self._get_impl_or_raise().set_color(QColor(c))

    @property
    @on_main_thread
    def line_width(self) -> float:
        return self._get_impl_or_raise().line_width()

    @line_width.setter
    @on_main_thread
    def line_width(self, w: float):
        self._get_impl_or_raise().set_line_width(w)

    @property
    @on_main_thread
    def line_style(self) -> Qt.PenStyle:
        return self._get_impl_or_raise().line_style()

    @line_style.setter
    @on_main_thread
    def line_style(self, style: Qt.PenStyle):
        self._get_impl_or_raise().set_line_style(style)


class StraightLine(_PlotItem):
    """A straight reference line on a plot.

    The public API accepts two endpoints, but the upstream
    ``SciQLopStraightLine`` only supports axis-aligned infinite lines. The
    wrapper therefore interprets the endpoints heuristically: true horizontal
    or vertical lines keep their orientation; for diagonal inputs it falls
    back to an axis-aligned line through the bounding-box centre along the
    dominant axis.

    The default line colour follows the plot's palette.

    Parameters
    ----------
    plot : Plot
        The plot to which the line belongs.
    x1, y1, x2, y2 : float
        Two points describing the line. For axis-aligned lines the line is
        placed at the corresponding constant coordinate; for diagonal lines a
        best-effort axis-aligned approximation is used.
    color : str or QColor, optional
        Line colour. Defaults to the plot's palette text colour.
    line_width : float, optional
        Line width.
    line_style : Qt.PenStyle, optional
        Line style (``Qt.SolidLine``, ``Qt.DashLine``, ...).
    coordinate_system : CoordinateSystem
        ``Data`` (default) or ``Pixel``.
    movable : bool
        Whether the user can drag the line. Defaults to False.
    """

    @on_main_thread
    def __init__(self, plot: Plot, x1: float, y1: float, x2: float, y2: float, *,
                 color: Optional[Union[str, QColor]] = None,
                 line_width: Optional[float] = None,
                 line_style: Optional[Qt.PenStyle] = None,
                 coordinate_system: CoordinateSystem = CoordinateSystem.Data,
                 movable: bool = False):
        impl = plot._get_impl_or_raise()
        dx = x2 - x1
        dy = y2 - y1
        if abs(dx) < 1e-12:
            self._orientation = Qt.Orientation.Vertical
            position = float(x1)
        elif abs(dy) < 1e-12:
            self._orientation = Qt.Orientation.Horizontal
            position = float(y1)
        elif abs(dx) >= abs(dy):
            self._orientation = Qt.Orientation.Horizontal
            position = float((y1 + y2) / 2.0)
        else:
            self._orientation = Qt.Orientation.Vertical
            position = float((x1 + x2) / 2.0)

        self._impl: _SciQLopStraightLine = _SciQLopStraightLine(
            impl, position, movable, _coordinate_system_to_sqp(coordinate_system), self._orientation)
        self.color = color if color is not None else _default_foreground(impl)
        if line_width is not None:
            self.line_width = line_width
        if line_style is not None:
            self.line_style = line_style

    @property
    def orientation(self) -> Qt.Orientation:
        return self._orientation

    @property
    @on_main_thread
    def value(self) -> float:
        return self._get_impl_or_raise().position

    @value.setter
    @on_main_thread
    def value(self, v: float):
        self._get_impl_or_raise().set_position(v)

    @property
    @on_main_thread
    def color(self) -> QColor:
        return self._get_impl_or_raise().color()

    @color.setter
    @on_main_thread
    def color(self, c: Union[str, QColor]):
        self._get_impl_or_raise().set_color(QColor(c))

    @property
    @on_main_thread
    def line_width(self) -> float:
        return self._get_impl_or_raise().line_width()

    @line_width.setter
    @on_main_thread
    def line_width(self, w: float):
        self._get_impl_or_raise().set_line_width(w)

    @property
    @on_main_thread
    def line_style(self) -> Qt.PenStyle:
        return self._get_impl_or_raise().line_style()

    @line_style.setter
    @on_main_thread
    def line_style(self, style: Qt.PenStyle):
        self._get_impl_or_raise().set_line_style(style)


def _default_span_color(plot_impl) -> QColor:
    """A semi-transparent variant of the palette foreground for span fills."""
    color = QColor(_default_foreground(plot_impl))
    color.setAlphaF(0.3)
    return color


class RectangularSpan(_PlotItem):
    """A rectangular span drawn between two X and two Y values.

    The default fill colour is a semi-transparent variant of the plot's
    palette foreground.

    Parameters
    ----------
    plot : Plot
        The plot to which the span belongs.
    x1, y1, x2, y2 : float
        Corners of the rectangle.
    color : str or QColor, optional
        Fill and border colour. Defaults to a transparent palette colour.
    borders_color : str or QColor, optional
        Border colour. Defaults to the same as ``color``.
    line_width : float, optional
        Border width.
    line_style : Qt.PenStyle, optional
        Border style.
    read_only : bool
        Whether the span is read-only. Defaults to False.
    visible : bool
        Whether the span is visible. Defaults to True.
    tool_tip : str
        Tooltip text.

    Examples
    --------
    >>> span = RectangularSpan(plot, x1=1.0, y1=-1.0, x2=2.0, y2=1.0, color="rgba(200, 50, 50, 0.3)")
    """

    @on_main_thread
    def __init__(self, plot: Plot, x1: float, y1: float, x2: float, y2: float, *,
                 color: Optional[Union[str, QColor]] = None,
                 borders_color: Optional[Union[str, QColor]] = None,
                 line_width: Optional[float] = None,
                 line_style: Optional[Qt.PenStyle] = None,
                 read_only: bool = False,
                 visible: bool = True,
                 tool_tip: str = ""):
        impl = plot._get_impl_or_raise()
        default_color = _default_span_color(impl)
        self._impl: _SciQLopRectangularSpan = _SciQLopRectangularSpan(
            impl, _SciQLopPlotRange(x1, x2), _SciQLopPlotRange(y1, y2),
            color or default_color, read_only, visible, tool_tip)
        self.borders_color = borders_color if borders_color is not None else (color if color is not None else default_color)
        if line_width is not None:
            self.line_width = line_width
        if line_style is not None:
            self.line_style = line_style

    @property
    @on_main_thread
    def color(self) -> QColor:
        return self._get_impl_or_raise().color()

    @color.setter
    @on_main_thread
    def color(self, c: Union[str, QColor]):
        self._get_impl_or_raise().set_color(QColor(c))

    @property
    @on_main_thread
    def borders_color(self) -> QColor:
        return self._get_impl_or_raise().borders_color()

    @borders_color.setter
    @on_main_thread
    def borders_color(self, c: Union[str, QColor]):
        self._get_impl_or_raise().set_borders_color(QColor(c))

    @property
    @on_main_thread
    def line_width(self) -> float:
        return self._get_impl_or_raise().line_width()

    @line_width.setter
    @on_main_thread
    def line_width(self, w: float):
        self._get_impl_or_raise().set_line_width(w)

    @property
    @on_main_thread
    def line_style(self) -> Qt.PenStyle:
        return self._get_impl_or_raise().line_style()

    @line_style.setter
    @on_main_thread
    def line_style(self, style: Qt.PenStyle):
        self._get_impl_or_raise().set_line_style(style)

    @property
    @on_main_thread
    def key_range(self) -> Tuple[float, float]:
        r = self._get_impl_or_raise().key_range()
        return r.start(), r.stop()

    @key_range.setter
    @on_main_thread
    def key_range(self, key_range: Tuple[float, float]):
        self._get_impl_or_raise().set_key_range(_SciQLopPlotRange(*key_range))

    @property
    @on_main_thread
    def value_range(self) -> Tuple[float, float]:
        r = self._get_impl_or_raise().value_range()
        return r.start(), r.stop()

    @value_range.setter
    @on_main_thread
    def value_range(self, value_range: Tuple[float, float]):
        self._get_impl_or_raise().set_value_range(_SciQLopPlotRange(*value_range))

    @property
    @on_main_thread
    def read_only(self) -> bool:
        return self._get_impl_or_raise().read_only()

    @read_only.setter
    @on_main_thread
    def read_only(self, read_only: bool):
        self._get_impl_or_raise().set_read_only(read_only)

    @property
    @on_main_thread
    def visible(self) -> bool:
        return self._get_impl_or_raise().visible()

    @visible.setter
    @on_main_thread
    def visible(self, visible: bool):
        self._get_impl_or_raise().set_visible(visible)

    @property
    @on_main_thread
    def tool_tip(self) -> str:
        return self._get_impl_or_raise().tool_tip()

    @tool_tip.setter
    @on_main_thread
    def tool_tip(self, tool_tip: str):
        self._get_impl_or_raise().set_tool_tip(tool_tip)


class HorizontalSpan(_PlotItem):
    """A horizontal span between two Y values.

    The default fill colour is a semi-transparent variant of the plot's
    palette foreground.

    Parameters
    ----------
    plot : Plot
        The plot to which the span belongs.
    y1, y2 : float
        Vertical extents of the span.
    color : str or QColor, optional
        Fill and border colour. Defaults to a transparent palette colour.
    borders_color : str or QColor, optional
        Border colour. Defaults to the same as ``color``.
    line_width : float, optional
        Border width.
    line_style : Qt.PenStyle, optional
        Border style.
    read_only : bool
        Whether the span is read-only. Defaults to False.
    visible : bool
        Whether the span is visible. Defaults to True.
    tool_tip : str
        Tooltip text.

    Examples
    --------
    >>> band = HorizontalSpan(plot, y1=-1.0, y2=1.0, color="rgba(50, 150, 200, 0.3)")
    """

    @on_main_thread
    def __init__(self, plot: Plot, y1: float, y2: float, *,
                 color: Optional[Union[str, QColor]] = None,
                 borders_color: Optional[Union[str, QColor]] = None,
                 line_width: Optional[float] = None,
                 line_style: Optional[Qt.PenStyle] = None,
                 read_only: bool = False,
                 visible: bool = True,
                 tool_tip: str = ""):
        impl = plot._get_impl_or_raise()
        default_color = _default_span_color(impl)
        self._impl: _SciQLopHorizontalSpan = _SciQLopHorizontalSpan(
            impl, _SciQLopPlotRange(y1, y2),
            color or default_color, read_only, visible, tool_tip)
        self.borders_color = borders_color if borders_color is not None else (color if color is not None else default_color)
        if line_width is not None:
            self.line_width = line_width
        if line_style is not None:
            self.line_style = line_style

    @property
    @on_main_thread
    def color(self) -> QColor:
        return self._get_impl_or_raise().color()

    @color.setter
    @on_main_thread
    def color(self, c: Union[str, QColor]):
        self._get_impl_or_raise().set_color(QColor(c))

    @property
    @on_main_thread
    def borders_color(self) -> QColor:
        return self._get_impl_or_raise().borders_color()

    @borders_color.setter
    @on_main_thread
    def borders_color(self, c: Union[str, QColor]):
        self._get_impl_or_raise().set_borders_color(QColor(c))

    @property
    @on_main_thread
    def line_width(self) -> float:
        return self._get_impl_or_raise().line_width()

    @line_width.setter
    @on_main_thread
    def line_width(self, w: float):
        self._get_impl_or_raise().set_line_width(w)

    @property
    @on_main_thread
    def line_style(self) -> Qt.PenStyle:
        return self._get_impl_or_raise().line_style()

    @line_style.setter
    @on_main_thread
    def line_style(self, style: Qt.PenStyle):
        self._get_impl_or_raise().set_line_style(style)

    @property
    @on_main_thread
    def range(self) -> Tuple[float, float]:
        r = self._get_impl_or_raise().range()
        return r.start(), r.stop()

    @range.setter
    @on_main_thread
    def range(self, vertical_range: Tuple[float, float]):
        self._get_impl_or_raise().set_range(_SciQLopPlotRange(*vertical_range))

    @property
    @on_main_thread
    def read_only(self) -> bool:
        return self._get_impl_or_raise().read_only()

    @read_only.setter
    @on_main_thread
    def read_only(self, read_only: bool):
        self._get_impl_or_raise().set_read_only(read_only)

    @property
    @on_main_thread
    def visible(self) -> bool:
        return self._get_impl_or_raise().visible()

    @visible.setter
    @on_main_thread
    def visible(self, visible: bool):
        self._get_impl_or_raise().set_visible(visible)

    @property
    @on_main_thread
    def tool_tip(self) -> str:
        return self._get_impl_or_raise().tool_tip()

    @tool_tip.setter
    @on_main_thread
    def tool_tip(self, tool_tip: str):
        self._get_impl_or_raise().set_tool_tip(tool_tip)
