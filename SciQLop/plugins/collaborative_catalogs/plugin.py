from PySide6.QtCore import QObject
from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.ui.mainwindow import SciQLopMainWindow
from .cocat_provider import CocatCatalogProvider
from .settings import CollaborativeCatalogsSettings

log = getLogger(__name__)


class Plugin(QObject):
    def __init__(self, main_window: SciQLopMainWindow):
        super().__init__(main_window)
        url = CollaborativeCatalogsSettings().server_url
        self._provider = CocatCatalogProvider(url=url, parent=self)

    async def close(self):
        await self._provider.async_close()
