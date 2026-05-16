from typing import Optional, Tuple, Union
from SciQLopPlots import (SciQLopPixmapItem as _SciQLopPixmapItem,
                          SciQLopEllipseItem as _SciQLopEllipseItem,
                          SciQLopTextItem as _SciQLopTextItem,
                          SciQLopCurvedLineItem as _SciQLopCurvedLineItem,
                          SciQLopHorizontalLine as _SciQLopHorizontalLine,
                          )

from SciQLopPlots import (Coordinates as _Coordinates, LineTermination)

from .protocol import Plot, Item
from .enums import CoordinateSystem
from .._annotations import experimental_api
from ._thread_safety import on_main_thread
from PySide6.QtCore import QRectF, QPointF
from PySide6.QtGui import QColor, QBrush, QFont, QPalette, QPixmap, Qt

__all__ = ['Pixmap', 'Ellipse', 'Text', 'CurvedLine', 'HorizontalLine', 'LineTermination']


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


class Pixmap(Item):
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
    def visible(self) -> bool:
        return self._impl.visible()

    @visible.setter
    @on_main_thread
    def visible(self, visible: bool):
        self._impl.set_visible(visible)

    @property
    @on_main_thread
    def position(self) -> Tuple[float, float]:
        p = self._impl.position()
        return p.x(), p.y()

    @position.setter
    @on_main_thread
    def position(self, position: Tuple[float, float]):
        self._impl.set_position(*position)


class Ellipse(Item):
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
    def visible(self) -> bool:
        return self._impl.visible()

    @visible.setter
    @on_main_thread
    def visible(self, visible: bool):
        self._impl.set_visible(visible)

    @property
    @on_main_thread
    def position(self) -> Tuple[float, float]:
        p = self._impl.position()
        return p.x(), p.y()

    @position.setter
    @on_main_thread
    def position(self, position: Tuple[float, float]):
        self._impl.set_position(*position)

    @property
    @on_main_thread
    def line_width(self) -> float:
        return self._impl.pen().width()

    @line_width.setter
    @on_main_thread
    def line_width(self, line_width: float):
        pen = self._impl.pen()
        pen.setWidthF(line_width)
        self._impl.set_pen(pen)

    @property
    @on_main_thread
    def line_color(self) -> int:
        return self._impl.pen().color().rgba()

    @line_color.setter
    @on_main_thread
    def line_color(self, line_color: Union[int, str]):
        pen = self._impl.pen()
        pen.setColor(QColor(line_color))
        self._impl.set_pen(pen)

    @property
    @on_main_thread
    def fill_color(self) -> int:
        return self._impl.brush().color().rgba()

    @fill_color.setter
    @on_main_thread
    def fill_color(self, fill_color: Union[int, str, None]):
        brush: QBrush = self._impl.brush()
        if fill_color is None:
            brush.setStyle(Qt.NoBrush)
        else:
            brush.setColor(QColor(fill_color))
            brush.setStyle(Qt.SolidPattern)
        self._impl.set_brush(brush)

    @property
    @on_main_thread
    def line_style(self) -> Qt.PenStyle:
        return self._impl.pen().style()

    @line_style.setter
    @on_main_thread
    def line_style(self, style: Qt.PenStyle):
        pen = self._impl.pen()
        pen.setStyle(style)
        self._impl.set_pen(pen)


class Text(Item):
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
        """
        impl = plot._get_impl_or_raise()
        self._impl: _SciQLopTextItem = _SciQLopTextItem(
            impl, text, QPointF(x, y), False,
            _coordinate_system_to_sqp(coordinate_system))
        self._impl.set_color(QColor(color) if color is not None else _default_foreground(impl))
        if font_size is not None:
            self._impl.set_font_size(font_size)
        if font_family is not None:
            self._impl.set_font_family(font_family)

    @property
    @on_main_thread
    def position(self) -> Tuple[float, float]:
        p = self._impl.position()
        return p.x(), p.y()

    @position.setter
    @on_main_thread
    def position(self, position: Tuple[float, float]):
        self._impl.set_position(QPointF(*position))

    @property
    @on_main_thread
    def text(self) -> str:
        return self._impl.text()

    @text.setter
    @on_main_thread
    def text(self, text: str):
        self._impl.set_text(text)

    @property
    @on_main_thread
    def color(self) -> QColor:
        return self._impl.color()

    @color.setter
    @on_main_thread
    def color(self, c: Union[str, QColor]):
        self._impl.set_color(QColor(c))

    @property
    @on_main_thread
    def font(self) -> QFont:
        return self._impl.font()

    @font.setter
    @on_main_thread
    def font(self, f: QFont):
        self._impl.set_font(f)

    @property
    @on_main_thread
    def font_size(self) -> float:
        return self._impl.font_size()

    @font_size.setter
    @on_main_thread
    def font_size(self, size: float):
        self._impl.set_font_size(size)

    @property
    @on_main_thread
    def font_family(self) -> str:
        return self._impl.font().family()

    @font_family.setter
    @on_main_thread
    def font_family(self, family: str):
        self._impl.set_font_family(family)


class CurvedLine(Item):
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
        self._impl.set_start_dir_position(QPointF(*start_direction))
        self._impl.set_stop_dir_position(QPointF(*stop_direction))

        self.color = color if color is not None else _default_foreground(impl)
        if line_width is not None:
            self.line_width = line_width
        if line_style is not None:
            self.line_style = line_style

    @property
    @on_main_thread
    def start(self) -> Tuple[float, float]:
        p = self._impl.start_position()
        return p.x(), p.y()

    @start.setter
    @on_main_thread
    def start(self, start: Tuple[float, float]):
        self._impl.set_start_position(QPointF(*start))

    @property
    @on_main_thread
    def stop(self) -> Tuple[float, float]:
        p = self._impl.stop_position()
        return p.x(), p.y()

    @stop.setter
    @on_main_thread
    def stop(self, stop: Tuple[float, float]):
        self._impl.set_stop_position(QPointF(*stop))

    @property
    @on_main_thread
    def start_direction(self) -> Tuple[float, float]:
        p = self._impl.start_dir_position()
        return p.x(), p.y()

    @start_direction.setter
    @on_main_thread
    def start_direction(self, start_direction: Tuple[float, float]):
        self._impl.set_start_dir_position(QPointF(*start_direction))

    @property
    @on_main_thread
    def stop_direction(self) -> Tuple[float, float]:
        p = self._impl.stop_dir_position()
        return p.x(), p.y()

    @stop_direction.setter
    @on_main_thread
    def stop_direction(self, stop_direction: Tuple[float, float]):
        self._impl.set_stop_dir_position(QPointF(*stop_direction))

    @property
    @on_main_thread
    def color(self) -> QColor:
        return self._impl.color()

    @color.setter
    @on_main_thread
    def color(self, c: Union[str, QColor]):
        self._impl.set_color(QColor(c))

    @property
    @on_main_thread
    def line_width(self) -> float:
        return self._impl.line_width()

    @line_width.setter
    @on_main_thread
    def line_width(self, w: float):
        self._impl.set_line_width(w)

    @property
    @on_main_thread
    def line_style(self) -> Qt.PenStyle:
        return self._impl.line_style()

    @line_style.setter
    @on_main_thread
    def line_style(self, style: Qt.PenStyle):
        self._impl.set_line_style(style)

    @property
    @on_main_thread
    def start_termination(self) -> LineTermination:
        return self._impl.start_termination()

    @start_termination.setter
    @on_main_thread
    def start_termination(self, termination: LineTermination):
        self._impl.set_start_termination(termination)

    @property
    @on_main_thread
    def stop_termination(self) -> LineTermination:
        return self._impl.stop_termination()

    @stop_termination.setter
    @on_main_thread
    def stop_termination(self, termination: LineTermination):
        self._impl.set_stop_termination(termination)


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

    @property
    @on_main_thread
    def value(self) -> float:
        return self._impl.position

    @value.setter
    @on_main_thread
    def value(self, v: float):
        self._impl.set_position(v)

    @property
    @on_main_thread
    def color(self) -> QColor:
        return self._impl.color()

    @color.setter
    @on_main_thread
    def color(self, c: Union[str, QColor]):
        self._impl.set_color(QColor(c))

    @property
    @on_main_thread
    def line_width(self) -> float:
        return self._impl.line_width()

    @line_width.setter
    @on_main_thread
    def line_width(self, w: float):
        self._impl.set_line_width(w)

    @on_main_thread
    def remove(self) -> None:
        """Remove this line from the plot and release C++ resources."""
        if self._impl is not None:
            self._impl.deleteLater()
            self._impl = None
