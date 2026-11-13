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


def _relative_luminance(color: QColor) -> float:
    """WCAG relative luminance of `color`, sRGB channels linearized first."""
    def linearize(c: float) -> float:
        if c <= 0.03928:
            return c / 12.92
        return ((c + 0.055) / 1.055) ** 2.4

    return (0.2126 * linearize(color.redF()) +
            0.7152 * linearize(color.greenF()) +
            0.0722 * linearize(color.blueF()))


def opposite_color(*colors: QColor) -> QColor:
    """Return a color (black or white) with the best worst-case perceived
    contrast against every color in `colors`.

    A single color picks whichever of black/white contrasts it best. Several
    colors (e.g. a fill and the background it sits on) can each favor the
    opposite choice — a contour drawn only against the fill can vanish into a
    same-lightness background. Passing every surface the color must read
    against picks the choice that maximises the *smallest* of the resulting
    contrast ratios, so it stays legible against all of them at once.

    Uses the WCAG relative luminance / contrast ratio calculation.

    Parameters
    ----------
    *colors : QColor
        Surface color(s) to contrast against.

    Returns
    -------
    QColor
        Either QColor(0, 0, 0) or QColor(255, 255, 255), chosen to maximise
        the worst-case contrast ratio.
    """
    luminances = [_relative_luminance(c) for c in colors if c.isValid()]
    if not luminances:
        return QColor(0, 0, 0)

    def worst_case_contrast(candidate_luminance: float) -> float:
        return min((max(candidate_luminance, L) + 0.05) / (min(candidate_luminance, L) + 0.05)
                   for L in luminances)

    if worst_case_contrast(1.0) >= worst_case_contrast(0.0):
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


# Drawn in more than the one contrast colour: ticked in the accent colour, empty in the muted one.
_INDICATOR_ICONS = ("check_box_checked", "check_box_unchecked", "radio_button_checked", "radio_button_unchecked")


def build_icon_set_for_palette(palette_name: str, base_color: str or QColor, indicator_colors: dict | None = None):
    """Bake palette-recolored PNGs that the stylesheet references via ``url()``
    (a Qt stylesheet can neither tint nor rescale a registry QIcon). Each theme
    icon is written at @1x and @2x so the QSS indicators stay crisp on HiDPI;
    the source extension is irrelevant — SVG sources just render sharper.
    `indicator_colors` maps a suffix to a colour: the checkbox and radio indicators are also
    written as `<name>_<suffix>.png` in that colour."""
    if isinstance(base_color, str):
        base_color = QColor(base_color)
    dest_color = opposite_color(base_color)
    out_dir = per_palette_icon_dir(palette_name)
    for path in filter(_is_theme_icon, Icons.icons()):
        _bake_recolored_icon(Icons.get_icon(path), Path(path).stem, dest_color, out_dir)
    _bake_mirrored(out_dir, "arrow_right", "arrow_left")
    for name in ("arrow_drop_up", "arrow_drop_down"):
        _bake_trimmed(out_dir, name, f"{name}_tight")
    for variant, color in (indicator_colors or {}).items():
        for name in _INDICATOR_ICONS:
            _bake_recolored_icon(get_icon(name, auto_adapt_colors=False), f"{name}_{variant}", QColor(color), out_dir)


def _drawn_rect(image: QImage) -> QRect:
    drawn = [(x, y) for y in range(image.height()) for x in range(image.width()) if image.pixelColor(x, y).alpha() > 0]
    xs, ys = [x for x, _ in drawn], [y for _, y in drawn]
    return QRect(QPoint(min(xs), min(ys)), QPoint(max(xs), max(ys))) if drawn else image.rect()


def _bake_trimmed(out_dir: Path, name: str, trimmed_name: str) -> None:
    """The icon without its empty margins. A spin box arrow has half the height of the field: the 24 px
    icon, two thirds of it margin, came out as a speck with clipped edges."""
    for suffix in ("", "@2x"):
        image = QImage(str(out_dir / f"{name}{suffix}.png"))
        if not image.isNull():
            image.copy(_drawn_rect(image)).save(str(out_dir / f"{trimmed_name}{suffix}.png"))


def _bake_mirrored(out_dir: Path, name: str, mirrored_name: str) -> None:
    """The icon set has no left arrow: the calendar's "previous month" button uses the right one, flipped."""
    for suffix in ("", "@2x"):
        image = QImage(str(out_dir / f"{name}{suffix}.png"))
        if not image.isNull():
            image.flipped(Qt.Orientation.Horizontal).save(str(out_dir / f"{mirrored_name}{suffix}.png"))


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
    from .palette import active_theme_name
    return QIcon(str(per_palette_icon_dir(palette_name=active_theme_name()) / f"{name}.png"))
