"""On macOS the native tab close glyph of the selected tab is drawn light, for the native dark
selected tab; with QTabBar::tab restyled to the base colour it vanished (QTBUG-61092). The close
button must have its own themed image."""

import re
from pathlib import Path

import pytest

from SciQLop.components.theming import palette as palette_module
from SciQLop.components.theming.stylesheet import load_stylesheets


@pytest.fixture
def restore_palette():
    original = palette_module.SCIQLOP_PALETTE
    yield
    palette_module.SCIQLOP_PALETTE = original


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_tab_close_button_has_a_themed_image(qapp, restore_palette, theme):
    qss = load_stylesheets(palette_module.setup_palette(theme), theme)

    rule = re.search(r"QTabBar::close-button\s*\{([^}]*)\}", qss)

    assert rule, "no QTabBar::close-button rule"
    image = re.search(r"image:\s*url\(([^)]+)\)", rule.group(1))
    assert image and Path(image.group(1)).is_file()
