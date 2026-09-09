import pytest
from PySide6.QtGui import QColor

from SciQLop.components.theming import palette as palette_module
from SciQLop.user_api import themes

PALETTES = [
    "light",
    "dark",
    "neutral",
    "space",
    "github_light",
    "nord_light",
    "catppuccin_latte",
    "high_contrast_light",
]


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


def test_list_themes():
    assert set(themes.list_themes()) == {
        "light",
        "dark",
        "neutral",
        "space",
        "github_light",
        "nord_light",
        "catppuccin_latte",
        "high_contrast_light",
    }


def test_apply_and_read_theme():
    themes.apply_theme("dark")
    assert themes.current_theme() == "dark"
    themes.apply_theme("light")
    assert themes.current_theme() == "light"


def test_light_palette_has_readable_ui_roles(restore_palette):
    from PySide6.QtGui import QColor
    from SciQLop.components.theming import palette

    palette.setup_palette("light")
    colors = palette.current_palette()

    assert QColor(colors["Border"]).name() == "#848e9c"
    assert QColor(colors["Selection"]).name() == "#4f46e5"
    assert colors["Highlight"] == colors["Selection"]
    assert colors["Link"] != colors["Selection"], (
        "Link must stay distinct from Highlight: one hex can't satisfy both "
        "AAA link-text contrast and the black-icon-on-Highlight floor"
    )
    assert colors["LinkVisited"] != "#ff00ff"


@pytest.mark.parametrize("name", PALETTES)
def test_border_stands_out_from_base(restore_palette, name):
    """`Border` outlines controls (QLineEdit, QToolButton, ...) and the plot
    legend over data -- WCAG 1.4.11 non-text contrast (3:1) applies, but
    nothing checked it directly until this test: 3 of 4 branded palettes
    shipped a sub-3:1 Border undetected."""
    from SciQLop.components.theming import palette

    palette.setup_palette(name)
    colors = palette.current_palette()
    ratio = _contrast(QColor(colors["Border"]), QColor(colors["Base"]))
    assert ratio >= 3.0, f"{name}: Border {colors['Border']} on Base {colors['Base']} is {ratio:.2f}:1"


@pytest.mark.parametrize("name", PALETTES)
def test_highlighted_text_is_readable_on_highlight(restore_palette, name):
    """Every selected row/item's text must clear WCAG AA (4.5:1) against its
    own Highlight fill."""
    from SciQLop.components.theming import palette

    palette.setup_palette(name)
    colors = palette.current_palette()
    ratio = _contrast(QColor(colors["HighlightedText"]), QColor(colors["Highlight"]))
    assert ratio >= 4.5, (
        f"{name}: HighlightedText {colors['HighlightedText']} on Highlight "
        f"{colors['Highlight']} is {ratio:.2f}:1"
    )
