from __future__ import annotations

from SciQLop.components.command_palette.backend.registry import PaletteCommand
from SciQLop.components.command_palette.arg_types import (
    PanelArg, ProductArg, CatalogArg, ProviderArg, WorkspaceArg, TimeRangeArg,
)


def _get_win():
    from SciQLop.core.sciqlop_application import sciqlop_app
    return sciqlop_app().main_window


def _do_plot_product(product: str = "", panel: str = ""):
    if not product:
        return
    from SciQLop.user_api.plot._plots import to_product_path
    from SciQLop.components.plotting.ui.time_sync_panel import plot_product
    from SciQLopPlots import PlotType
    win = _get_win()
    target = win.new_plot_panel() if panel == "__new__" else win.plot_panel(panel)
    if target is None:
        return
    plot_product(target, to_product_path(product), plot_type=PlotType.TimeSeries)


def _do_remove_panel(panel: str = ""):
    _get_win().remove_panel(panel)


def _toggle_fullscreen():
    win = _get_win()
    win.showNormal() if win.isFullScreen() else win.showFullScreen()


def _do_set_time_range(time_range: str = ""):
    from datetime import datetime, timedelta
    from SciQLop.core import TimeRange
    durations = {"1h": 1, "1d": 24, "1w": 168, "1M": 720}
    hours = durations.get(time_range, 24)
    now = datetime.utcnow()
    tr = TimeRange((now - timedelta(hours=hours)).timestamp(), now.timestamp())
    _get_win()._default_time_range = tr


def _do_switch_workspace(workspace: str = ""):
    from SciQLop.sciqlop_app import switch_workspace
    switch_workspace(workspace)


def _reveal_catalogs_browser(win):
    browser = win.catalogs_browser
    dw = win.dock_manager.findDockWidget(browser.windowTitle())
    if dw is not None:
        dw.toggleView(True)
        dw.raise_()
    return browser


def _find_provider_node(tree_model, provider):
    from PySide6.QtCore import QModelIndex
    for row in range(tree_model.rowCount(QModelIndex())):
        idx = tree_model.index(row, 0, QModelIndex())
        if tree_model.node_from_index(idx).provider is provider:
            return tree_model.node_from_index(idx)
    return None


def _do_create_catalog(provider: str = ""):
    """Reuse the tree's own "New Catalog" inline-edit flow -- same UX as
    right-clicking the provider in the browser, just reached from the
    palette."""
    from SciQLop.components.catalogs.backend.registry import CatalogRegistry
    from SciQLop.components.catalogs.ui.catalog_tree import _PlaceholderType
    target = CatalogRegistry.instance().provider_by_name(provider)
    if target is None:
        return
    win = _get_win()
    browser = _reveal_catalogs_browser(win)
    node = _find_provider_node(browser._tree_model, target)
    if node is None:
        return
    placeholder = next(
        (c for c in node.children if c.placeholder_type == _PlaceholderType.CATALOG), None)
    if placeholder is None:
        return
    browser._trigger_placeholder_edit(placeholder)


def _do_open_catalog(catalog: str = ""):
    from SciQLop.components.command_palette.arg_types import resolve_catalog_arg
    cat = resolve_catalog_arg(catalog)
    if cat is None:
        return
    win = _get_win()
    browser = _reveal_catalogs_browser(win)
    node = _find_provider_node(browser._tree_model, cat.provider)
    if node is None:
        return
    cat_node = next((c for c in node.children
                      if c.catalog is not None and c.catalog.uuid == cat.uuid), None)
    if cat_node is None:
        return
    source_index = browser._tree_model.createIndex(cat_node.row(), 0, cat_node)
    proxy_index = browser._proxy_model.mapFromSource(source_index)
    browser._catalog_tree.setCurrentIndex(proxy_index)
    browser._catalog_tree.scrollTo(proxy_index)


def register_builtin_commands(registry):
    registry.register(PaletteCommand(
        id="plot.new_panel",
        name="New plot panel",
        description="Create a new plot panel",
        callback=lambda: _get_win().new_plot_panel(),
        replaces_qaction="Add new plot panel",
    ))

    registry.register(PaletteCommand(
        id="plot.product",
        name="Plot product",
        description="Plot a product in a panel",
        callback=_do_plot_product,
        args=[ProductArg(), PanelArg()],
    ))

    registry.register(PaletteCommand(
        id="plot.remove_panel",
        name="Remove panel",
        description="Remove an existing plot panel",
        callback=_do_remove_panel,
        args=[PanelArg(name="panel")],
    ))

    registry.register(PaletteCommand(
        id="plot.set_time_range",
        name="Set time range",
        description="Set the global time range",
        callback=_do_set_time_range,
        args=[TimeRangeArg()],
    ))

    registry.register(PaletteCommand(
        id="catalog.create",
        name="Create catalog",
        description="Create a new catalog",
        callback=_do_create_catalog,
        args=[ProviderArg()],
    ))

    registry.register(PaletteCommand(
        id="catalog.open",
        name="Open catalog",
        description="Open a catalog in the browser",
        callback=_do_open_catalog,
        args=[CatalogArg()],
    ))

    registry.register(PaletteCommand(
        id="jupyter.lab",
        name="Open JupyterLab in browser",
        description="Open JupyterLab in browser",
        callback=lambda: __import__(
            "SciQLop.components.workspaces", fromlist=["workspaces_manager_instance"]
        ).workspaces_manager_instance().open_in_browser(),
    ))

    registry.register(PaletteCommand(
        id="workspace.switch",
        name="Switch workspace",
        description="Switch to a different workspace",
        callback=_do_switch_workspace,
        args=[WorkspaceArg()],
    ))

    registry.register(PaletteCommand(
        id="view.fullscreen",
        name="Toggle fullscreen",
        description="Toggle fullscreen mode (F11)",
        callback=_toggle_fullscreen,
        keywords=["F11"],
    ))
