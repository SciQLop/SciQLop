import sys
import uuid
from typing import Optional, List, Any, Union
from httpx_ws import aconnect_ws
from pycrdt import Doc, Map, MapEvent, Transaction
from pycrdt_websocket import WebsocketProvider
from pycrdt_websocket.websocket import HttpxWebsocket
from SciQLop.widgets.plots.time_sync_panel import TimeSyncPanel
import traceback
import asyncio
from SciQLop.backend.sciqlop_logging import getLogger
from SciQLop.backend.sciqlop_application import sciqlop_app
from PySide6.QtCore import QObject, Signal, Slot

log = getLogger(__name__)


class PanelsSync(QObject):
    create_panel = Signal(str)
    remove_panel = Signal(str)

    def __init__(self, doc: Doc, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._panels: Map = doc.get("panels", type=Map)
        self._doc = doc
        self._panels.observe(self._remote_panels_changed)
        self._new_remote_panels = []

    def _remote_panels_changed(self, event: MapEvent, txn: Transaction):
        log.debug(f"even type: {event}, txn origin: {txn.origin}")
        if txn.origin == "local":
            # we are at the origin of the panel creation, do nothing
            return
        for name, desc in event.keys.items():
            if desc['action'] == 'add':
                self._new_remote_panels.append(name)
                self.create_panel.emit(name)
            elif desc['action'] == 'delete':
                self.remove_panel.emit(name)

    @Slot(TimeSyncPanel)
    def plot_panel_added(self, plot_panel: TimeSyncPanel):
        try:
            if plot_panel.name not in self._panels:
                with self._doc.transaction(origin="local"):
                    name = plot_panel.name
                    self._panels[name] = Map()
                    log.debug(f"Panel {name} added")
                    plot_panel.destroyed.connect(lambda: self.plot_panel_removed(name))
            elif plot_panel.name in self._new_remote_panels:
                name = plot_panel.name
                plot_panel.destroyed.connect(lambda: self.plot_panel_removed(name))
                self._new_remote_panels.remove(plot_panel.name)
        except Exception as e:
            log.error(f"Error adding panel {plot_panel.name}: {e}, traceback: {traceback.format_exc()}")

    @Slot(str)
    def plot_panel_removed(self, plot_panel: str):
        try:
            with self._doc.transaction(origin="local"):
                del self._panels[plot_panel]
                log.debug(f"Panel {plot_panel} removed")
        except Exception as e:
            log.error(f"Error removing panel {plot_panel}: {e}, traceback: {traceback.format_exc()}")
