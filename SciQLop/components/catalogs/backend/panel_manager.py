from __future__ import annotations

from enum import Enum
from uuid import uuid4
from datetime import datetime, timezone

from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtWidgets import QMenu

from SciQLop.components.catalogs.backend.provider import Catalog, Capability, CatalogEvent
from SciQLop.components.catalogs.backend.overlay import CatalogOverlay
from SciQLop.components.catalogs.backend.registry import CatalogRegistry
from SciQLop.components.catalogs.backend.color_palette import color_for_catalog


class InteractionMode(Enum):
    VIEW = "view"
    JUMP = "jump"
    EDIT = "edit"


class PanelCatalogManager(QObject):
    """Manages catalog overlays and interaction mode for one TimeSyncPanel."""

    event_clicked = Signal(object)  # CatalogEvent

    def __init__(self, panel, parent: QObject | None = None):
        super().__init__(parent or panel)
        self._panel = panel
        self._overlays: dict[str, CatalogOverlay] = {}
        self._mode = InteractionMode.VIEW
        self._bar_connected = False
        self._panel.span_created.connect(self._on_span_created)

    @property
    def panel(self):
        return self._panel

    @property
    def catalog_uuids(self) -> set[str]:
        return set(self._overlays.keys())

    @property
    def mode(self) -> InteractionMode:
        return self._mode

    @mode.setter
    def mode(self, value: InteractionMode) -> None:
        self._mode = value
        for uuid, overlay in self._overlays.items():
            if value == InteractionMode.EDIT:
                caps = overlay.catalog.provider.capabilities(overlay.catalog)
                overlay.read_only = Capability.EDIT_EVENTS not in caps
            else:
                overlay.read_only = True
        self._update_creation_target_choices()
        self._apply_span_creation_state()

    def add_catalog(self, catalog: Catalog) -> None:
        if catalog.uuid in self._overlays:
            return
        overlay = CatalogOverlay(catalog=catalog, panel=self._panel, parent=self)
        overlay.event_clicked.connect(self._on_event_clicked)
        self._overlays[catalog.uuid] = overlay
        # Apply current mode
        if self._mode == InteractionMode.EDIT:
            caps = catalog.provider.capabilities(catalog)
            overlay.read_only = Capability.EDIT_EVENTS not in caps
        else:
            overlay.read_only = True
        self._update_creation_target_choices()
        self._apply_span_creation_state()

    def remove_catalog(self, catalog: Catalog) -> None:
        overlay = self._overlays.pop(catalog.uuid, None)
        if overlay is not None:
            overlay.clear()
            overlay.deleteLater()
        self._update_creation_target_choices()
        self._apply_span_creation_state()

    def overlay(self, catalog_uuid: str) -> CatalogOverlay | None:
        return self._overlays.get(catalog_uuid)

    def select_event(self, event: CatalogEvent) -> None:
        for overlay in self._overlays.values():
            overlay.select_event(event)
        if self._mode == InteractionMode.JUMP:
            from SciQLop.core import TimeRange
            duration = event.stop.timestamp() - event.start.timestamp()
            if duration <= 0:
                margin = 3600.0  # 1 hour fallback for zero-duration events
            else:
                margin = duration * 4.5
            tr = TimeRange(
                event.start.timestamp() - margin,
                event.stop.timestamp() + margin,
            )
            self._panel.time_range = tr

    def build_catalogs_menu(self, parent_menu: QMenu) -> QMenu:
        menu = parent_menu.addMenu("Catalogs")
        registry = CatalogRegistry.instance()
        for provider in registry.providers():
            provider_menu = QMenu(provider.name, menu)
            menu.addMenu(provider_menu)
            for catalog in provider.catalogs():
                target_menu = self._get_or_create_submenu(provider_menu, catalog.path)
                action = target_menu.addAction(catalog.name)
                action.setCheckable(True)
                action.setChecked(catalog.uuid in self._overlays)
                action.toggled.connect(
                    lambda checked, c=catalog: self.add_catalog(c) if checked else self.remove_catalog(c)
                )

        menu.addSeparator()
        mode_menu = QMenu("Mode", menu)
        menu.addMenu(mode_menu)
        for m in InteractionMode:
            action = mode_menu.addAction(m.value.capitalize())
            action.setCheckable(True)
            action.setChecked(m == self._mode)
            action.triggered.connect(lambda checked, mode=m: setattr(self, 'mode', mode))
        return menu

    @staticmethod
    def _get_or_create_submenu(menu: QMenu, path: list[str]) -> QMenu:
        current = menu
        for segment in path:
            existing = None
            for action in current.actions():
                if action.menu() and action.text() == segment:
                    existing = action.menu()
                    break
            if existing is not None:
                current = existing
            else:
                submenu = QMenu(segment, current)
                current.addMenu(submenu)
                current = submenu
        return current

    def _editable_catalogs(self) -> list[Catalog]:
        result = []
        for overlay in self._overlays.values():
            cat = overlay.catalog
            caps = cat.provider.capabilities(cat)
            if Capability.CREATE_EVENTS in caps:
                result.append(cat)
        return result

    def _time_range_bar(self):
        bar = getattr(self._panel, '_time_range_bar', None)
        if bar is not None and not self._bar_connected:
            bar.catalog_choice_changed.connect(lambda _: self._apply_span_creation_state())
            self._bar_connected = True
        return bar

    def _update_creation_target_choices(self) -> None:
        bar = self._time_range_bar()
        if bar is None:
            return
        if self._mode != InteractionMode.EDIT:
            bar.clear_catalog_choices()
            return
        editable = self._editable_catalogs()
        bar.set_catalog_choices([(c.name, c.uuid) for c in editable])

    def _apply_span_creation_state(self) -> None:
        bar = self._time_range_bar()
        if bar is None:
            return
        uuid = bar.selected_catalog_uuid()
        enabled = self._mode == InteractionMode.EDIT and uuid is not None
        self._panel.set_span_creation_enabled(enabled)
        if enabled:
            if hasattr(self._panel, 'set_span_creation_modifier'):
                self._panel.set_span_creation_modifier(Qt.ShiftModifier)
            self._panel.set_span_creation_color(color_for_catalog(uuid))

    def _on_span_created(self, raw_span) -> None:
        bar = self._time_range_bar()
        if self._mode != InteractionMode.EDIT or bar is None:
            raw_span.deleteLater()
            return
        target_uuid = bar.selected_catalog_uuid()
        if target_uuid is None:
            raw_span.deleteLater()
            return
        tr = raw_span.range
        raw_span.deleteLater()
        overlay = self._overlays.get(target_uuid)
        if overlay is None:
            return
        cat = overlay.catalog
        start = datetime.fromtimestamp(tr.start(), tz=timezone.utc)
        stop = datetime.fromtimestamp(tr.stop(), tz=timezone.utc)
        event = CatalogEvent(uuid=str(uuid4()), start=start, stop=stop)
        cat.provider.add_event(cat, event)

    def _on_event_clicked(self, event: CatalogEvent) -> None:
        if self._mode == InteractionMode.JUMP:
            from SciQLop.core import TimeRange
            margin = (event.stop.timestamp() - event.start.timestamp()) * 0.5
            tr = TimeRange(
                event.start.timestamp() - margin,
                event.stop.timestamp() + margin,
            )
            self._panel.time_range = tr
        self.event_clicked.emit(event)
