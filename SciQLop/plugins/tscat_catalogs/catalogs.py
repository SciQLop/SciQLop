from typing import List, Tuple
from datetime import datetime

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QToolBar
from tscat_gui import TSCatGUI

from SciQLop.core.ui.mainwindow import SciQLopMainWindow
from SciQLop.components.theming import get_current_style_icon

def zoom_out(start: datetime, stop: datetime, factor: float):
    delta = ((stop - start) / 2.) * factor
    return start - delta, stop + delta


def timestamps(start: datetime, stop: datetime):
    return start.timestamp(), stop.timestamp()


class CatalogGUISpawner(QAction):
    def __init__(self, catalog_gui, parent=None):
        super(CatalogGUISpawner, self).__init__(parent)
        self.catalog_gui = catalog_gui
        self.setIcon(get_current_style_icon("catalogue"))
        self.triggered.connect(self.show_catalogue_gui)
        self.setText("Open Catalogue Explorer")

    def show_catalogue_gui(self):
        self.catalog_gui.show()


class Plugin(QObject):
    def __init__(self, main_window: SciQLopMainWindow):
        super(Plugin, self).__init__(main_window)
        self.manager_ui = TSCatGUI()
        from .lightweight_manager import LightweightManager
        self.lightweight_manager = LightweightManager(main_window=main_window, manager_ui=self.manager_ui)
        from .tscat_provider import TscatCatalogProvider
        self._catalog_provider = TscatCatalogProvider(parent=self)
        self.lightweight_manager.setWindowIcon(get_current_style_icon("catalogue"))
        self.show_catalog = CatalogGUISpawner(self.manager_ui)
        self.main_window = main_window
        self.last_event = None
        self.toolbar: QToolBar = main_window.addToolBar("Catalogs")
        self.toolbar.addAction(self.show_catalog)

        main_window.panels_list_changed.connect(self.lightweight_manager.update_panels_list)
        main_window.add_side_pan(self.lightweight_manager)

        from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
        self._catalog_browser = CatalogBrowser()
        self._catalog_browser.setWindowTitle("Catalog Browser")
        main_window.add_side_pan(self._catalog_browser)

        # Connect to existing panels
        for panel_name in main_window.plot_panels():
            panel = main_window.plot_panel(panel_name)
            if panel is not None:
                self._catalog_browser.connect_to_panel(panel)

        # Connect to future panels
        main_window.panel_added.connect(self._catalog_browser.connect_to_panel)


    def catalogs(self)-> List[str]:
        return self.lightweight_manager.catalogs()

    def events(self, catalog: str)-> List[Tuple[datetime, datetime]]:
        return self.lightweight_manager.events(catalog)
