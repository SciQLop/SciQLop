"""The rendered QSS must follow the active palette, not the startup one."""
import re

import pytest

from SciQLop.components.theming import palette as palette_module
from SciQLop.components.theming.stylesheet import load_stylesheets, qtads_stylesheet


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


def test_qtads_rules_are_not_in_the_application_stylesheet(qapp, restore_palette):
    """They must be assigned to CDockManager instead.

    QApplication.setPalette() repolishes every widget, after which QtAds widgets
    ignore application-level rules permanently — a freshly appended
    `background: red` on ads--CDockWidgetTab is simply dropped. Only a
    widget-level sheet still gets through, so the QtAds section belongs on the
    dock manager, re-assigned on every theme change (see
    SciQLopMainWindow._apply_dock_theme).
    """
    qss = load_stylesheets(palette_module.setup_palette("dark"), "dark")
    assert "ads--CDockWidgetTab" not in qss
    assert "ads--CAutoHideTab" not in qss


def test_qtads_stylesheet_carries_the_dock_rules(qapp, restore_palette):
    qss = qtads_stylesheet(palette_module.setup_palette("dark"), "dark")
    assert 'ads--CDockWidgetTab[activeTab="true"]' in qss
    assert 'ads--CAutoHideTab[iconOnly="true"][activeTab="true"]' in qss
    assert "{{" not in qss, "QtAds sheet must be fully rendered"
    assert palette_module.current_palette()["Mid"].lower() in qss.lower(), \
        "QtAds sheet must resolve against the active palette"


def test_qtads_sheet_does_not_size_icons(qapp, restore_palette):
    """qproperty-*/icon-size do not survive QApplication.setPalette(): they are
    applied once, at a widget's first polish, and no repolish brings them back.
    The auto-hide tab icon size is set from Python instead."""
    qss = qtads_stylesheet(palette_module.setup_palette("dark"), "dark")
    tab_rule = qss[qss.index("ads--CAutoHideTab:hover"):]
    tab_rule = tab_rule[:tab_rule.index("}")]
    assert "icon-size" not in tab_rule and "qproperty-iconSize" not in tab_rule
