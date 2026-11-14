"""A project's folder icon with a coloured badge: synced, on its way, stopped, or not joined.
SciQLop's theme has no status icons, and a bare dot would look like a catalogue's colour swatch."""
from __future__ import annotations

from functools import cache

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

COLOURS = {
    "synced": "#3fa34d",
    "connecting": "#e0a526",
    "offline": "#e0a526",
    "unauthorized": "#d0453a",
    "no_access": "#d0453a",
    "not joined": "#9a9a9a",
}
SIZE = 16
BADGE = 8


def status_badge(status: str) -> QIcon:
    return _badge(status, QApplication.palette().window().color().name())


@cache
def _badge(status: str, background: str) -> QIcon:
    """Cached per palette too: the folder is drawn in the theme's colours."""
    from SciQLop.components.theming import get_icon
    pixmap = get_icon("folder_open").pixmap(SIZE, SIZE)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QColor(background))
    painter.setBrush(QColor(COLOURS.get(status, COLOURS["offline"])))
    painter.drawEllipse(SIZE - BADGE, SIZE - BADGE, BADGE - 1, BADGE - 1)
    painter.end()
    return QIcon(pixmap)


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
