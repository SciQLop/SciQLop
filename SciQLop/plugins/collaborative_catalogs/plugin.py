from typing import List, Optional
from datetime import datetime, timedelta, timezone
from PySide6.QtCore import QObject, Signal, Qt, QTimer, Slot
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QToolBar
from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.ui.mainwindow import SciQLopMainWindow
from cocat import DB
from cocat import Catalogue as CoCatalogue, Event as CoEvent
from wire_websocket import AsyncWebSocketClient
from SciQLop.components.plotting.backend.catalogue import Catalogue, CatalogueProviderBase, EventBase, TimeRange
from SciQLop.user_api.plot import create_plot_panel
import asyncio
import httpx
from tempfile import TemporaryDirectory
import traceback

log = getLogger(__name__)


class Event(EventBase):

    def __init__(self, event: CoEvent):
        super(Event, self).__init__()
        self._event = event
        self._cached_range: TimeRange = TimeRange(self._event.start, self._event.stop)
        self._next_range: TimeRange = self._cached_range
        self._event.on_change_range(lambda start, stop: self.range_changed.emit(TimeRange(start, stop)))
        self._delayed_range_update = QTimer(self)
        self._delayed_range_update.setSingleShot(True)
        self._delayed_range_update.setInterval(100)
        self._delayed_range_update.timeout.connect(self._apply_range_change)

    def set_range(self, r: TimeRange):
        self._delayed_range_update.start()
        self._next_range = r

    @Slot()
    def _apply_range_change(self):
        self.range = self._next_range

    @property
    def range(self):
        return self._cached_range

    @range.setter
    def range(self, dtrange: TimeRange):
        changed = False
        if self._cached_range != dtrange:
            self._event.range = (dtrange.datetime_start(), dtrange.datetime_stop())
            self._cached_range = dtrange
            self.range_changed.emit(dtrange)

    @property
    def uuid(self):
        return str(self._event.uuid)

    @property
    def tool_tip(self) -> str:
        return ""


class CatalogueProvider(CatalogueProviderBase):
    def __init__(self, catalog: CoCatalogue):
        super(CatalogueProvider, self).__init__()
        self._catalog = catalog
        self._catalog.on_add_events(self._on_add_events)
        self._catalog.on_remove_events(self._on_remove_events)
        self._events: List[Event] = []
        for event in self._catalog.events:
            self._events.append(Event(event))

    def _on_add_events(self, events: List[CoEvent]):
        pass

    def _on_remove_events(self, events: List[str]):
        pass

    @property
    def events(self) -> List[EventBase]:
        return self._events


class CatalogGUISpawner(QAction):
    _connected = Signal()

    def __init__(self, db: DB, parent=None):
        super(CatalogGUISpawner, self).__init__(parent)
        self.setIcon(QIcon("://icons/theme/catalogue.png"))
        self.triggered.connect(self.show_catalogue_gui)
        self.setText("Open Catalogue Explorer")
        self.close_event = asyncio.Event()
        self._db = db
        self._catalogue: Optional[Catalogue] = None
        self._host = "http://127.0.0.1"
        self._port = 8000
        self._fdir = TemporaryDirectory()
        self._file_path = f"{self._fdir.name}/cocat.y"
        self._room_id = "room0"
        self._cookies = httpx.Cookies()
        self._connected.connect(self._once_connected, Qt.ConnectionType.QueuedConnection)
        self._client = None
        self._cocatalogue: Optional[CoCatalogue] = None
        self._task: Optional[asyncio.Task] = None

    def _once_connected(self):
        panel = create_plot_panel()
        panel.plot("speasy//amda//Parameters//ACE//MFI//final / prelim//b_gse")
        panel.time_range = TimeRange(datetime(2020, 1, 10, 0, tzinfo=timezone.utc),
                                     datetime(2020, 1, 20, 0, tzinfo=timezone.utc))
        try:
            self._cocatalogue = self._db.get_catalogue("cat0")
        except Exception as e:
            with self._db.transaction():
                self._cocatalogue = self._db.create_catalogue(name="cat0", author="Paul", attributes={"baz": 3})
                for i in range(100):
                    self._cocatalogue.add_events(
                        self._db.create_event(
                            start=datetime(2020, 1, 1, 12, tzinfo=timezone.utc) + timedelta(days=i),
                            stop=datetime(2020, 1, 1, 13, tzinfo=timezone.utc) + timedelta(days=i),
                            author="Paul",
                            attributes={"index": i}
                        )
                    )

        self._catalogue = Catalogue(catalogue_provider=CatalogueProvider(self._cocatalogue),
                                    parent=panel._get_impl_or_raise())
        self._catalogue.read_only = False

    def show_catalogue_gui(self):
        try:
            if not self._login():
                raise RuntimeError("Login failed")
            log.info("Connecting to websocket")
            self._task = asyncio.create_task(self._start())
        except Exception as e:
            log.error(e)

    def _login(self) -> bool:
        log.info("Logging in to websocket")
        data = {"username": "test@example.com", "password": "test"}
        response = httpx.post(f"{self._host}:{self._port}/auth/jwt/login", data=data)
        cookie = response.cookies.get("fastapiusersauth")
        if cookie:
            self._cookies.set("fastapiusersauth", cookie)
            log.info("Successfully logged in")
            return True
        log.info("Failed to log in to websocket")
        return False

    async def _start(self):
        log.info("Starting websocket")
        log.info(f"Connecting to websocket url: {self._host}:{self._port}, cookies: {self._cookies}")
        try:
            async with (AsyncWebSocketClient(f"room/{self._room_id}", doc=self._db.doc,
                                             host=self._host, port=self._port,
                                             cookies=self._cookies) as self._client):  # ,
                # connect("file", doc=self._db.doc, path=self._file_path) as self.file):
                log.info('Connected to websocket')
                self._connected.emit()
                await self.close_event.wait()
        except Exception as e:
            log.error(e)
            log.error(traceback.format_exc())


class Plugin(QObject):
    def __init__(self, main_window: SciQLopMainWindow):
        super(Plugin, self).__init__(main_window)
        self._main_window = main_window
        self._db = DB()

        self.show_catalog = CatalogGUISpawner(self._db)
        self.toolbar: QToolBar = main_window.addToolBar("Catalogs")
        self.toolbar.addAction(self.show_catalog)
