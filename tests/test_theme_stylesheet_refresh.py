"""The rendered QSS must follow the active palette, not the startup one."""
import re

import pytest

from SciQLop.components.theming import palette as palette_module
from SciQLop.components.theming.stylesheet import load_stylesheets


def _colors(qss: str) -> set[str]:
    return set(re.findall(r"#[0-9a-fA-F]{6}", qss.lower()))


@pytest.fixture
def restore_palette():
    original = palette_module.SCIQLOP_PALETTE
    yield
    palette_module.SCIQLOP_PALETTE = original


def _render(name: str) -> str:
    return load_stylesheets(palette_module.setup_palette(name), name)


def test_custom_palette_keys_follow_the_active_palette(qapp, restore_palette):
    """`palette('border')` & friends are not QPalette roles — they resolve
    through the palette dict, which must be the freshly loaded one."""
    light = _render("light")
    dark = _render("dark")

    assert palette_module.SCIQLOP_PALETTE["Border"].lower() in dark
    assert palette_module.SCIQLOP_PALETTE["Border"] == "#555555"
    assert "#c8ced6" in light, "light Border colour missing from the light QSS"


def test_no_palette_leaks_between_themes(qapp, restore_palette):
    """No colour from the space palette may survive into light or dark QSS."""
    space_only = {"#0b0e17", "#2a3358", "#6b8afd", "#8892b0"}
    for name in ("light", "dark"):
        leaked = _colors(_render(name)) & space_only
        assert not leaked, f"{name} stylesheet leaked space palette colours: {leaked}"
