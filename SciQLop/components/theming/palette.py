import os
from PySide6 import QtGui
from PySide6.QtCore import QDirIterator
from PySide6.QtGui import QColor
from seaborn import color_palette as color_palette

import SciQLop
from .settings import SciQLopStyle
from .icons import build_icon_set_for_palette
from SciQLop.components.sciqlop_logging import getLogger
import yaml

log = getLogger(__name__)

__background_color__ = '#ffffff'

palettes_path = os.path.join(SciQLop.sciqlop_root, "resources", "palettes")


def _make_palette_case_insensitive(palette: dict[str, str]) -> dict[str, str]:
    palette.update({k.lower(): v for k, v in palette.items()})
    return palette


def _load_palette(palette: str) -> dict[str, str]:
    with open(f"{palettes_path}/{palette}.yaml", 'r') as stream:
        try:
            return _make_palette_case_insensitive(yaml.safe_load(stream))
        except yaml.YAMLError as exc:
            log.error(exc)
            return {}


SCIQLOP_PALETTE = _load_palette(SciQLopStyle().color_palette)


def build_palette(palette: dict[str, str]) -> QtGui.QPalette:
    qpalette = QtGui.QPalette()
    for role, color in palette.items():
        if role in QtGui.QPalette.ColorRole.__members__:
            qpalette.setColor(QtGui.QPalette.ColorRole[role], QtGui.QColor(color))
    return qpalette


def setup_palette(palette_name: str) -> QtGui.QPalette:
    """Load the named palette, rebuild icons, and return a QPalette."""
    global SCIQLOP_PALETTE
    SCIQLOP_PALETTE = _load_palette(palette_name)
    qpalette = build_palette(SCIQLOP_PALETTE)
    build_icon_set_for_palette(palette_name, qpalette.base().color())
    return qpalette
