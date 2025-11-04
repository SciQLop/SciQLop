from typing import List, Optional, Protocol, Dict, Any, Tuple, runtime_checkable, Union

import qtconsole.comms
from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtGui import QColor
from shiboken6 import isValid

from SciQLopPlots import SciQLopMultiPlotPanel, MultiPlotsVSpanCollection
from SciQLop.components.plotting.ui.time_span import TimeSpan
from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
from SciQLop.core import TimeRange, sciqlop_application
from SciQLop.core.property import SciQLopProperty


class EventBase(QObject):
    range_changed = Signal(TimeRange)

    def __init__(self):
        super(EventBase, self).__init__()

    def set_range(self, r: TimeRange):
        if r != self.range:
            self.range = r

    @property
    def range(self) -> TimeRange:
        raise NotImplementedError("range not implemented")

    @range.setter
    def range(self, value: TimeRange):
        raise NotImplementedError("range not implemented")

    @property
    def uuid(self) -> str:
        raise NotImplementedError("uuid not implemented")

    @uuid.setter
    def uuid(self, value: str):
        raise NotImplementedError("uuid not implemented")

    @property
    def meta(self) -> Dict[str, Any]:
        raise NotImplementedError("meta not implemented")

    @meta.setter
    def meta(self, value: Dict[str, Any]):
        raise NotImplementedError("meta not implemented")

    @property
    def color(self) -> QColor:
        return QColor(100, 100, 100, 50)

    @color.setter
    def color(self, value: QColor):
        raise NotImplementedError("color not implemented")

    @property
    def tool_tip(self) -> str:
        raise NotImplementedError("tool_tip not implemented")

    def __eq__(self, other):
        if isinstance(other, EventBase):
            return (self is other) or (self.uuid == other.uuid)
        return False


def set_range(obj, r: TimeRange):
    obj.range = r


class CatalogueProviderBase(QObject):
    event_added = Signal(EventBase)
    event_removed = Signal(EventBase)

    def __init__(self, parent=None):
        super(CatalogueProviderBase, self).__init__(parent)

    @property
    def events(self) -> List[EventBase]:
        raise NotImplementedError("events not implemented")


class Catalogue(QObject):
    def __init__(self, catalogue_provider: CatalogueProviderBase, parent: SciQLopMultiPlotPanel):
        super(Catalogue, self).__init__(parent)
        self.catalogue_provider = catalogue_provider
        self._span_collection = MultiPlotsVSpanCollection(parent)
        self.catalogue_provider.event_added.connect(self.add_event)
        self.catalogue_provider.event_removed.connect(self.remove_event)
        count = 0
        self._read_only = True
        for event in self.catalogue_provider.events:
            self.add_event(event)
            count += 1
            if count % 100 == 0:
                sciqlop_application.sciqlop_app().processEvents()

    def remove_event(self, event: EventBase):
        self._span_collection.remove_span(event.uuid)

    def add_event(self, event: EventBase):
        span = self._span_collection.create_span(event.range, color=event.color, read_only=self._read_only,
                                                 tool_tip=event.tool_tip,
                                                 id=event.uuid)
        event.range_changed.connect(lambda r: set_range(span, r), Qt.ConnectionType.QueuedConnection)
        span.range_changed.connect(event.set_range, Qt.ConnectionType.QueuedConnection)
        return event

    @property
    def read_only(self) -> bool:
        return self._read_only

    @read_only.setter
    def read_only(self, value: bool):
        self._read_only = value
        for span in self._span_collection.spans():
            span.read_only = value
