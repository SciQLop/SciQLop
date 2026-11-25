from PySide6.QtGui import QColor


def _to_qcolor(r: float, g: float, b: float):
    return QColor(int(r * 255), int(g * 255), int(b * 255))


class Palette:
    _palette_index: int = 0

    def __init__(self, n_colors=32):
        from seaborn import color_palette  # here, not at import: seaborn costs ~1 s at startup, before any panel
        self._palette = color_palette(n_colors=n_colors)

    def next(self) -> QColor:
        color = self._palette[self._palette_index]
        self._palette_index = (self._palette_index + 1) % len(self._palette)
        return _to_qcolor(*color)

    def __len__(self):
        return len(self._palette)

    def reset(self):
        self._palette_index = 0


def make_color_list(palette):
    return  [ palette.next() for _ in range(len(palette)) ]