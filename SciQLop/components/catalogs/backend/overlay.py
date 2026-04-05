from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Qt, QTimer
from datetime import datetime, timezone

from SciQLopPlots import MultiPlotsVSpanCollection
from SciQLop.core import TimeRange
from SciQLop.components.catalogs.backend.provider import CatalogEvent, Catalog, Capability
from SciQLop.components.catalogs.backend.color_palette import color_for_catalog
from SciQLop.components.catalogs.backend.color_mapper import ColorMapper
from SciQLop.components.catalogs.backend.color_mapper_storage import get_color_mapper
from SciQLop.components.sciqlop_logging import getLogger

from speasy.core import make_utc_datetime

log = getLogger(__name__)


def _format_tooltip(event: CatalogEvent, catalog_name: str) -> str:
    lines = [
        f"<b>{catalog_name}</b>",
        f"{event.start.strftime('%Y-%m-%d %H:%M:%S')} — {event.stop.strftime('%Y-%m-%d %H:%M:%S')}",
    ]
    for key, value in event.meta.items():
        lines.append(f"<b>{key}:</b> {value}")
    return "<br>".join(lines)


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
        self._mapper = get_color_mapper(catalog)

        self._span_collection = MultiPlotsVSpanCollection(panel)
        self._event_by_span_id: dict[str, CatalogEvent] = {}
        self._event_connections: dict[str, list[tuple]] = {}  # uuid -> [(signal, slot), ...]

        # React to event list changes
        catalog.provider.events_changed.connect(self._on_events_changed)

        # Decide: lazy or eager
        all_events = catalog.provider.events(catalog)
        self._event_colors = self._mapper(all_events, self._color)
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
        try:
            self._catalog.provider.events_changed.disconnect(self._on_events_changed)
        except RuntimeError:
            pass
        if self._lazy and hasattr(self._panel, 'time_range_changed'):
            try:
                self._panel.time_range_changed.disconnect(self._on_time_range_changed)
            except RuntimeError:
                pass
        for uuid in list(self._event_connections):
            self._disconnect_event(uuid)
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
            span.set_read_only(value)

    def select_event(self, event: CatalogEvent) -> None:
        span = self._span_collection.span(event.uuid)
        if span is not None:
            span.selected = True

    def update_color_mapper(self, mapper: ColorMapper) -> None:
        self._mapper = mapper
        all_events = list(self._event_by_span_id.values())
        self._event_colors = self._mapper(all_events, self._color)
        for uuid in list(self._event_connections):
            self._disconnect_event(uuid)
        for span in self._span_collection.spans():
            self._span_collection.delete_span(span)
        self._event_by_span_id.clear()
        for event in all_events:
            self._add_span(event)

    def _add_span(self, event: CatalogEvent):
        color = self._event_colors.get(event.uuid, self._color)
        tr = TimeRange(event.start.timestamp(), event.stop.timestamp())
        span = self._span_collection.create_span(
            tr,
            color=color,
            read_only=self._read_only,
            tool_tip=_format_tooltip(event, self._catalog.name),
            id=event.uuid,
        )
        self._event_by_span_id[event.uuid] = event

        # Bidirectional sync: event range <-> span range
        # A shared list (mutable) tracks the sync source to break feedback loops.
        sync_source = [None]  # 'span' or 'event'

        span_debounce = QTimer(self)
        span_debounce.setSingleShot(True)
        span_debounce.setInterval(50)

        def _apply_event_to_span(e=event, s=span):
            sync_source[0] = 'event'
            s.set_range(TimeRange(e.start.timestamp(), e.stop.timestamp()))
            sync_source[0] = None

        span_debounce.timeout.connect(_apply_event_to_span)

        def _on_event_changed(t=span_debounce, src=sync_source):
            if src[0] != 'span':
                t.start()

        def _on_span_changed(r, e=event, src=sync_source):
            if src[0] != 'event':
                src[0] = 'span'
                self._on_span_range_changed(r, e)
                src[0] = None

        event.range_changed.connect(_on_event_changed)
        span.range_changed.connect(_on_span_changed)
        _on_selection = lambda selected, e=event: self._on_span_selected(selected, e)
        span.selection_changed.connect(_on_selection)
        _on_delete = lambda e=event: self._on_span_delete_requested(e)
        span.delete_requested.connect(_on_delete)
        self._event_connections[event.uuid] = [
            (event.range_changed, _on_event_changed),
            (span.range_changed, _on_span_changed),
            (span.selection_changed, _on_selection),
            (span.delete_requested, _on_delete),
        ]
        return span

    def _disconnect_event(self, uuid: str) -> None:
        for signal, slot in self._event_connections.pop(uuid, []):
            try:
                signal.disconnect(slot)
            except RuntimeError:
                pass

    def _on_span_range_changed(self, new_range: TimeRange, event: CatalogEvent) -> None:
        event.start = make_utc_datetime(new_range.datetime_start())
        event.stop = make_utc_datetime(new_range.datetime_stop())

    def _on_time_range_changed(self, *args) -> None:
        if self._lazy:
            self._debounce.start()

    def _refresh_visible(self) -> None:
        """Load events visible in the current panel time range (with 2x margin)."""
        try:
            tr = self._panel.time_range
            duration = tr.stop() - tr.start()
            margin = duration  # 1x margin on each side
            start = datetime.fromtimestamp(tr.start() - margin, tz=timezone.utc)
            stop = datetime.fromtimestamp(tr.stop() + margin, tz=timezone.utc)
        except Exception:
            log.debug("Could not get panel time range for lazy refresh", exc_info=True)
            return

        new_events = self._catalog.provider.events(self._catalog, start, stop)
        new_uuids = {e.uuid for e in new_events}
        current_uuids = set(self._event_by_span_id.keys())
        self._event_colors.update(self._mapper(new_events, self._color))

        # Remove out-of-range spans
        for uuid in current_uuids - new_uuids:
            self._disconnect_event(uuid)
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
        self._event_colors = self._mapper(new_events, self._color)

        # Remove stale spans
        for uuid in current_uuids - new_uuids:
            self._disconnect_event(uuid)
            span = self._span_collection.span(uuid)
            if span is not None:
                self._span_collection.delete_span(span)
            self._event_by_span_id.pop(uuid, None)

        # Add new spans
        for event in new_events:
            if event.uuid not in current_uuids:
                self._add_span(event)

    def _on_span_delete_requested(self, event: CatalogEvent) -> None:
        if self._read_only:
            return
        provider = self._catalog.provider
        if Capability.DELETE_EVENTS not in provider.capabilities(self._catalog):
            return
        provider.remove_event(self._catalog, event)

    def _on_span_selected(self, selected: bool, event: CatalogEvent) -> None:
        if selected:
            self.event_clicked.emit(event)
