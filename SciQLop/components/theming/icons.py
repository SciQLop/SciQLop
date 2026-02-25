from pathlib import Path
from PySide6.QtGui import QIcon, QColor, QPixmap, QPalette
from PySide6.QtCore import QSize
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


def register_icon(name: str, icon: QIcon):
    Icons.add_icon(name, icon)


def _mutate_icon_color(icon: QIcon, color: QColor) -> QIcon:
    """Replaces the black pixels of the icon with the given color, while keeping the transparency and the white pixels unchanged

    Parameters
    ----------
    icon : QIcon
        The icon to mutate
    color : QColor
        The color to replace the black pixels with
    """
    if len(icon.availableSizes()) == 0:
        size = QSize(24, 24)
    else:
        size = icon.availableSizes()[0]
    pixmap = icon.pixmap(size)
    image = pixmap.toImage()
    for x in range(image.width()):
        for y in range(image.height()):
            c = image.pixelColor(x, y)
            if c.alpha() != 0:
                image.setPixelColor(x, y, color)
    return QIcon(QPixmap.fromImage(image))


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


def get_icon(name: str, auto_adapt_colors=True) -> QIcon:
    icon = Icons.get_icon(name)
    if auto_adapt_colors:
        return _mutate_icon_color(icon,
                                  opposite_color(_app_base_color()))
    else:
        return icon


def _is_theme_icon(name: str) -> bool:
    return "://icons/theme/" in name or ":/icons/theme/" in name


def build_icon_set_for_palette(palette_name: str, base_color: str or QColor):
    """Generates a variant of the default icon set with colors adapted to the given palette."""
    if type(base_color) is str:
        base_color = QColor(base_color)
    icons = filter(_is_theme_icon, Icons.icons())
    for icon in icons:
        if '/' in icon:
            name = icon.split("/")[-1].split(".png")[0]
        else:
            name = icon.split(":")[-1].split(".png")[0]
        destination_path = per_palette_icon_dir(palette_name) / f"{name}.png"
        dest_color = opposite_color(base_color)
        if not destination_path.exists():
            mutated_icon = _mutate_icon_color(get_icon(icon, auto_adapt_colors=False), dest_color)
            if 'theme' in name:
                name = name.split("://icons/theme/")[-1].split(".png")[0]
            mutated_icon.pixmap(QSize(24, 24)).save(str(per_palette_icon_dir(palette_name) / f"{name}.png"))


def list_icons() -> list[str]:
    """Returns a dictionary of all registered icons, mapping their name to their path."""
    return Icons.icons()


def get_current_style_icon(name: str) -> QIcon:
    from .settings import SciQLopStyle
    return QIcon(str(per_palette_icon_dir(palette_name=SciQLopStyle().color_palette) / f"{name}.png"))
