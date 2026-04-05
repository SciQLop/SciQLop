from __future__ import annotations

from hashlib import md5
from typing import Any

from pydantic import BaseModel
from PySide6.QtGui import QColor

from .color_palette import _PALETTE

_SPAN_ALPHA = 80


def _is_numeric(values: list[Any]) -> bool:
    return all(isinstance(v, (int, float)) for v in values if v is not None)


def _hash_color(value: str) -> QColor:
    index = int.from_bytes(md5(str(value).encode()).digest()[:4], "little") % len(_PALETTE)
    return QColor(_PALETTE[index])


class ColorMapper(BaseModel):
    column: str | None = None
    colormap: str = "viridis"
    vmin: float | None = None
    vmax: float | None = None

    def __call__(self, events, catalog_color: QColor) -> dict[str, QColor]:
        if self.column is None:
            return {e.uuid: QColor(catalog_color) for e in events}

        values = [e.meta.get(self.column) for e in events]
        non_none = [v for v in values if v is not None]

        if not non_none:
            return {e.uuid: QColor(catalog_color) for e in events}

        if _is_numeric(non_none):
            return self._continuous(events, values, catalog_color)
        return self._categorical(events, values, catalog_color)

    def _continuous(self, events, values, catalog_color: QColor) -> dict[str, QColor]:
        import matplotlib
        cmap = matplotlib.colormaps[self.colormap]

        numeric = [v for v in values if v is not None and isinstance(v, (int, float))]
        lo = self.vmin if self.vmin is not None else min(numeric)
        hi = self.vmax if self.vmax is not None else max(numeric)
        span = hi - lo if hi != lo else 1.0

        result = {}
        for event, val in zip(events, values):
            if val is None or not isinstance(val, (int, float)):
                result[event.uuid] = QColor(catalog_color)
                continue
            norm = max(0.0, min(1.0, (val - lo) / span))
            r, g, b, _ = cmap(norm)
            result[event.uuid] = QColor(int(r * 255), int(g * 255), int(b * 255), _SPAN_ALPHA)
        return result

    def _categorical(self, events, values, catalog_color: QColor) -> dict[str, QColor]:
        result = {}
        for event, val in zip(events, values):
            if val is None:
                result[event.uuid] = QColor(catalog_color)
            else:
                result[event.uuid] = _hash_color(val)
        return result
