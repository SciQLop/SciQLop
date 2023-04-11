from SciQLop.widgets.mainwindow import SciQLopMainWindow
from .catalogs import Plugin

__all__ = ["load"]


def load(main_window: SciQLopMainWindow):
    return Plugin(main_window)
