from pathlib import Path
from PySide6.QtGui import QIcon, QIconEngine, QColor, QPixmap, QPainter, QPalette, QImage
from PySide6.QtCore import QSize, QRect, QPoint, Qt
from SciQLopPlots import Icons
from PySide6.QtWidgets import QApplication
from SciQLop.components.storage import cache_dir
from SciQLop.components.sciqlop_logging import getLogger

log = getLogger(__name__)


def per_palette_icon_dir(palette_name: str) -> Path:
    """Returns the directory where icons adapted to the given palette are stored."""
    return cache_dir(f"icons/{palette_name}")


def per_palette_icon_name(name: str, palette_name: str) -> str:
    """Returns the name of the icon adapted to the given palette."""
    return f"{name}_{palette_name}"


_deferred_icons: list[tuple[str, callable]] = []


def register_icon(name: str, icon_or_factory):
    """Register a named icon. If QApplication doesn't exist yet, defers
    registration until flush_deferred_icons() is called.

    icon_or_factory can be a QIcon or a callable returning a QIcon.
    When called at module level before QApp, pass a lambda to avoid
    constructing QIcon/QPixmap too early, or pass a QIcon directly
    and this function will defer the add_icon call.
    """
    if QApplication.instance() is not None:
        icon = icon_or_factory() if callable(icon_or_factory) else icon_or_factory
        Icons.add_icon(name, icon)
    else:
        if callable(icon_or_factory):
            _deferred_icons.append((name, icon_or_factory))
        else:
            # icon is already a QIcon constructed (somehow) before QApp — wrap it
            _deferred_icons.append((name, lambda i=icon_or_factory: i))


def flush_deferred_icons():
    """Register all icons that were deferred because QApplication didn't exist."""
    while _deferred_icons:
        name, factory = _deferred_icons.pop(0)
        Icons.add_icon(name, factory())


def _transparent_argb(size: QSize, dpr: float) -> QPixmap:
    """A transparent ARGB32 pixmap of *size* device pixels at *dpr*.

    A screen-format ``QPixmap(size)`` inherits the framebuffer's color depth —
    under a 16-bit display (e.g. headless xvfb) that is RGB16, which has no
    alpha channel and silently ignores ``setDevicePixelRatio``. Building from an
    explicit ARGB32 image keeps alpha and DPR regardless of the display depth.
    """
    image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    image.setDevicePixelRatio(dpr)
    image.fill(Qt.GlobalColor.transparent)
    return QPixmap.fromImage(image)


def _tinted(pixmap: QPixmap, color: QColor) -> QPixmap:
    """Recolor every opaque pixel of *pixmap* to *color*, preserving the source
    alpha (so anti-aliased edges stay smooth) and its devicePixelRatio.

    Resolution-independent and GPU-friendly: a ``CompositionMode_SourceIn``
    fill instead of a per-pixel Python loop, so it works at any size/DPR.
    """
    out = _transparent_argb(pixmap.size(), pixmap.devicePixelRatio())
    painter = QPainter(out)
    painter.drawPixmap(0, 0, pixmap)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(out.rect(), color)
    painter.end()
    return out


def opposite_color(color: QColor) -> QColor:
    """Return a color (black or white) that has the best perceived contrast against the
    provided background `color`.

    This uses the WCAG relative luminance / contrast ratio calculation to pick the
    color (either opaque black or white) which yields the higher contrast ratio.

    Parameters
    ----------
    color : QColor
        Background color to contrast against.

    Returns
    -------
    QColor
        Either QColor(0, 0, 0) or QColor(255, 255, 255), chosen to maximise contrast.
    """
    # Guard: invalid color -> default to black
    if not color.isValid():
        return QColor(0, 0, 0)

    # Use sRGB channels in [0,1]
    r = color.redF()
    g = color.greenF()
    b = color.blueF()

    # Convert sRGB to linear RGB for luminance (per WCAG)
    def linearize(c: float) -> float:
        if c <= 0.03928:
            return c / 12.92
        return ((c + 0.055) / 1.055) ** 2.4

    lr = linearize(r)
    lg = linearize(g)
    lb = linearize(b)

    # Relative luminance
    L = 0.2126 * lr + 0.7152 * lg + 0.0722 * lb

    # Contrast ratios with white and black
    # contrast = (L_lighter + 0.05) / (L_darker + 0.05)
    contrast_with_white = (1.0 + 0.05) / (L + 0.05)
    contrast_with_black = (L + 0.05) / (0.0 + 0.05)

    # Prefer the color with the higher contrast ratio
    if contrast_with_white >= contrast_with_black:
        return QColor(255, 255, 255)
    return QColor(0, 0, 0)


def _app_base_color() -> QColor:
    """Return the application's base palette color, with a safe fallback if no app exists."""
    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app.palette().color(QPalette.ColorRole.Base)
    # fallback to white which is a safe default for most light backgrounds
    return QColor(255, 255, 255)


class _ThemeIconEngine(QIconEngine):
    """Tints a registered icon to contrast the current palette. All rendering
    flows through paint(), which draws the source at the painter's device
    resolution — so a scalable (SVG) source stays crisp at any DPI, per the
    QIconEngine contract (Qt 6.11)."""

    def __init__(self, name: str):
        super().__init__()
        self._name = name

    def paint(self, painter: QPainter, rect: QRect, mode, state):
        dpr = painter.device().devicePixelRatioF()
        device = QSize(round(rect.width() * dpr), round(rect.height() * dpr))
        source = Icons.get_icon(self._name).pixmap(device)
        tinted = _tinted(source, opposite_color(_app_base_color()))
        tinted.setDevicePixelRatio(dpr)
        painter.drawPixmap(rect, tinted)

    def pixmap(self, size: QSize, mode, state) -> QPixmap:
        return self.scaledPixmap(size, mode, state, 1.0)

    def scaledPixmap(self, size: QSize, mode, state, scale: float) -> QPixmap:
        # `size` is device-independent (Qt >= 6.8); produce a scale-aware target
        # and let paint() fill it at the right device resolution.
        device = QSize(round(size.width() * scale), round(size.height() * scale))
        pixmap = _transparent_argb(device, scale)
        painter = QPainter(pixmap)
        self.paint(painter, QRect(QPoint(0, 0), size), mode, state)
        painter.end()
        return pixmap

    def clone(self) -> QIconEngine:
        return _ThemeIconEngine(self._name)


def theme_icon(name: str) -> QIcon:
    """Return an icon that re-tints to the current palette on every paint and
    stays crisp at any DPI."""
    return QIcon(_ThemeIconEngine(name))


def theme_adapted_icon(name: str) -> QIcon:
    """Alias of :func:`theme_icon`, kept for callers that used the
    registry-based variant before the two engines were unified."""
    return QIcon(_ThemeIconEngine(name))


def get_icon(name: str, auto_adapt_colors=True) -> QIcon:
    if auto_adapt_colors:
        return QIcon(_ThemeIconEngine(name))
    return Icons.get_icon(name)


def _is_theme_icon(path: str) -> bool:
    return ":/icons/theme/" in path or "://icons/theme/" in path


def build_icon_set_for_palette(palette_name: str, base_color: str or QColor):
    """Bake palette-recolored PNGs that the stylesheet references via ``url()``
    (a Qt stylesheet can neither tint nor rescale a registry QIcon). Each theme
    icon is written at @1x and @2x so the QSS indicators stay crisp on HiDPI;
    the source extension is irrelevant — SVG sources just render sharper."""
    if isinstance(base_color, str):
        base_color = QColor(base_color)
    dest_color = opposite_color(base_color)
    out_dir = per_palette_icon_dir(palette_name)
    for path in filter(_is_theme_icon, Icons.icons()):
        _bake_recolored_icon(Icons.get_icon(path), Path(path).stem, dest_color, out_dir)


def _bake_recolored_icon(source: QIcon, name: str, color: QColor, out_dir: Path) -> None:
    for scale, suffix in ((1, ""), (2, "@2x")):
        size = QSize(24 * scale, 24 * scale)
        pixmap = source.pixmap(size)
        if not pixmap.isNull() and pixmap.size() != size:
            pixmap = pixmap.scaled(
                size, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        _tinted(pixmap, color).save(str(out_dir / f"{name}{suffix}.png"))


def list_icons() -> list[str]:
    """Returns a dictionary of all registered icons, mapping their name to their path."""
    return Icons.icons()


def get_current_style_icon(name: str) -> QIcon:
    from .settings import SciQLopStyle
    return QIcon(str(per_palette_icon_dir(palette_name=SciQLopStyle().color_palette) / f"{name}.png"))
