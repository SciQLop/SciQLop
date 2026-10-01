from typing import Callable, List, Tuple

from SciQLop.components.plotting.backend import panel_menus as _panel_menus
from ._thread_safety import on_main_thread


@on_main_thread
def register_panel_menu(title: str, entries: Callable[["PlotPanel"], List[Tuple[str, Callable[[], None]]]]) -> None:
    """Add a submenu to every plot panel's context menu.

    Parameters
    ----------
    title : str
        Submenu title. Registering the same title again replaces it.
    entries : callable
        Called with the clicked ``PlotPanel`` each time the menu opens; returns
        ``(label, callback)`` pairs. An empty list hides the submenu, and an
        exception is logged without breaking the rest of the menu.

    Examples
    --------
    >>> register_panel_menu("Events", lambda panel: [
    ...     ("Storm", lambda: setattr(panel, "time_range", TimeRange("2015-03-17", "2015-03-18")))])
    """
    _panel_menus.register(title, entries)


@on_main_thread
def unregister_panel_menu(title: str) -> None:
    """Remove a submenu added with :func:`register_panel_menu`; unknown titles are ignored."""
    _panel_menus.unregister(title)
