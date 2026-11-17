"""A project's folder icon with a badge for its state. Each state people must tell apart has its own
shape, so the badge reads without colour. SciQLop's theme has no status icons, and a bare dot would
look like a catalogue's colour swatch."""
from __future__ import annotations

from functools import cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QApplication

GREEN, AMBER, RED, GREY, BLUE, SLATE = "#3fa34d", "#e0a526", "#d0453a", "#9a9a9a", "#4a7fc1", "#55606e"
BADGES = {  # state -> (shape, colour): one shape per state, the colour only a second cue
    "synced": ("dot", GREEN),                 # all sent and received
    "connecting": ("ring", AMBER),            # on its way
    "offline": ("triangle", AMBER),           # server unreachable: changes wait
    "unauthorized": ("cross", RED),           # the sign-in ended
    "no_access": ("no entry", RED),           # the person was removed from the project
    "not joined": ("plus", GREY),             # listed, Join loads it
    "read-only": ("lock", BLUE),
    "on this computer": ("screen", SLATE),    # kept here only, never synced
    "released": ("hollow square", GREY),      # kept here, closed in this window
    "elsewhere": ("two windows", AMBER),      # kept here, open in another SciQLop window
}
SIZE = 16
BADGE = 8


def status_badge(state: str) -> QIcon:
    return _badge(*BADGES.get(state, BADGES["offline"]), QApplication.palette().window().color().name())


@cache
def _badge(shape: str, colour: str, background: str) -> QIcon:
    """Cached per palette too: the folder is drawn in the theme's colours."""
    from SciQLop.components.theming import get_icon
    pixmap = get_icon("folder_open").pixmap(SIZE, SIZE)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    box = QRectF(SIZE - BADGE, SIZE - BADGE, BADGE - 1, BADGE - 1)
    painter.setPen(QPen(QColor(background), 1))
    painter.setBrush(QColor(background))
    painter.drawEllipse(box.adjusted(-1, -1, 1, 1))
    _SHAPES[shape](painter, box, _readable(QColor(colour), QColor(background)))
    painter.end()
    return QIcon(pixmap)


def _readable(colour: QColor, background: QColor) -> QColor:
    """Dark themes: the same hue, lighter, so slate and grey badges stand out on the folder."""
    return colour.lighter(160) if background.lightness() < 128 else colour


def _filled(painter: QPainter, colour: QColor) -> None:
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(colour)


def _stroked(painter: QPainter, colour: QColor) -> None:
    painter.setPen(QPen(colour, 1.6))
    painter.setBrush(Qt.BrushStyle.NoBrush)


def _dot(painter, box, colour):
    _filled(painter, colour)
    painter.drawEllipse(box)


def _ring(painter, box, colour):
    _stroked(painter, colour)
    painter.drawEllipse(box.adjusted(1, 1, -1, -1))


def _triangle(painter, box, colour):
    _filled(painter, colour)
    painter.drawPolygon(QPolygonF([QPointF(box.center().x(), box.top()), box.bottomRight(), box.bottomLeft()]))


def _cross(painter, box, colour):
    _stroked(painter, colour)
    inner = box.adjusted(1, 1, -1, -1)
    painter.drawLine(inner.topLeft(), inner.bottomRight())
    painter.drawLine(inner.topRight(), inner.bottomLeft())


def _no_entry(painter, box, colour):
    _filled(painter, colour)
    painter.drawEllipse(box)
    painter.setBrush(QColor("white"))
    painter.drawRect(QRectF(box.left() + 1.5, box.center().y() - 0.9, box.width() - 3, 1.8))


def _plus(painter, box, colour):
    _stroked(painter, colour)
    inner = box.adjusted(1, 1, -1, -1)
    painter.drawLine(QPointF(inner.center().x(), inner.top()), QPointF(inner.center().x(), inner.bottom()))
    painter.drawLine(QPointF(inner.left(), inner.center().y()), QPointF(inner.right(), inner.center().y()))


def _hollow_square(painter, box, colour):
    _stroked(painter, colour)
    painter.drawRect(box.adjusted(1, 1, -1, -1))


def _two_windows(painter, box, colour):
    side = box.width() * 0.62
    _stroked(painter, colour)
    painter.drawRect(QRectF(box.left(), box.top(), side, side))
    _filled(painter, colour)
    painter.drawRect(QRectF(box.right() - side, box.bottom() - side, side, side))


def _lock(painter, box, colour):
    body = QRectF(box.left(), box.center().y(), box.width(), box.height() / 2)
    _filled(painter, colour)
    painter.drawRect(body)
    _stroked(painter, colour)
    shackle = QPainterPath()
    shackle.arcMoveTo(QRectF(box.left() + 1.5, box.top(), box.width() - 3, box.height() - 1), 0)
    shackle.arcTo(QRectF(box.left() + 1.5, box.top(), box.width() - 3, box.height() - 1), 0, 180)
    painter.drawPath(shackle)


def _screen(painter, box, colour):
    _filled(painter, colour)
    painter.drawRect(QRectF(box.left(), box.top(), box.width(), box.height() * 0.65))
    painter.drawRect(QRectF(box.left() + 1.5, box.bottom() - 1.5, box.width() - 3, 1.5))


_SHAPES = {"dot": _dot, "ring": _ring, "triangle": _triangle, "cross": _cross, "no entry": _no_entry,
           "plus": _plus, "lock": _lock, "screen": _screen, "hollow square": _hollow_square,
           "two windows": _two_windows}


@cache
def colour_dot(colour: str) -> QIcon:
    """An author's colour, as the CoCat web app shows it."""
    pixmap = QPixmap(SIZE, SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(colour))
    painter.drawEllipse(4, 4, SIZE - 8, SIZE - 8)
    painter.end()
    return QIcon(pixmap)
