"""The auto-hide side bar must show at a glance which panel is open.

The side bar is icon-only (`AutoHideSideBarsIconOnly`) and the icons are tinted
against `palette(Base)` regardless of the tab they sit on — so the tab
background is the *only* open/closed cue. It has to clear the WCAG 3:1 floor for
non-text UI state against the side bar background (`palette(Window)`, see
QtAds.qss.j2), in every palette.
"""
import re

import pytest

from PySide6.QtGui import QColor

from SciQLop.components.theming import palette as palette_module
from SciQLop.components.theming.stylesheet import load_stylesheets

PALETTES = ["light", "dark", "neutral", "space"]
ACTIVE_TAB_RULE = r'ads--CAutoHideTab\[iconOnly="true"\]\[activeTab="true"\][^{]*\{([^}]*)\}'
MIN_CONTRAST = 3.0


@pytest.fixture
def restore_palette():
    original = palette_module.SCIQLOP_PALETTE
    yield
    palette_module.SCIQLOP_PALETTE = original


def _relative_luminance(color: QColor) -> float:
    def channel(v: float) -> float:
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = map(channel, (color.red(), color.green(), color.blue()))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a: QColor, b: QColor) -> float:
    high, low = sorted((_relative_luminance(a), _relative_luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def _over(color: QColor, background: QColor) -> QColor:
    """Flatten a translucent colour onto an opaque background."""
    a = color.alphaF()
    return QColor(*(round(bg + a * (fg - bg)) for fg, bg in
                    ((color.red(), background.red()),
                     (color.green(), background.green()),
                     (color.blue(), background.blue()))))


def _resolve(value: str, colors: dict[str, str]) -> QColor:
    role = re.fullmatch(r"palette\((\w+)\)", value)
    if role:
        return QColor(colors[role.group(1).lower()])
    rgba = re.fullmatch(r"rgba\((\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)", value)
    if rgba:
        return QColor(*map(int, rgba.groups()))
    return QColor(value)


def _active_tab_background(name: str) -> tuple[QColor, QColor]:
    qss = load_stylesheets(palette_module.setup_palette(name), name)
    colors = palette_module.current_palette()
    body = re.search(ACTIVE_TAB_RULE, qss).group(1)
    declared = re.search(r"background:\s*([^;]+);", body).group(1).strip()
    side_bar = QColor(colors["window"])
    return _over(_resolve(declared, colors), side_bar), side_bar


@pytest.mark.parametrize("name", PALETTES)
def test_open_panel_tab_stands_out_from_the_side_bar(qapp, restore_palette, name):
    active, side_bar = _active_tab_background(name)
    ratio = _contrast(active, side_bar)
    assert ratio >= MIN_CONTRAST, (
        f"{name}: open auto-hide tab is {ratio:.2f}:1 against the side bar "
        f"({active.name()} on {side_bar.name()}), below {MIN_CONTRAST}:1 — "
        "open and closed panels look the same"
    )


@pytest.mark.parametrize("name", PALETTES)
def test_icon_stays_legible_on_the_open_tab(qapp, restore_palette, name):
    """Icons are black or white, picked to contrast palette(Base) — check the
    choice still works once the tab is filled."""
    from SciQLop.components.theming.icons import opposite_color

    active, side_bar = _active_tab_background(name)
    icon = opposite_color(QColor(palette_module.current_palette()["base"]))
    ratio = _contrast(icon, active)
    assert ratio >= MIN_CONTRAST, (
        f"{name}: icon {icon.name()} on the open tab {active.name()} is "
        f"{ratio:.2f}:1, below {MIN_CONTRAST}:1"
    )
