from typing import Optional
import uuid
import asyncio
from httpx_ws import aconnect_ws
from pycrdt_websocket import WebsocketProvider
from pycrdt_websocket.websocket import HttpxWebsocket
from PySide6.QtCore import QObject, Slot
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QToolBar
from SciQLop.widgets.mainwindow import SciQLopMainWindow
from .collab_wizard import CollabWizard, Result as CollabResult
from .collab import PanelsSync
from pycrdt import Doc
from SciQLop.backend.sciqlop_logging import getLogger

from ...widgets.plots.time_sync_panel import TimeSyncPanel

log = getLogger(__name__)


class Plugin(QObject):

    def __init__(self, main_window: SciQLopMainWindow):
        super(Plugin, self).__init__(main_window)
        self._doc = Doc()
        self._panels = PanelsSync(self._doc, self)
        main_window.panel_added.connect(self._panels.plot_panel_added)
        self._panels.remove_panel.connect(main_window.remove_panel)
        self._panels.create_panel.connect(lambda name: main_window.new_plot_panel(name=name))

        self._collab_wizard = CollabWizard(main_window)
        self._collab_wizard.setModal(True)
        self._collab_wizard.done.connect(self._start_collab)

        self.start_collab = QAction(self)
        self.start_collab.setIcon(QIcon("://icons/theme/collab.png"))
        self.start_collab.setText("Start collaborative mode")
        self.start_collab.triggered.connect(self.toggle_collab)
        main_window.toolBar.addAction(self.start_collab)

        self._server_url = "https://sciqlop.lpp.polytechnique.fr/cache-dev"
        self._room_id = uuid.uuid4().hex
        self._ws = None
        self._provider = None
        self.close_event = asyncio.Event()

    @property
    def server_url(self) -> str:
        return self._server_url

    @property
    def room_id(self) -> str:
        return self._room_id

    @property
    def join_url(self) -> str:
        return f"{self._server_url}/{self._room_id}"

    def toggle_collab(self):
        if self._ws is None:
            self._start_collab_wizard()
        else:
            self.stop()

    def _start_collab_wizard(self):
        self._collab_wizard.restart()
        self._collab_wizard.show()

    def _start_collab(self, result: CollabResult, server_url: str, room_id: str):
        if result != CollabResult.Nothing:
            log.info(
                f"Starting collab with server URL {self._collab_wizard.server_url} and room {self._collab_wizard.room_id}")
            self._server_url = server_url
            self._room_id = room_id
            self.start()

    def close(self):
        self.close_event.set()

    async def _start(self):
        async with (
            aconnect_ws(f"{self._server_url}/{self._room_id}") as websocket,
            WebsocketProvider(self._doc, HttpxWebsocket(websocket, self._room_id), log) as provider,
        ):
            self._ws = websocket
            self._provider = provider
            await self.close_event.wait()

    def start(self):
        self._task = asyncio.create_task(self._start())
        self.start_collab.setText("Stop collaborative mode")

    def stop(self):
        self.close_event.set()
        self._ws = None
        self._provider = None
        self.start_collab.setText("Start collaborative mode")
