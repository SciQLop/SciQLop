import os
from SciQLop.widgets.mainwindow import SciQLopMainWindow
from .plugin import Plugin

__all__ = ["load"]


def load(main_window: SciQLopMainWindow):
    if os.environ.get("SCIQLOP_COLLAB", False):
        return Plugin(main_window)
    return None
