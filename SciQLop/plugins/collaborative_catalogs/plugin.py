from PySide6.QtCore import QObject
from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.ui.mainwindow import SciQLopMainWindow
from cocat import DB, CatalogueModel, EventModel
from datetime import datetime, timedelta, timezone

log = getLogger(__name__)


class Plugin(QObject):
    def __init__(self, main_window: SciQLopMainWindow):
        super(Plugin, self).__init__(main_window)
        self._main_window = main_window
        self._db = DB()
        self._catalogue = self._db.create_catalogue(
            CatalogueModel(name="cat0", author="Paul", attributes={"baz": 3}))
        for i in range(10000):
            self._catalogue.add_events(
                self._db.create_event(
                    EventModel(
                        start=datetime(2020, 1, 1, 12, tzinfo=timezone.utc) + timedelta(days=i),
                        stop=datetime(2020, 1, 1, 13, tzinfo=timezone.utc) + timedelta(days=i),
                        author="Paul",
                        attributes={"index": i}
                    )
                )
            )
