from __future__ import annotations

from PySide6.QtCore import QObject

from SciQLop.core.ui.mainwindow import SciQLopMainWindow


class Plugin(QObject):
    def __init__(self, main_window: SciQLopMainWindow):
        super(Plugin, self).__init__(main_window)
        from .tscat_provider import TscatCatalogProvider
        self._catalog_provider = TscatCatalogProvider(parent=self)
        self.main_window = main_window
