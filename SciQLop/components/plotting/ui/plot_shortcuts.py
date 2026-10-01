"""Per-plot keys: M autoscales, L toggles log scale, H hides the selection.

SciQLopPlots 0.36 stopped binding them itself and leaves them to the host. They
act on the plot holding keyboard focus, so a plot gets them the first time focus
lands inside it: plugin plots outside any panel (CDF workbench preview, MSA fit
inspector) get them with nothing to call.
"""
from SciQLopPlots import SciQLopPlotInterface

from SciQLop.components.shortcuts import add_shortcut

PLOT_SHORTCUTS = {
    "plot.autoscale": "rescale_hovered_or_selected_axes",
    "plot.toggle_log": "toggle_log_scale_hovered_or_selected_axes",
    "plot.toggle_selection_visibility": "toggle_selected_objects_visibility",
}

_INSTALLED = "sciqlop_plot_shortcuts"


def install_plot_shortcuts(plot) -> None:
    # Once per plot: two shortcuts on the same key make Qt treat both as ambiguous.
    if plot.property(_INSTALLED):
        return
    plot.setProperty(_INSTALLED, True)
    for shortcut_id, action in PLOT_SHORTCUTS.items():
        add_shortcut(plot, shortcut_id, getattr(plot, action))


def _enclosing_plot(widget):
    while widget is not None and not isinstance(widget, SciQLopPlotInterface):
        widget = widget.parentWidget()
    return widget


def _on_focus_changed(_old, new) -> None:
    plot = _enclosing_plot(new)
    if plot is not None:
        install_plot_shortcuts(plot)


def enable_plot_shortcuts_everywhere(app) -> None:
    """Hook focusChanged rather than an application event filter: it fires only
    when focus moves, while a Python event filter would run on every Qt event."""
    if app.property(_INSTALLED):
        return
    app.setProperty(_INSTALLED, True)
    app.focusChanged.connect(_on_focus_changed)
