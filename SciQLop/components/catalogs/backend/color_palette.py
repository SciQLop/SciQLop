from functools import lru_cache
from hashlib import md5
from typing import ClassVar

from PySide6.QtCore import QObject, QRect, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QIconEngine, QPainter

from SciQLop.components.settings.backend.entry import ConfigEntry, SettingsCategory

# Paul Tol's colorblind-safe "muted" qualitative scheme (9 colors, 80 alpha
# for span fill). Replaces a tab10-derived set that paired a near-pure red
# (214,39,40) with a near-pure green (44,160,44) -- the classic red-green
# confusion pair, with real odds of both landing on-screen at once (~40%
# with just 4 hash-assigned catalogs). See https://sronpersonalpages.nl/~pault/
_PALETTE = [
    QColor(51, 34, 136, 80),    # indigo
    QColor(136, 204, 238, 80),  # cyan
    QColor(68, 170, 153, 80),   # teal
    QColor(17, 119, 51, 80),    # green
    QColor(153, 153, 51, 80),   # olive
    QColor(221, 204, 119, 80),  # sand
    QColor(204, 102, 119, 80),  # rose
    QColor(136, 34, 85, 80),    # wine
    QColor(170, 68, 153, 80),   # purple
]


_SPAN_ALPHA = 80


class CatalogColors(ConfigEntry):
    """User-picked catalog colors, keyed by catalog uuid. UI state kept
    outside the catalog (like EventTableViewState) so read-only providers
    get it too."""
    category: ClassVar[str] = SettingsCategory.CATALOGS
    subcategory: ClassVar[str] = "Colors"
    colors: dict[str, str] = {}


class _CatalogColorNotifier(QObject):
    changed = Signal(str)


_notifier = _CatalogColorNotifier()
catalog_color_changed = _notifier.changed
# Loaded once on first use: color_for_catalog runs on every tree repaint,
# and a ConfigEntry re-reads its YAML file on each construction.
_overrides: dict[str, str] | None = None


def _custom_colors() -> dict[str, str]:
    global _overrides
    if _overrides is None:
        _overrides = dict(CatalogColors().colors)
    return _overrides


@lru_cache(maxsize=None)
def _hash_color(uuid: str) -> QColor:
    # md5 is stable across processes, unlike hash() which is randomized per-process
    index = int.from_bytes(md5(uuid.encode()).digest()[:4], "little") % len(_PALETTE)
    return _PALETTE[index]


def color_for_catalog(uuid: str) -> QColor:
    custom = _custom_colors().get(uuid)
    if custom is None:
        return QColor(_hash_color(uuid))
    color = QColor(custom)
    color.setAlpha(_SPAN_ALPHA)
    return color


def has_custom_color(uuid: str) -> bool:
    return uuid in _custom_colors()


def set_catalog_color(uuid: str, color: QColor | None) -> None:
    """Persist a user-picked color for this catalog (None restores the
    palette default) and notify every tree and panel overlay."""
    overrides = _custom_colors()
    with CatalogColors() as settings:
        if color is None:
            overrides.pop(uuid, None)
            settings.colors.pop(uuid, None)
        else:
            overrides[uuid] = QColor(color).name()
            settings.colors[uuid] = overrides[uuid]
    catalog_color_changed.emit(uuid)


class _CatalogSwatchIconEngine(QIconEngine):
    """Paints a filled dot in a catalog's color, at the painter's device
    resolution -- like theming/icons.py's _ThemeIconEngine, rendering
    on demand keeps this crisp at any DPI without baking a fixed-size
    pixmap (and needs no cache: the engine itself holds only a QColor)."""

    def __init__(self, color: QColor):
        super().__init__()
        self._color = color

    def paint(self, painter: QPainter, rect: QRect, mode, state):
        # No custom pixmap()/scaledPixmap(): QIconEngine's default pixmap()
        # already builds a proper ARGB32_Premultiplied buffer and calls
        # paint() on it -- exactly the DPR-safe pattern
        # theming/icons.py's _transparent_argb exists to guarantee by hand.
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._color)
        margin = max(1, min(rect.width(), rect.height()) // 12)
        painter.drawEllipse(rect.adjusted(margin, margin, -margin, -margin))
        painter.restore()

    def clone(self) -> QIconEngine:
        return _CatalogSwatchIconEngine(self._color)


def catalog_swatch_icon(uuid: str) -> QIcon:
    """A small filled dot in this catalog's color, for the tree row --
    cheap legend so 'which color is which catalog' is answerable without
    hovering an event on the plot (the only place the color was visible
    before this)."""
    color = QColor(color_for_catalog(uuid))
    color.setAlpha(255)
    return QIcon(_CatalogSwatchIconEngine(color))
