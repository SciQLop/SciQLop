from functools import lru_cache
from hashlib import md5

from PySide6.QtGui import QColor

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
