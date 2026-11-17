from __future__ import annotations

from PySide6.QtCore import QObject, QTimer

from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.components.storage import user_data_dir

from .provider import CocatRsProvider
from .session import Session
from .settings import CocatRsSettings
from .tscat_import import read_tscat_database, stop_reading

log = getLogger(__name__)

class Plugin(QObject):
    def __init__(self, main_window):
        super().__init__(main_window)
        settings = CocatRsSettings()
        self.provider = CocatRsProvider(session=Session(settings.server_url), cache_dir=user_data_dir("cocat_rs"),
                                        local_dir=user_data_dir("cocat_rs_local"),
                                        read_tscat=read_tscat_database, parent=self)
        QTimer.singleShot(0, self.provider.start)

    def close(self):
        """The read is stopped before anything is awaited: without a running loop, SciQLop closes
        the returned coroutine without running it."""
        stop_reading()
        return self.provider.close()


def load(main_window):
    return Plugin(main_window)
