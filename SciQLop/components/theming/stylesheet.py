import os
from functools import partial
from typing import List, Optional, Dict
from glob import glob
from PySide6 import QtGui, QtCore
from jinja2 import Template, Environment, FileSystemLoader
from seaborn import color_palette

import SciQLop
from SciQLop.components.sciqlop_logging import getLogger
from .palette import SCIQLOP_PALETTE

log = getLogger(__name__)

__background_color__ = '#ffffff'

style_sheets_path = os.path.join(SciQLop.sciqlop_root, "resources", "stylesheets")
env = Environment(loader=FileSystemLoader(style_sheets_path))


def _list_stylesheets(folders: Optional[List[str]] = None) -> List[str]:
    if folders is None:
        folders = ["QWidgets", "QtAds"]
    style_sheets = []
    for folder in folders:
        style_sheets.extend(sorted(map(lambda f: f"{folder}/{os.path.basename(f)}",
                                       glob(os.path.join(style_sheets_path, f"{folder}/*.qss.j2")))))
    return style_sheets


def _alpha(color: str, alpha: int) -> str:
    c = QtGui.QColor(color)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alpha})"


def _palette(palette: QtGui.QPalette, name: str):
    if hasattr(palette, name):
        b = getattr(palette, name)()
        if isinstance(b, QtGui.QBrush):
            return b.color().name()
    if name in SCIQLOP_PALETTE:
        return SCIQLOP_PALETTE[name]
    if name.lower() in SCIQLOP_PALETTE:
        return SCIQLOP_PALETTE[name.lower()]
    return palette.base().color().name()


def _icon(palette_name: str, name: str) -> str:
    from .icons import per_palette_icon_dir
    # Use as_posix() so backslashes on Windows don't break CSS url() parsing
    return f"url({(per_palette_icon_dir(palette_name) / f'{name}.png').as_posix()})"


def load_stylesheets(palette: QtGui.QPalette, palette_name: str) -> str:
    env.globals['sciqlop_list_templates'] = _list_stylesheets
    env.globals['controls_height'] = '2.4ex'
    env.globals['palette'] = partial(_palette, palette)
    env.globals['lighter'] = lambda color, factor: QtGui.QColor(color).lighter(factor).name()
    env.globals['lighten'] = lambda color, factor: QtGui.QColor(color).lighter(factor).name()
    env.globals['darker'] = lambda color, factor: QtGui.QColor(color).darker(factor).name()
    env.globals['darken'] = lambda color, factor: QtGui.QColor(color).darker(factor).name()
    env.globals['icon'] = partial(_icon, palette_name)
    env.filters['alpha'] = _alpha
    env.filters['lighter'] = lambda color, factor: QtGui.QColor(color).lighter(factor).name()
    env.filters['lighten'] = lambda color, factor: QtGui.QColor(color).lighter(factor).name()
    env.filters['darker'] = lambda color, factor: QtGui.QColor(color).darker(factor).name()
    env.filters['darken'] = lambda color, factor: QtGui.QColor(color).darker(factor).name()
    env.filters['icon'] = partial(_icon, palette_name)
    return env.get_template("SciQLop.qss.j2").render()
