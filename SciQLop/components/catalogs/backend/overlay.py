from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Qt

from SciQLopPlots import MultiPlotsVSpanCollection
from SciQLop.core import TimeRange
from SciQLop.components.plotting.backend.time_span_controller import TimeSpanController
from SciQLop.components.catalogs.backend.provider import CatalogEvent, Catalog
from SciQLop.components.catalogs.backend.color_palette import color_for_catalog


class CatalogOverlay(QObject):
    """Draws events from one Catalog as vertical spans on a TimeSyncPanel."""

    event_clicked = Signal(object)  # CatalogEvent

    def __init__(self, catalog: Catalog, panel, parent: QObject | None = None):
        super().__init__(parent or panel)
        self._catalog = catalog
        self._panel = panel
        self._color = color_for_catalog(catalog.uuid)
        self._read_only = True

        self._span_collection = MultiPlotsVSpanCollection(panel)
        self._controller = TimeSpanController(panel, parent=self)
        self._event_by_span_id: dict[str, CatalogEvent] = {}

        events = catalog.provider.events(catalog)
        spans = []
        for event in events:
            span = self._add_span(event)
            spans.append(span)
        self._controller.spans = spans

    @property
    def catalog(self) -> Catalog:
        return self._catalog

    @property
    def span_count(self) -> int:
        return len(self._event_by_span_id)

    @property
    def read_only(self) -> bool:
        return self._read_only

    @read_only.setter
    def read_only(self, value: bool) -> None:
        self._read_only = value
        for span in self._span_collection.spans():
            span.read_only = value

    def select_event(self, event: CatalogEvent) -> None:
        span = self._span_collection.span(event.uuid)
        if span is not None:
            span.selected = True

    def _add_span(self, event: CatalogEvent):
        tr = TimeRange(event.start.timestamp(), event.stop.timestamp())
        span = self._span_collection.create_span(
            tr,
            color=self._color,
            read_only=self._read_only,
            tool_tip=f"{event.start} — {event.stop}",
            id=event.uuid,
        )
        self._event_by_span_id[event.uuid] = event

        # Bidirectional sync: event range <-> span range
        # CatalogEvent.range_changed is Signal() with no args, so we read from event
        event.range_changed.connect(
            lambda e=event, s=span: s.set_range(
                TimeRange(e.start.timestamp(), e.stop.timestamp())
            ),
            Qt.ConnectionType.QueuedConnection,
        )
        span.range_changed.connect(
            lambda r, e=event: self._on_span_range_changed(r, e),
            Qt.ConnectionType.QueuedConnection,
        )
        span.selection_changed.connect(
            lambda selected, e=event: self._on_span_selected(selected, e),
        )
        return span

    def _on_span_range_changed(self, new_range: TimeRange, event: CatalogEvent) -> None:
        from datetime import datetime, timezone
        event.start = datetime.fromtimestamp(new_range.start, tz=timezone.utc)
        event.stop = datetime.fromtimestamp(new_range.stop, tz=timezone.utc)

    def _on_span_selected(self, selected: bool, event: CatalogEvent) -> None:
        if selected:
            self.event_clicked.emit(event)
