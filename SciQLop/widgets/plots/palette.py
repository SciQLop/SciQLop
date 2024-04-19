from PySide6.QtGui import QColor
from seaborn import color_palette as seaborn_color_palette


def _to_qcolor(r: float, g: float, b: float):
    return QColor(int(r * 255), int(g * 255), int(b * 255))


class Palette:
    _palette_index: int = 0

    def __init__(self):
        self._palette = seaborn_color_palette()

    def next(self) -> QColor:
        color = self._palette[self._palette_index]
        self._palette_index = (self._palette_index + 1) % len(self._palette)
        return _to_qcolor(*color)

    def reset(self):
        self._palette_index = 0
