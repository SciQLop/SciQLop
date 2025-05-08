import sys
import uuid
from typing import Optional, List, Any, Union
from httpx_ws import aconnect_ws
from pycrdt import Doc, Map, Array, MapEvent, Transaction, ArrayEvent
from pycrdt_websocket import WebsocketProvider
from pycrdt_websocket.websocket import HttpxWebsocket
from SciQLop.widgets.plots.time_sync_panel import TimeSyncPanel, TimeRange, SciQLopPlot
import traceback
import asyncio
from SciQLop.backend.sciqlop_logging import getLogger
from SciQLop.backend.common import SignalRateLimiter
from SciQLop.backend.sciqlop_application import sciqlop_app
from PySide6.QtCore import QObject, Signal, Slot

log = getLogger(__name__)


def epoch_to_ns(epoch: float) -> int:
    """Convert epoch time to nanoseconds."""
    return int(epoch * 1e9)


def ns_to_epoch(ns: int) -> float:
    """Convert nanoseconds to epoch time."""
    return ns / 1e9


def time_range_to_crdt(trange: TimeRange) -> Map:
    """Convert a TimeRange to a CRDT Map."""
    return Map({
        "start": epoch_to_ns(trange.start()),
        "stop": epoch_to_ns(trange.stop())
    })


def crdt_to_time_range(crdt_timerange: Map) -> TimeRange:
    return TimeRange(ns_to_epoch(crdt_timerange["start"]), ns_to_epoch(crdt_timerange["stop"]))


def update_time_range(crdt_timerange: Map, trange: TimeRange):
    """Update the CRDT time range with the given TimeRange."""
    crdt_timerange["start"] = epoch_to_ns(trange.start())
    crdt_timerange["stop"] = epoch_to_ns(trange.stop())
    return crdt_timerange


class PlotSync(QObject):
    graph_added = Signal()
    graph_removed = Signal()

    def __init__(self, plot: SciQLopPlot, panel_map: Map):
        super().__init__(plot)
        self._plot = plot
        self._plot_crdt = None
        self._sub = None
        self._panel_map = panel_map


class PanelSync(QObject):
    plot_product = Signal(str)
    remove_graph = Signal(str)
    remove_plot = Signal(str)

    def __init__(self, panels_map: Map, panel: TimeSyncPanel):
        super().__init__(panel)
        self._plots = []
        self._panel = panel
        self._time_range_rate_limiter = SignalRateLimiter(panel.time_range_changed, 20, self._time_range_changed, 100)
        if panel.name not in panels_map:
            with panels_map.doc.transaction(origin="local"):
                self._panel_crdt = Map()
                panels_map[panel.name] = self._panel_crdt
                self._panel_crdt["time_range"] = time_range_to_crdt(panel.time_range)
        else:
            self._panel_crdt = panels_map[panel.name]
            panel.time_range = crdt_to_time_range(self.time_range_crdt)
        self._sub = self.time_range_crdt.observe(self._remote_time_range_changed)

    @property
    def crdt(self):
        return self._panel_crdt

    @property
    def doc(self):
        return self._panel_crdt.doc

    @property
    def time_range_crdt(self):
        return self._panel_crdt['time_range']

    @time_range_crdt.setter
    def time_range_crdt(self, trange: TimeRange):
        """Set the CRDT time range."""
        try:
            with self.doc.transaction(origin="local"):
                update_time_range(self.time_range_crdt, trange)
        except Exception as e:
            log.error(f"Error changing time range: {e}, traceback: {traceback.format_exc()}")

    def _remote_time_range_changed(self, event, txn):
        log.debug(f"event type: {event}")
        if txn.origin == "local":
            # we are at the origin of the time range change, do nothing
            return
        for name, desc in event.keys.items():
            log.debug(f"event key: {name}, desc: {desc}")
            if desc['action'] == 'update':
                self._panel.time_range = crdt_to_time_range(self.time_range_crdt)

    def _time_range_changed(self, time_range: TimeRange):
        log.debug(f"Time range changed to {time_range}")
        self.time_range_crdt = time_range

    def _plot_added(self, plot: SciQLopPlot):
        pass

    def _plot_removed(self, plot: SciQLopPlot):
        pass


class PanelsSync(QObject):
    create_panel = Signal(str)
    remove_panel = Signal(str)

    def __init__(self, doc: Doc, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._panels: Map = doc.get("panels", type=Map)
        self._doc = doc
        self._panels.observe(self._remote_panels_changed)
        self._panels_sync = {}
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
                    self._panels_sync[name] = PanelSync(self._panels, plot_panel)
                    log.debug(f"Panel {name} added")
                    plot_panel.destroyed.connect(lambda: self.plot_panel_removed(name))
            elif plot_panel.name in self._new_remote_panels:
                name = plot_panel.name
                plot_panel.destroyed.connect(lambda: self.plot_panel_removed(name))
                self._new_remote_panels.remove(name)
                self._panels_sync[name] = PanelSync(self._panels, plot_panel)
        except Exception as e:
            log.error(f"Error adding panel {plot_panel.name}: {e}, traceback: {traceback.format_exc()}")

    @Slot(str)
    def plot_panel_removed(self, plot_panel: str):
        try:
            with self._doc.transaction(origin="local"):
                del self._panels[plot_panel]
                del self._panels_sync[plot_panel]
                log.debug(f"Panel {plot_panel} removed")
        except Exception as e:
            log.error(f"Error removing panel {plot_panel}: {e}, traceback: {traceback.format_exc()}")
