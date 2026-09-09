"""The plot's minor grid line must stay visible against Base.

`Midlight` is tuned for chrome (QtAds hover fills, near-Base tones) and sits
at ~1.05-1.16:1 contrast against `Base` in every palette — using it directly
as the plot's sub-grid colour makes the minor grid invisible everywhere. A
50% mix of `Mid` toward `Base` gives a consistent, visible faintness instead.
"""

from PySide6.QtGui import QColor

from SciQLop.components.plotting.ui.time_sync_panel import _theme_from_palette

_PALETTE = {
    "Base": "#ffffff",
    "Text": "#000000",
    "Mid": "#d4d9e1",
    "Midlight": "#f1f3f6",
    "Highlight": "#4f46e5",
    "Border": "#848e9c",
    "Window": "#f8f9fb",
}


def test_sub_grid_is_a_mix_of_mid_and_base():
    theme = _theme_from_palette(_PALETTE)
    assert theme.sub_grid().name() == "#eaecf0"


def test_sub_grid_is_not_the_raw_midlight_value():
    theme = _theme_from_palette(_PALETTE)
    assert theme.sub_grid().name() != QColor(_PALETTE["Midlight"]).name()
