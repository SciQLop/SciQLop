from functools import lru_cache
from hashlib import md5

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

# 12 distinguishable colors with 80 alpha for span fill
_PALETTE = [
    QColor(31, 119, 180, 80),
    QColor(255, 127, 14, 80),
    QColor(44, 160, 44, 80),
    QColor(214, 39, 40, 80),
    QColor(148, 103, 189, 80),
    QColor(140, 86, 75, 80),
    QColor(227, 119, 194, 80),
    QColor(127, 127, 127, 80),
    QColor(188, 189, 34, 80),
    QColor(23, 190, 207, 80),
    QColor(174, 199, 232, 80),
    QColor(255, 187, 120, 80),
]


@lru_cache(maxsize=None)
def color_for_catalog(uuid: str) -> QColor:
    # md5 is stable across processes, unlike hash() which is randomized per-process
    index = int.from_bytes(md5(uuid.encode()).digest()[:4], "little") % len(_PALETTE)
    return QColor(_PALETTE[index])


_SWATCH_SIZE = 14


@lru_cache(maxsize=None)
def catalog_swatch_icon(uuid: str) -> QIcon:
    """A small filled dot in this catalog's color, for the tree row --
    cheap legend so 'which color is which catalog' is answerable without
    hovering an event on the plot (the only place the color was visible
    before this)."""
    color = QColor(color_for_catalog(uuid))
    color.setAlpha(255)
    pixmap = QPixmap(_SWATCH_SIZE, _SWATCH_SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    painter.drawEllipse(1, 1, _SWATCH_SIZE - 2, _SWATCH_SIZE - 2)
    painter.end()
    return QIcon(pixmap)
