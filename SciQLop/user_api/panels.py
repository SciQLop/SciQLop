"""Open panels of any kind contributed to ``sciqlop.panel_kinds``."""
from typing import List, Optional, Union

from PySide6.QtWidgets import QWidget

from SciQLop.core.panel_kinds import PANEL_KINDS
from SciQLop.core.plot_kinds import TIME_PANEL
from .gui import get_main_window as _get_main_window
from .plot import PlotPanel
from .threading import on_main_thread

__all__ = ["open_panel", "list_panel_kinds"]


@on_main_thread
def open_panel(kind: str, name: Optional[str] = None, **config) -> Union[PlotPanel, QWidget]:
    """Open a panel of the given kind and dock it.

    Args:
        kind (str): A panel kind id, see :func:`list_panel_kinds`.
        name (Optional[str]): The panel name. Made unique if already taken.
        **config: Passed as is to the kind's constructor; every key is the kind's own, ``area`` included.

    Returns:
        The :class:`PlotPanel` for the time panel kind, the panel widget for any other kind.
    """
    widget = _get_main_window()._open_panel(kind, name, None, config)
    return PlotPanel(widget) if kind == TIME_PANEL else widget


def list_panel_kinds() -> List[str]:
    """Ids of every panel kind that :func:`open_panel` accepts."""
    return PANEL_KINDS.keys()
