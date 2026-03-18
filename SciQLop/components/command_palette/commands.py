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
    _get_win()._dt_range_action.range = tr


def _do_switch_workspace(workspace: str = ""):
    from SciQLop.sciqlop_app import switch_workspace
    switch_workspace(workspace)


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
        callback=lambda provider="": None,
        args=[ProviderArg()],
    ))

    registry.register(PaletteCommand(
        id="catalog.open",
        name="Open catalog",
        description="Open a catalog in the browser",
        callback=lambda catalog="": None,
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
