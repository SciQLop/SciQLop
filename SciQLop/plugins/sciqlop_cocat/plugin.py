from __future__ import annotations

from PySide6.QtCore import QObject, QTimer

from SciQLop.components.plugins.backend.settings import SciQLopPluginsSettings
from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.components.storage import user_data_dir

from .provider import CocatRsProvider
from .session import Session
from .settings import CocatRsSettings
from .tscat_import import read_tscat_database

log = getLogger(__name__)

BUILTIN_PLUGIN = "collaborative_catalogs"


def builtin_plugin_enabled(settings) -> bool:
    entry = settings.plugins.get(BUILTIN_PLUGIN)
    return entry is not None and entry.enabled


class Plugin(QObject):
    def __init__(self, main_window):
        super().__init__(main_window)
        settings = CocatRsSettings()
        self.provider = CocatRsProvider(session=Session(settings.server_url), cache_dir=user_data_dir("cocat_rs"),
                                        local_dir=user_data_dir("cocat_rs_local"),
                                        read_tscat=read_tscat_database, parent=self)
        QTimer.singleShot(0, self.provider.start)
        if builtin_plugin_enabled(SciQLopPluginsSettings()):
            log.warning("Both the built-in 'Collaborative Catalogs' plugin and 'Shared Catalogs "
                        "(cocat-rs)' are enabled. They run side by side as 'Shared' and 'Catalogs "
                        "(cocat-rs)'; disable one in Settings > Plugins if this is not intended.")

    async def close(self):
        await self.provider.close()


def load(main_window):
    return Plugin(main_window)
