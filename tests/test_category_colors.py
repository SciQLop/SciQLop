from .fixtures import *
from dataclasses import dataclass, field

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QToolButton


@dataclass
class _Event:
    uuid: str
    meta: dict = field(default_factory=dict)


def _events():
    return [_Event("a", {"class": "solar_wind"}), _Event("b", {"class": "magnetosheath"})]


def test_category_override_applies_with_span_alpha(qapp):
    from SciQLop.components.catalogs.backend.color_mapper import ColorMapper, _hash_color
    from SciQLop.components.catalogs.backend.color_palette import _SPAN_ALPHA
    mapper = ColorMapper(column="class", category_colors={"solar_wind": "#ff0000"})
    colors = mapper(_events(), QColor("black"))
    assert (colors["a"].red(), colors["a"].green(), colors["a"].blue()) == (255, 0, 0)
    assert colors["a"].alpha() == _SPAN_ALPHA
    assert colors["b"] == _hash_color("magnetosheath")


def test_category_colors_json_roundtrip():
    from SciQLop.components.catalogs.backend.color_mapper import ColorMapper
    mapper = ColorMapper(column="class", category_colors={"x": "#00ff00"})
    loaded = ColorMapper.model_validate_json(mapper.model_dump_json())
    assert loaded.category_colors == {"x": "#00ff00"}


def test_old_json_without_category_colors_loads():
    from SciQLop.components.catalogs.backend.color_mapper import ColorMapper
    loaded = ColorMapper.model_validate_json('{"column": "class", "colormap": "viridis", "vmin": null, "vmax": null}')
    assert loaded.category_colors == {}


def _icon_rgb(button: QToolButton):
    c = button.icon().pixmap(QSize(16, 16)).toImage().pixelColor(8, 8)
    return (c.red(), c.green(), c.blue())


def _default(value: str) -> QColor:
    return QColor(10, 20, 30, 80) if value == "a" else QColor(40, 50, 60, 80)


def _dialog(qtbot, current=None):
    from SciQLop.components.catalogs.ui.category_colors_dialog import CategoryColorsDialog
    dialog = CategoryColorsDialog(["a", "b"], current or {}, _default)
    qtbot.addWidget(dialog)
    return dialog


def test_dialog_swatch_buttons_are_flat(qtbot, qapp):
    """Every other icon-only QToolButton in the app sets autoRaise so the QSS
    renders it as a flat icon; without it, QToolButton's default style paints
    a raised background+border box around the color dot (see
    QWidgets/QToolButton.qss.j2's un-autoRaise'd rule) -- the "garbage box
    around the swatch" bug."""
    dialog = _dialog(qtbot)
    assert dialog._buttons["a"].autoRaise()
    assert dialog._buttons["b"].autoRaise()


def test_dialog_initial_icons_match_default_and_current(qtbot, qapp):
    dialog = _dialog(qtbot, {"b": "#ff0000"})
    assert dialog.windowTitle() == "Category colors"
    assert _icon_rgb(dialog._buttons["a"]) == (10, 20, 30)
    assert _icon_rgb(dialog._buttons["b"]) == (255, 0, 0)
    assert dialog.category_colors == {"b": "#ff0000"}


def test_dialog_picking_color_updates_category_colors(qtbot, qapp, monkeypatch):
    dialog = _dialog(qtbot)
    monkeypatch.setattr(QColorDialog, "getColor", staticmethod(lambda *a, **k: QColor("#0000ff")))
    dialog._buttons["a"].click()
    assert dialog.category_colors == {"a": "#0000ff"}
    assert _icon_rgb(dialog._buttons["a"]) == (0, 0, 255)


def test_dialog_reset_all_clears_customizations(qtbot, qapp):
    dialog = _dialog(qtbot, {"a": "#ff0000", "b": "#00ff00"})
    dialog._reset_button.click()
    assert dialog.category_colors == {}
    assert _icon_rgb(dialog._buttons["a"]) == (10, 20, 30)


def test_dialog_cancelled_color_pick_changes_nothing(qtbot, qapp, monkeypatch):
    dialog = _dialog(qtbot, {"a": "#ff0000"})
    monkeypatch.setattr(QColorDialog, "getColor", staticmethod(lambda *a, **k: QColor()))
    dialog._buttons["a"].click()
    dialog._buttons["b"].click()
    assert dialog.category_colors == {"a": "#ff0000"}
    assert _icon_rgb(dialog._buttons["b"]) == (40, 50, 60)
