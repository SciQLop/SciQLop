"""Colour parsing shared by plot primitives and layers.

QColor reads Qt names and ``#RRGGBB``/``#AARRGGBB`` but not CSS ``rgb()``/
``rgba()``: it returns an *invalid* colour, which paints nothing, so a styled
item simply vanishes with no error anywhere.
"""
import re
from typing import Optional, Union

from PySide6.QtGui import QColor

_CSS_RGB = re.compile(
    r"^\s*rgba?\(\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)\s*"
    r"(?:,\s*([0-9.]+)\s*)?\)\s*$", re.IGNORECASE)


def css_rgb(text: str) -> Optional[QColor]:
    """QColor from a CSS ``rgb()``/``rgba()`` string, or None if it is not one."""
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


def to_qcolor(color: Union[str, QColor, int]) -> QColor:
    """QColor from a QColor, a Qt colour name, ``#RRGGBB``/``#AARRGGBB`` or CSS
    ``rgb()``/``rgba()``; raises ValueError for a string that is none of these."""
    if isinstance(color, str):
        c = css_rgb(color) or QColor(color.strip())
        if not c.isValid():
            raise ValueError(f"unrecognised colour {color!r}: use a name, #RRGGBB, "
                             "#AARRGGBB or rgba(r, g, b, a)")
        return c
    return QColor(color)
