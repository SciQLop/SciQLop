from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Qt, QTimer
from datetime import datetime, timezone

from SciQLopPlots import MultiPlotsVSpanCollection
from SciQLop.core import TimeRange
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
        self._lazy = False

        self._span_collection = MultiPlotsVSpanCollection(panel)
        self._event_by_span_id: dict[str, CatalogEvent] = {}

        # React to event list changes
        catalog.provider.events_changed.connect(self._on_events_changed)

        # Decide: lazy or eager
        all_events = catalog.provider.events(catalog)
        if len(all_events) >= 5000:
            self._lazy = True
            self._debounce = QTimer(self)
            self._debounce.setSingleShot(True)
            self._debounce.setInterval(200)
            self._debounce.timeout.connect(self._refresh_visible)
            # Connect to panel time range changes
            if hasattr(panel, 'time_range_changed'):
                panel.time_range_changed.connect(self._on_time_range_changed)
            self._refresh_visible()
        else:
            for event in all_events:
                self._add_span(event)

    def clear(self) -> None:
        for span in self._span_collection.spans():
            self._span_collection.delete_span(span)
        self._event_by_span_id.clear()

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

    def _on_time_range_changed(self, *args) -> None:
        if self._lazy:
            self._debounce.start()

    def _refresh_visible(self) -> None:
        """Load events visible in the current panel time range (with 2x margin)."""
        try:
            tr = self._panel.time_range
            duration = tr.stop - tr.start
            margin = duration  # 1x margin on each side
            start = datetime.fromtimestamp(tr.start - margin, tz=timezone.utc)
            stop = datetime.fromtimestamp(tr.stop + margin, tz=timezone.utc)
        except Exception:
            return

        new_events = self._catalog.provider.events(self._catalog, start, stop)
        new_uuids = {e.uuid for e in new_events}
        current_uuids = set(self._event_by_span_id.keys())

        # Remove out-of-range spans
        for uuid in current_uuids - new_uuids:
            span = self._span_collection.span(uuid)
            if span is not None:
                self._span_collection.delete_span(span)
            self._event_by_span_id.pop(uuid, None)

        # Add new visible spans
        for event in new_events:
            if event.uuid not in current_uuids:
                self._add_span(event)

    def _on_events_changed(self, changed_catalog: Catalog) -> None:
        if changed_catalog.uuid != self._catalog.uuid:
            return
        if self._lazy:
            self._refresh_visible()
            return
        current_uuids = set(self._event_by_span_id.keys())
        new_events = self._catalog.provider.events(self._catalog)
        new_uuids = {e.uuid for e in new_events}

        # Remove stale spans
        for uuid in current_uuids - new_uuids:
            span = self._span_collection.span(uuid)
            if span is not None:
                self._span_collection.delete_span(span)
            self._event_by_span_id.pop(uuid, None)

        # Add new spans
        for event in new_events:
            if event.uuid not in current_uuids:
                self._add_span(event)

    def _on_span_selected(self, selected: bool, event: CatalogEvent) -> None:
        if selected:
            self.event_clicked.emit(event)
