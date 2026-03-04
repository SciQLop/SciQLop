from typing import Optional
from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QToolBar
from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.ui.mainwindow import SciQLopMainWindow
from qasync import asyncSlot
from .room import Room

log = getLogger(__name__)


class CatalogGUISpawner(QAction):
    _connected = Signal()

    def __init__(self, url: str = "https://sciqlop.lpp.polytechnique.fr/cocat/", parent=None):
        super().__init__(parent)
        self._url = url
        self.setIcon(QIcon("://icons/theme/catalogue.png"))
        self.triggered.connect(self.show_catalogue_gui)
        self.setText("Open Collaborative Catalogs")
        self._room: Optional[Room] = None
        self._provider = None
        self._connected.connect(self._once_connected, Qt.ConnectionType.QueuedConnection)

    def _once_connected(self):
        from .cocat_provider import CocatCatalogProvider
        self._provider = CocatCatalogProvider(room=self._room, parent=self)
        log.info("CoCat provider registered with %d catalogs", len(self._provider.catalogs()))

    @asyncSlot()
    async def show_catalogue_gui(self):
        try:
            self._room = Room(url=self._url, parent=self)
            if await self._room.join():
                self._connected.emit()
        except Exception as e:
            log.error(e)


class Plugin(QObject):
    def __init__(self, main_window: SciQLopMainWindow):
        super().__init__(main_window)
        self._main_window = main_window
        self.show_catalog = CatalogGUISpawner()
        self.toolbar: QToolBar = main_window.addToolBar("Collaborative Catalogs")
        self.toolbar.addAction(self.show_catalog)
