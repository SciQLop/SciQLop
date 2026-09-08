"""Catalog color actions shared by the catalog tree's context menu and the
plot panel's Catalogs menu: pick/reset the catalog color, and the
"Color by..." submenu (column choice, colormap, category colors).
"""
from __future__ import annotations

from PySide6.QtWidgets import QColorDialog, QMenu, QWidget

from SciQLop.components.catalogs.backend.color_mapper import ColorMapper, _hash_color, _is_numeric
from SciQLop.components.catalogs.backend.color_mapper_storage import get_color_mapper, set_color_mapper
from SciQLop.components.catalogs.backend.color_palette import (
    color_for_catalog, has_custom_color, set_catalog_color,
)
from SciQLop.components.catalogs.backend.provider import Catalog
from SciQLop.components.sciqlop_logging import getLogger

log = getLogger(__name__)

EVENT_SAMPLE_SIZE = 200


def sample_events(catalog: Catalog, report_failure=None) -> list:
    """A bounded read of the catalog's events for menu building; a backend
    failure is reported (or logged) instead of aborting the menu."""
    if catalog.provider is None:
        return []
    try:
        return list(catalog.provider.events(catalog)[:EVENT_SAMPLE_SIZE])
    except Exception as e:
        if report_failure is not None:
            report_failure(f"Could not load columns for '{catalog.name}'", e)
        else:
            log.warning("Could not load columns for '%s': %s", catalog.name, e)
        return []


def pick_catalog_color(catalog: Catalog, dialog_parent: QWidget | None) -> None:
    current = color_for_catalog(catalog.uuid)
    current.setAlpha(255)
    color = QColorDialog.getColor(current, dialog_parent, f"Color for '{catalog.name}'")
    if color.isValid():
        set_catalog_color(catalog.uuid, color)


def add_catalog_color_actions(menu: QMenu, catalog: Catalog, dialog_parent: QWidget | None) -> None:
    set_action = menu.addAction("Set color...")
    set_action.triggered.connect(lambda: pick_catalog_color(catalog, dialog_parent))
    if has_custom_color(catalog.uuid):
        reset_action = menu.addAction("Reset color")
        reset_action.triggered.connect(lambda: set_catalog_color(catalog.uuid, None))


def build_color_by_menu(parent_menu: QMenu, catalog: Catalog, events: list,
                        dialog_parent: QWidget | None) -> QMenu:
    current = get_color_mapper(catalog)
    color_menu = parent_menu.addMenu("Color by...")
    color_menu.setObjectName("color_by_menu")

    uniform_action = color_menu.addAction("Uniform (default)")
    uniform_action.setCheckable(True)
    uniform_action.setChecked(current.column is None)
    uniform_action.triggered.connect(lambda: set_color_mapper(catalog, ColorMapper()))

    columns = sorted({key for event in events for key in event.meta.keys()})
    if columns:
        color_menu.addSeparator()
    for col in columns:
        action = color_menu.addAction(col)
        action.setCheckable(True)
        action.setChecked(current.column == col)
        action.triggered.connect(
            lambda checked, c=col: set_color_mapper(catalog, ColorMapper(column=c)))

    if current.column is None:
        return color_menu
    values = [e.meta.get(current.column) for e in events if e.meta.get(current.column) is not None]
    color_menu.addSeparator()
    if _is_numeric(values):
        _add_colormap_submenu(color_menu, catalog, current)
        configure_action = color_menu.addAction("Configure colormap...")
        configure_action.triggered.connect(lambda: _show_colormap_dialog(catalog, current, dialog_parent))
    else:
        categories = sorted({str(v) for v in values})
        categories_action = color_menu.addAction("Category colors...")
        categories_action.triggered.connect(
            lambda: _show_category_colors_dialog(catalog, current, categories, dialog_parent))
    return color_menu


def _add_colormap_submenu(color_menu: QMenu, catalog: Catalog, current: ColorMapper) -> None:
    from .colormap_dialog import _COLORMAPS
    cmap_menu = color_menu.addMenu("Colormap")
    cmap_menu.setObjectName("colormap_menu")
    names = _COLORMAPS if current.colormap in _COLORMAPS else [*_COLORMAPS, current.colormap]
    for name in names:
        action = cmap_menu.addAction(name)
        action.setCheckable(True)
        action.setChecked(name == current.colormap)
        action.triggered.connect(
            lambda checked, n=name: set_color_mapper(catalog, current.model_copy(update={"colormap": n})))


def _show_category_colors_dialog(catalog: Catalog, current: ColorMapper, categories: list[str],
                                 dialog_parent: QWidget | None) -> None:
    from .category_colors_dialog import CategoryColorsDialog
    dialog = CategoryColorsDialog(categories, current.category_colors, _hash_color, parent=dialog_parent)
    if dialog.exec() == CategoryColorsDialog.DialogCode.Accepted:
        set_color_mapper(catalog, current.model_copy(update={"category_colors": dialog.category_colors}))


def _show_colormap_dialog(catalog: Catalog, current: ColorMapper, dialog_parent: QWidget | None) -> None:
    from .colormap_dialog import ColormapDialog
    dialog = ColormapDialog(
        current_colormap=current.colormap,
        current_vmin=current.vmin,
        current_vmax=current.vmax,
        parent=dialog_parent,
    )
    if dialog.exec() == ColormapDialog.DialogCode.Accepted:
        set_color_mapper(catalog, current.model_copy(
            update={"colormap": dialog.colormap, "vmin": dialog.vmin, "vmax": dialog.vmax}))
