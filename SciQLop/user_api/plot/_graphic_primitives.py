from typing import Tuple, Union
from SciQLopPlots import (SciQLopPixmapItem as _SciQLopPixmapItem,
                          SciQLopEllipseItem as _SciQLopEllipseItem,
                          SciQLopTextItem as _SciQLopTextItem,
                          SciQLopCurvedLineItem as _SciQLopCurvedLineItem,
                          )

from SciQLopPlots import (Coordinates as _Coordinates, LineTermination as _LineTermination)

from .protocol import Plot, Item
from .enums import CoordinateSystem
from PySide6.QtCore import QRectF, QPointF
from PySide6.QtGui import QColor, QBrush, Qt

__all__ = ['Pixmap', 'Ellipse', 'Text', 'CurvedLine']


def _coordinate_system_to_sqp(coordinate_system: CoordinateSystem) -> _Coordinates:
    if coordinate_system == CoordinateSystem.Pixel:
        return _Coordinates.Pixel
    elif coordinate_system == CoordinateSystem.Data:
        return _Coordinates.Data
    else:
        raise ValueError(f"Unknown coordinate system {coordinate_system}")


class Pixmap(Item):
    def __init__(self, plot: Plot, x: float, y: float, width: float, height: float, image: Union[str, bytes],
                 coordinate_system: CoordinateSystem = CoordinateSystem.Data, tool_tip: str = ""):
        bounding_box = QRectF(QPointF(x, y), QPointF(x + width, y + height))

        self._impl: _SciQLopPixmapItem = _SciQLopPixmapItem(plot._get_impl_or_raise(), image, bounding_box,
                                                            False, _coordinate_system_to_sqp(coordinate_system),
                                                            tool_tip)

    @property
    def visible(self) -> bool:
        return self._impl.visible()

    @visible.setter
    def visible(self, visible: bool):
        self._impl.set_visible(visible)

    @property
    def position(self) -> Tuple[float, float]:
        p = self._impl.position()
        return p.x(), p.y()

    @position.setter
    def position(self, position: Tuple[float, float]):
        self._impl.set_position(*position)


class Ellipse(Item):
    def __init__(self, plot: Plot, x: float, y: float, width: float, height: float,
                 coordinate_system: CoordinateSystem = CoordinateSystem.Data, tool_tip: str = ""):

        bounding_box = QRectF(QPointF(x, y), QPointF(x + width, y + height))

        self._impl: _SciQLopEllipseItem = _SciQLopEllipseItem(plot._get_impl_or_raise(),
                                                              bounding_box,
                                                              False, _coordinate_system_to_sqp(coordinate_system),
                                                              tool_tip)

    @property
    def visible(self) -> bool:
        return self._impl.visible()

    @visible.setter
    def visible(self, visible: bool):
        self._impl.set_visible(visible)

    @property
    def position(self) -> Tuple[float, float]:
        p = self._impl.position()
        return p.x(), p.y()

    @position.setter
    def position(self, position: Tuple[float, float]):
        self._impl.set_position(*position)

    @property
    def line_width(self) -> float:
        return self._impl.pen().width()

    @line_width.setter
    def line_width(self, line_width: float):
        pen = self._impl.pen()
        pen.setWidthF(line_width)
        self._impl.set_pen(pen)

    @property
    def line_color(self) -> int:
        return self._impl.pen().color().rgba()

    @line_color.setter
    def line_color(self, line_color: Union[int, str]):
        pen = self._impl.pen()
        pen.setColor(QColor(line_color))
        self._impl.set_pen(pen)

    @property
    def fill_color(self) -> int:
        return self._impl.brush().color().rgba()

    @fill_color.setter
    def fill_color(self, fill_color: Union[int, str, None]):
        brush: QBrush = self._impl.brush()
        if fill_color is None:
            brush.setStyle(Qt.NoBrush)
        else:
            brush.setColor(QColor(fill_color))
            brush.setStyle(Qt.SolidPattern)
        self._impl.set_brush(brush)


class Text(Item):
    def __init__(self, plot: Plot, text: str, x: float, y: float,
                 coordinate_system: CoordinateSystem = CoordinateSystem.Data, ):
        self._impl: _SciQLopTextItem = _SciQLopTextItem(plot._get_impl_or_raise(), text, QPointF(x, y), False,
                                                        _coordinate_system_to_sqp(coordinate_system))

    @property
    def position(self) -> Tuple[float, float]:
        p = self._impl.position()
        return p.x(), p.y()

    @position.setter
    def position(self, position: Tuple[float, float]):
        self._impl.set_position(QPointF(*position))

    @property
    def text(self) -> str:
        return self._impl.text()

    @text.setter
    def text(self, text: str):
        self._impl.set_text(text)


class CurvedLine(Item):
    def __init__(self, plot: Plot, start: Tuple[float, float], stop: Tuple[float, float],
                 coordinate_system: CoordinateSystem = CoordinateSystem.Data):
        self._impl: _SciQLopCurvedLineItem = _SciQLopCurvedLineItem(plot._get_impl_or_raise(), QPointF(*start),
                                                                    QPointF(*stop),
                                                                    _LineTermination.NoneTermination,
                                                                    _LineTermination.Arrow,
                                                                    _coordinate_system_to_sqp(coordinate_system))

    @property
    def start(self) -> Tuple[float, float]:
        p = self._impl.start_position()
        return p.x(), p.y()

    @start.setter
    def start(self, start: Tuple[float, float]):
        self._impl.set_start_position(QPointF(*start))

    @property
    def stop(self) -> Tuple[float, float]:
        p = self._impl.stop_position()
        return p.x(), p.y()

    @stop.setter
    def stop(self, stop: Tuple[float, float]):
        self._impl.set_stop_position(QPointF(*stop))

    @property
    def start_direction(self) -> Tuple[float, float]:
        p = self._impl.start_dir_position()
        return p.x(), p.y()

    @start_direction.setter
    def start_direction(self, start_direction: Tuple[float, float]):
        self._impl.set_start_dir_position(QPointF(*start_direction))

    @property
    def stop_direction(self) -> Tuple[float, float]:
        p = self._impl.stop_dir_position()
        return p.x(), p.y()

    @stop_direction.setter
    def stop_direction(self, stop_direction: Tuple[float, float]):
        self._impl.set_stop_dir_position(QPointF(*stop_direction))
