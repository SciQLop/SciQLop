from PySide6.QtCore import QObject
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QToolBar
from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.ui.mainwindow import SciQLopMainWindow
from .cocat_provider import CocatCatalogProvider

log = getLogger(__name__)


class Plugin(QObject):
    def __init__(self, main_window: SciQLopMainWindow):
        super().__init__(main_window)
        self._main_window = main_window
        self._provider = CocatCatalogProvider(parent=self)

        self._connect_action = QAction(self)
        self._connect_action.setIcon(QIcon("://icons/theme/catalogue.png"))
        self._connect_action.setText("Open Collaborative Catalogs")
        self._connect_action.triggered.connect(self._on_connect)

        self.toolbar: QToolBar = main_window.addToolBar("Collaborative Catalogs")
        self.toolbar.addAction(self._connect_action)

    def _on_connect(self) -> None:
        if not self._provider.connected:
            self._provider.connect_to_server()
        else:
            self._provider.disconnect_from_server()

    async def close(self):
        await self._provider.async_close()
