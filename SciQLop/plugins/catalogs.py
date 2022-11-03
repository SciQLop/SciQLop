import tscat
from tscat_gui import TSCatGUI
from PySide6.QtWidgets import QComboBox
from PySide6.QtGui import QAction, QIcon
from PySide6.QtCore import QRunnable, Slot, Signal, QThreadPool, QObject
from datetime import datetime
from SciQLop.widgets.mainwindow import SciQLopMainWindow


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


class CatalogSelector(QComboBox):
    def __init__(self, parent=None):
        super(CatalogSelector, self).__init__(parent)
        self.catalogs = [None]
        self.update_list()

    def update_list(self):
        selected = self.catalogs[self.currentIndex()]
        self.catalogs = [None] + tscat.get_catalogues()
        self.clear()
        self.addItems(map(catalog_display_txt, self.catalogs))
        self.setCurrentIndex(index_of(self.catalogs, selected))


class PanelSelector(QComboBox):
    def __init__(self, parent=None):
        super(PanelSelector, self).__init__(parent)
        self.addItems(["None"])

    def update_list(self, panels):
        selected = self.currentText()
        self.clear()
        self.addItems(["None"] + panels)
        self.setCurrentText(selected)


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
        self.ui = TSCatGUI()
        self.catalog_selector = CatalogSelector()
        self.panel_selector = PanelSelector()
        self.show_catalog = CatalogGUISpawner(self.ui)
        self.main_window = main_window
        self.last_event = None

        main_window.toolBar.addAction(self.show_catalog)
        main_window.toolBar.addWidget(self.catalog_selector)
        main_window.toolBar.addWidget(self.panel_selector)

        main_window.central_widget.panels_list_changed.connect(self.panel_selector.update_list)

        self.ui.event_selected.connect(self.event_selected)

    @Slot()
    def event_selected(self, event):
        if self.panel_selector.currentText() != 'None':
            if self.last_event is not None:
                del self.last_event
            e = tscat.get_events(tscat.filtering.UUID(event))[0]
            print(e)
            if e:
                p = self.main_window.plotPanel(self.panel_selector.currentText())
                print(p)
                if p:
                    p.setTimeRange(*timestamps(*zoom_out(e.start, e.stop, 0.3)))
                    # self.last_event = EventTimeSpan(p, *timestamps(e.start, e.stop))


def load(main_window: SciQLopMainWindow):
    return Plugin(main_window)
