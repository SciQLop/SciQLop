"""ColormapDialog (2026-09-06 review): drop non-perceptually-uniform
colormaps from the picker, and replace the free-text vmin/vmax QLineEdits
(a typo silently fell back to "auto" with no feedback) with QDoubleSpinBox
so invalid input can't be typed in the first place.
"""
from .fixtures import *


def test_removed_colormaps_are_gone(qapp):
    from SciQLop.components.catalogs.ui.colormap_dialog import ColormapDialog
    dialog = ColormapDialog()
    items = {dialog._cmap_combo.itemText(i) for i in range(dialog._cmap_combo.count())}
    assert "jet" not in items
    assert "turbo" not in items
    assert "hot" not in items


def test_perceptually_uniform_colormaps_kept(qapp):
    from SciQLop.components.catalogs.ui.colormap_dialog import ColormapDialog
    dialog = ColormapDialog()
    items = {dialog._cmap_combo.itemText(i) for i in range(dialog._cmap_combo.count())}
    for name in ("viridis", "plasma", "inferno", "magma", "cividis", "coolwarm", "RdBu"):
        assert name in items


def test_vmin_vmax_default_to_auto(qapp):
    from SciQLop.components.catalogs.ui.colormap_dialog import ColormapDialog
    dialog = ColormapDialog()
    assert dialog.vmin is None
    assert dialog.vmax is None


def test_vmin_vmax_preset_from_current_values(qapp):
    from SciQLop.components.catalogs.ui.colormap_dialog import ColormapDialog
    dialog = ColormapDialog(current_vmin=1.5, current_vmax=42.0)
    assert dialog.vmin == 1.5
    assert dialog.vmax == 42.0


def test_vmin_vmax_cannot_hold_invalid_text(qapp):
    """The old QLineEdit accepted any text and silently returned None (=
    auto) for anything that didn't parse as a float, with zero feedback
    that the input was rejected. A QDoubleSpinBox can't hold non-numeric
    text at all -- there's no invalid state to silently swallow."""
    from SciQLop.components.catalogs.ui.colormap_dialog import ColormapDialog
    dialog = ColormapDialog()
    dialog._vmin_spin.setValue(3.25)
    assert dialog.vmin == 3.25
    # Setting back toward -infinity clamps to the auto sentinel, not a typo.
    dialog._vmin_spin.setValue(-1e30)
    assert dialog.vmin is None
