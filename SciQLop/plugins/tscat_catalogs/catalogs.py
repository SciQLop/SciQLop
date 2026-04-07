from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QToolBar
from tscat_gui import TSCatGUI

from SciQLop.core.ui.mainwindow import SciQLopMainWindow
from SciQLop.components.theming import theme_icon


class CatalogGUISpawner(QAction):
    def __init__(self, catalog_gui, parent=None):
        super(CatalogGUISpawner, self).__init__(parent)
        self.catalog_gui = catalog_gui
        self.setIcon(theme_icon("catalogue"))
        self.triggered.connect(self.show_catalogue_gui)
        self.setText("Open Catalogue Explorer")

    def show_catalogue_gui(self):
        self.catalog_gui.show()


class Plugin(QObject):
    def __init__(self, main_window: SciQLopMainWindow):
        super(Plugin, self).__init__(main_window)
        self.manager_ui = TSCatGUI()
        from .tscat_provider import TscatCatalogProvider
        self._catalog_provider = TscatCatalogProvider(parent=self)
        self.show_catalog = CatalogGUISpawner(self.manager_ui)
        self.main_window = main_window
        self.toolbar: QToolBar = main_window.addToolBar("Catalogs")
        self.toolbar.addAction(self.show_catalog)
