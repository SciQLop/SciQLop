import os
from functools import partial
from typing import List, Optional
from glob import glob
from PySide6 import QtGui, QtCore
from jinja2 import Template, Environment, FileSystemLoader
import SciQLop

__background_color__ = '#ffffff'

style_sheets_path = os.path.join(SciQLop.sciqlop_root, "resources", "stylesheets")
env = Environment(loader=FileSystemLoader(style_sheets_path))

__light_palette__ = {
    "Window": "#ffffff",
    "WindowText": "#000000",
    "Base": "#ffffff",
    "AlternateBase": "#eef2f7",
    "ToolTipBase": "#ffffff",
    "ToolTipText": "#000000",
    "Text": "#000000",
    "Button": "#eef2f7",
    "ButtonText": "#000000",
    "BrightText": "#ffffff",
    "Light": "#ffffff",
    "Midlight": "#ffffff",
    "Mid": "#eef2f7",
    "Dark": "#eef2f7",
    "Shadow": "#eef2f7",
    "Highlight": "#6a68d4",
    "HighlightedText": "#ffffff",
    "Link": "#0000ff",
    "LinkVisited": "#ff00ff",

    "WelcomeBackground": "#eef2f7",
    "Borders": "#6c757d",
    "Selection": "#6a68d4",
    "UnselectedText": "#9eadb2",
}

__light_palette_case_insensitive__ = {k.lower(): v for k, v in __light_palette__.items()}


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
    if name in __light_palette__:
        return __light_palette__[name]
    if name.lower() in __light_palette_case_insensitive__:
        return __light_palette_case_insensitive__[name.lower()]
    return palette.base().color().name()


def _alpha(color: str, alpha: int) -> str:
    c = QtGui.QColor(color)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alpha})"


def load_stylesheets(palette: QtGui.QPalette) -> str:
    env.globals['sciqlop_list_templates'] = _list_stylesheets
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
    for role, color in __light_palette__.items():
        if role in QtGui.QPalette.ColorRole.__members__:
            palette.setColor(QtGui.QPalette.ColorRole[role], QtGui.QColor(color))
    return palette
