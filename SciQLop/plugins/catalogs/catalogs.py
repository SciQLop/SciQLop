from datetime import datetime

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QToolBar
from tscat_gui import TSCatGUI

from SciQLop.widgets.mainwindow import SciQLopMainWindow
from .lightweight_manager import LightweightManager


def catalog_display_txt(catalog):
    if catalog is not None:
        return catalog.name
    return "None"


def index_of(catalogs, catalog):
    index = 0
    if catalog:
        for c in catalogs:
            if (c is not None) and (c.uuid == catalog.uuid):
                return index
            index += 1
    return 0


def zoom_out(start: datetime, stop: datetime, factor: float):
    delta = ((stop - start) / 2.) * factor
    return start - delta, stop + delta


def timestamps(start: datetime, stop: datetime):
    return start.timestamp(), stop.timestamp()


class CatalogGUISpawner(QAction):
    def __init__(self, catalog_gui, parent=None):
        super(CatalogGUISpawner, self).__init__(parent)
        self.catalog_gui = catalog_gui
        self.setIcon(QIcon("://icons/catalogue.png"))
        self.triggered.connect(self.show_catalogue_gui)

    def show_catalogue_gui(self):
        self.catalog_gui.show()


class Plugin(QObject):
    def __init__(self, main_window: SciQLopMainWindow):
        super(Plugin, self).__init__(main_window)
        self.manager_ui = TSCatGUI()
        self.lightweight_manager = LightweightManager()
        self.show_catalog = CatalogGUISpawner(self.manager_ui)
        self.main_window = main_window
        self.last_event = None
        self.toolbar: QToolBar = main_window.addToolBar("Catalogs")
        self.toolbar.addAction(self.show_catalog)

        main_window.central_widget.panels_list_changed.connect(self.lightweight_manager.update_panels_list)
        main_window.add_side_pan(self.lightweight_manager)
