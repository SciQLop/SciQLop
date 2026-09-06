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
    dialog._vmin_auto.setChecked(False)
    dialog._vmin_spin.setValue(3.25)
    assert dialog.vmin == 3.25


def test_vmin_can_represent_an_extreme_value_without_becoming_auto(qapp):
    """opencode review: an earlier design used a numeric sentinel (-1e18)
    to mean 'auto', which is itself a legitimate, representable double a
    user could genuinely want as vmin -- exactly the class of silent
    misinterpretation this whole redesign exists to prevent. 'Auto' is now
    a separate checkbox, so every representable double is a real value."""
    from SciQLop.components.catalogs.ui.colormap_dialog import ColormapDialog
    dialog = ColormapDialog()
    dialog._vmin_auto.setChecked(False)
    dialog._vmin_spin.setValue(-1e18)
    assert dialog.vmin == -1e18


def test_vmin_vmax_auto_checkbox_disables_the_spinbox(qapp):
    from SciQLop.components.catalogs.ui.colormap_dialog import ColormapDialog
    dialog = ColormapDialog(current_vmin=5.0)
    assert not dialog._vmin_auto.isChecked()
    assert dialog._vmin_spin.isEnabled()
    dialog._vmin_auto.setChecked(True)
    assert not dialog._vmin_spin.isEnabled()
    assert dialog.vmin is None


def test_dialog_preserves_a_legacy_removed_colormap_if_unchanged(qapp):
    """opencode review: dropping jet/turbo/hot from the picker must not
    silently rewrite an existing catalog's persisted colormap the moment
    someone opens this dialog and clicks OK without touching the combo --
    that's a destructive change disguised as a no-op."""
    from SciQLop.components.catalogs.ui.colormap_dialog import ColormapDialog
    dialog = ColormapDialog(current_colormap="jet")
    assert dialog.colormap == "jet"


def test_dialog_still_offers_the_recommended_colormaps_alongside_a_legacy_one(qapp):
    from SciQLop.components.catalogs.ui.colormap_dialog import ColormapDialog
    dialog = ColormapDialog(current_colormap="jet")
    items = {dialog._cmap_combo.itemText(i) for i in range(dialog._cmap_combo.count())}
    assert "viridis" in items
    assert "jet" in items
