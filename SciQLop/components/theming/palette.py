from PySide6 import QtGui
from PySide6.QtCore import QDirIterator
from PySide6.QtGui import QColor
from seaborn import color_palette as color_palette

from .settings import SciQLopStyle
from .icons import build_icon_set_for_palette
from SciQLop.components.sciqlop_logging import getLogger
from .themes import DEFAULT_THEME, THEMES, palettes_path  # noqa: F401

log = getLogger(__name__)

__background_color__ = '#ffffff'

def _make_palette_case_insensitive(palette: dict[str, str]) -> dict[str, str]:
    palette.update({k.lower(): v for k, v in palette.items()})
    return palette


def _resolve(name: str) -> str:
    return name if name in THEMES else DEFAULT_THEME


_active_theme = _resolve(SciQLopStyle().color_palette)


def _load_palette(name: str) -> dict[str, str]:
    try:
        return _make_palette_case_insensitive(THEMES.get(_resolve(name)).colors())
    except ValueError as e:  # a core palette file broken on disk
        log.error(e)
        return _make_palette_case_insensitive(THEMES.get(DEFAULT_THEME).colors())


def active_theme_name() -> str:
    """The theme actually shown: the requested one, or the default while it is not contributed."""
    return _active_theme


SCIQLOP_PALETTE = _load_palette(_active_theme)


def current_palette() -> dict[str, str]:
    """The palette dict of the active theme.

    Always call this instead of importing `SCIQLOP_PALETTE` at module level:
    `setup_palette()` rebinds the global to a *new* dict on every theme change,
    so an imported reference is frozen at the startup theme.
    """
    return SCIQLOP_PALETTE


def _muted_text(palette: dict[str, str]) -> QColor:
    """The colour of hints and placeholders: the theme's own, else its
    unselected-text colour, else its text colour blended halfway into the
    background. Qt's default is half-transparent black, unreadable on dark themes."""
    for role in ("PlaceholderText", "UnselectedText"):
        if role in palette:
            return QColor(palette[role])
    text, base = QColor(palette.get("Text", "#000000")), QColor(palette.get("Base", "#ffffff"))
    return QColor(*((t + b) // 2 for t, b in zip(text.getRgb()[:3], base.getRgb()[:3])))


def build_palette(palette: dict[str, str]) -> QtGui.QPalette:
    qpalette = QtGui.QPalette()
    qpalette.setColor(QtGui.QPalette.ColorRole.PlaceholderText, _muted_text(palette))
    for role, color in palette.items():
        if role in QtGui.QPalette.ColorRole.__members__:
            qpalette.setColor(QtGui.QPalette.ColorRole[role], QtGui.QColor(color))
    return qpalette


def setup_palette(palette_name: str) -> QtGui.QPalette:
    """Load the named palette (the default when it is not contributed), rebuild icons, and return a QPalette."""
    global SCIQLOP_PALETTE, _active_theme
    _active_theme = _resolve(palette_name)
    SCIQLOP_PALETTE = _load_palette(_active_theme)
    qpalette = build_palette(SCIQLOP_PALETTE)
    build_icon_set_for_palette(_active_theme, qpalette.base().color(),
                               {"accent": qpalette.highlight().color(), "muted": _muted_text(SCIQLOP_PALETTE)})
    return qpalette
