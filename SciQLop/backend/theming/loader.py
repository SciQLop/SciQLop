import os
from functools import partial
from typing import List, Optional, Dict
from glob import glob
from PySide6 import QtGui, QtCore
from jinja2 import Template, Environment, FileSystemLoader
import SciQLop
from SciQLop.backend.sciqlop_logging import getLogger
import yaml

log = getLogger(__name__)

__background_color__ = '#ffffff'

style_sheets_path = os.path.join(SciQLop.sciqlop_root, "resources", "stylesheets")
palettes_path = os.path.join(SciQLop.sciqlop_root, "resources", "palettes")
env = Environment(loader=FileSystemLoader(style_sheets_path))


def _make_palette_case_insensitive(palette: Dict[str, str]) -> Dict[str, str]:
    palette.update({k.lower(): v for k, v in palette.items()})
    return palette


def _load_palette(palette: str) -> Dict[str, str]:
    with open(f"{palettes_path}/{palette}.yaml", 'r') as stream:
        try:
            return _make_palette_case_insensitive(yaml.safe_load(stream))
        except yaml.YAMLError as exc:
            log.error(exc)
            return {}


_sciqlop_palette = _load_palette("light")


def _list_stylesheets(folders: Optional[List[str]] = None) -> List[str]:
    if folders is None:
        folders = ["QWidgets", "QtAds"]
    style_sheets = []
    for folder in folders:
        style_sheets.extend(sorted(map(lambda f: f"{folder}/{os.path.basename(f)}",
                                       glob(os.path.join(style_sheets_path, f"{folder}/*.qss.j2")))))
    return style_sheets


def _palette(palette: QtGui.QPalette, name: str):
    if hasattr(palette, name):
        b = getattr(palette, name)()
        if isinstance(b, QtGui.QBrush):
            return b.color().name()
    if name in _sciqlop_palette:
        return _sciqlop_palette[name]
    if name.lower() in _sciqlop_palette:
        return _sciqlop_palette[name.lower()]
    return palette.base().color().name()


def _alpha(color: str, alpha: int) -> str:
    c = QtGui.QColor(color)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alpha})"


def load_stylesheets(palette: QtGui.QPalette) -> str:
    env.globals['sciqlop_list_templates'] = _list_stylesheets
    env.globals['controls_height'] = '24px'
    env.globals['palette'] = partial(_palette, palette)
    env.globals['lighter'] = lambda color, factor: QtGui.QColor(color).lighter(factor).name()
    env.globals['lighten'] = lambda color, factor: QtGui.QColor(color).lighter(factor).name()
    env.globals['darker'] = lambda color, factor: QtGui.QColor(color).darker(factor).name()
    env.globals['darken'] = lambda color, factor: QtGui.QColor(color).darker(factor).name()
    env.filters['alpha'] = _alpha
    env.filters['lighter'] = lambda color, factor: QtGui.QColor(color).lighter(factor).name()
    env.filters['lighten'] = lambda color, factor: QtGui.QColor(color).lighter(factor).name()
    env.filters['darker'] = lambda color, factor: QtGui.QColor(color).darker(factor).name()
    env.filters['darken'] = lambda color, factor: QtGui.QColor(color).darker(factor).name()
    return env.get_template("SciQLop.qss.j2").render()


def build_palette(background_color: str, palette: QtGui.QPalette) -> QtGui.QPalette:
    for role, color in _sciqlop_palette.items():
        if role in QtGui.QPalette.ColorRole.__members__:
            palette.setColor(QtGui.QPalette.ColorRole[role], QtGui.QColor(color))
    return palette
