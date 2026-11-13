"""A selected row must stay readable in every theme, also when its window is not the active one.

An inactive window (a dialog or a floating panel has the focus, or another application) draws the
selection with a translucent fill. The text kept the "highlighted text" colour, white in the light
themes, on a fill that had become pale.
"""
import re

import pytest
from PySide6.QtGui import QColor

from SciQLop.components.theming import palette as palette_module
from SciQLop.components.theming.stylesheet import load_stylesheets

from .test_autohide_tab_contrast import PALETTES, _contrast, _over, _resolve, restore_palette  # noqa: F401

VIEWS = ("QTreeView", "QListView", "QTableView")
STATES = ("active", "!active")
MIN_TEXT_CONTRAST = 4.5


def _declared(body: str, prop: str):
    found = re.search(rf"(?<![-\w]){prop}:\s*([^;]+);", body)
    return found.group(1).strip() if found else None


def _selected_row_colours(name: str, view: str, state: str) -> tuple[QColor, QColor]:
    qss = load_stylesheets(palette_module.setup_palette(name), name)
    colors = palette_module.current_palette()
    body = re.search(rf"{view}::item:selected:{re.escape(state)}\s*\{{([^}}]*)\}}", qss).group(1)
    fill = _over(_resolve(_declared(body, "background"), colors), QColor(colors["base"]))
    text = _declared(body, "color")
    return (_resolve(text, colors) if text else QColor(colors["highlightedtext"])), fill


@pytest.mark.parametrize("state", STATES)
@pytest.mark.parametrize("view", VIEWS)
@pytest.mark.parametrize("name", PALETTES)
def test_the_text_of_a_selected_row_is_readable(qapp, restore_palette, name, view, state):  # noqa: F811
    text, fill = _selected_row_colours(name, view, state)
    ratio = _contrast(text, fill)
    assert ratio >= MIN_TEXT_CONTRAST, (
        f"{name}: {view} selected row ({state}) is {ratio:.2f}:1 ({text.name()} on {fill.name()})")
