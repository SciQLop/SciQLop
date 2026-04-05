from SciQLop.core.ui.mainwindow import SciQLopMainWindow
from .catalogs import Plugin
from ._patches import apply_tscat_gui_patches

__all__ = ["load"]


def load(main_window: SciQLopMainWindow):
    apply_tscat_gui_patches()
    return Plugin(main_window)
