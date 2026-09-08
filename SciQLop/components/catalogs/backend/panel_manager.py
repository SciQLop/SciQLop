from __future__ import annotations

from enum import Enum
from uuid import uuid4
from datetime import datetime, timezone

from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtWidgets import QMenu

from SciQLop.components.catalogs.backend.provider import Catalog, Capability, CatalogEvent
from SciQLop.components.catalogs.backend.overlay import CatalogOverlay
from SciQLop.components.catalogs.backend.registry import CatalogRegistry
from SciQLop.components.catalogs.backend.color_palette import (
    color_for_catalog, catalog_color_changed, catalog_swatch_icon,
)


class InteractionMode(Enum):
    VIEW = "view"
    JUMP = "jump"
    EDIT = "edit"


class PanelCatalogManager(QObject):
    """Manages catalog overlays and interaction mode for one TimeSyncPanel."""

    event_clicked = Signal(object)  # CatalogEvent
    catalog_event_clicked = Signal(object, object)  # Catalog, CatalogEvent

    def __init__(self, panel, parent: QObject | None = None):
        super().__init__(parent or panel)
        self._panel = panel
        self._overlays: dict[str, CatalogOverlay] = {}
        self._mode = InteractionMode.VIEW
        self._bar_connected = False
        self._panel.span_created.connect(self._on_span_created)
        registry = CatalogRegistry.instance()
        for provider in registry.providers():
            self._bind_provider(provider)
        registry.provider_registered.connect(self._bind_provider)
        catalog_color_changed.connect(self._on_catalog_color_changed)
        from SciQLop.components.catalogs.backend.color_mapper_storage import color_mapper_changed
        color_mapper_changed.connect(self._on_color_mapper_changed)

    def _on_color_mapper_changed(self, uuid: str) -> None:
        from SciQLop.components.catalogs.backend.color_mapper_storage import get_color_mapper
        overlay = self._overlays.get(uuid)
        if overlay is not None:
            overlay.update_color_mapper(get_color_mapper(overlay.catalog))

    def _bind_provider(self, provider) -> None:
        provider.catalog_removed.connect(self.remove_catalog)

    def _on_catalog_color_changed(self, uuid: str) -> None:
        overlay = self._overlays.get(uuid)
        if overlay is not None:
            overlay.color = color_for_catalog(uuid)
        self._apply_span_creation_state()

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
        chrome = getattr(self._panel, '_catalog_chrome', None)
        if chrome is not None:
            chrome.mode = value.value

    def add_catalog(self, catalog: Catalog) -> None:
        if catalog.uuid in self._overlays:
            return
        overlay = CatalogOverlay(catalog=catalog, panel=self._panel, parent=self)
        overlay.event_clicked.connect(lambda event, c=catalog: self._on_event_clicked(event, c))
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

    @property
    def jump_zoom_out_factor(self) -> float:
        """Visible range around a picked event as a multiple of its duration."""
        chrome = self._catalog_chrome()
        if chrome is not None:
            return chrome.zoom_out_factor
        from SciQLop.components.catalogs.backend.jump_settings import CatalogJumpSettings
        return CatalogJumpSettings().zoom_out_factor

    def _jump_to_event(self, event: CatalogEvent) -> None:
        from SciQLop.core import TimeRange
        duration = event.stop.timestamp() - event.start.timestamp()
        if duration <= 0:
            margin = 3600.0  # 1 hour fallback for zero-duration events
        else:
            margin = duration * (self.jump_zoom_out_factor - 1) / 2
        self._panel.time_range = TimeRange(
            event.start.timestamp() - margin,
            event.stop.timestamp() + margin,
        )

    def select_event(self, event: CatalogEvent) -> None:
        for overlay in self._overlays.values():
            overlay.select_event(event)
        if self._mode == InteractionMode.JUMP:
            self._jump_to_event(event)

    def build_catalogs_menu(self, parent_menu: QMenu) -> QMenu:
        menu = parent_menu.addMenu("Catalogs")
        self._add_loaded_catalog_entries(menu)
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

    def _add_loaded_catalog_entries(self, menu: QMenu) -> None:
        """One submenu per catalog shown on this panel: remove it, or reach
        its color actions without a trip to the catalog tree."""
        if not self._overlays:
            return
        for overlay in self._overlays.values():
            self._add_loaded_catalog_submenu(menu, overlay.catalog)
        menu.addSeparator()

    def _add_loaded_catalog_submenu(self, menu: QMenu, catalog: Catalog) -> None:
        from SciQLop.components.catalogs.ui.color_menus import (
            add_catalog_color_actions, build_color_by_menu, sample_events,
        )
        sub = menu.addMenu(catalog_swatch_icon(catalog.uuid), catalog.name)
        sub.setObjectName(f"loaded_catalog_{catalog.uuid}")
        remove_action = sub.addAction("Remove from panel")
        remove_action.triggered.connect(lambda: self.remove_catalog(catalog))
        sub.addSeparator()
        add_catalog_color_actions(sub, catalog, dialog_parent=self._panel)
        build_color_by_menu(sub, catalog, sample_events(catalog), dialog_parent=self._panel)

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

    def _catalog_chrome(self):
        chrome = getattr(self._panel, '_catalog_chrome', None)
        if chrome is not None and not self._bar_connected:
            chrome.target_changed.connect(lambda _: self._apply_span_creation_state())
            chrome.mode_changed.connect(self._on_chrome_mode_changed)
            chrome.zoom_out_changed.connect(self._on_zoom_out_changed)
            chrome.mode = self._mode.value
            self._bar_connected = True
        return chrome

    @staticmethod
    def _on_zoom_out_changed(value: float) -> None:
        from SciQLop.components.catalogs.backend.jump_settings import CatalogJumpSettings
        with CatalogJumpSettings() as settings:
            settings.zoom_out_factor = value

    def _on_chrome_mode_changed(self, value: str) -> None:
        try:
            self.mode = InteractionMode(value)
        except ValueError:
            pass

    def _update_creation_target_choices(self) -> None:
        chrome = self._catalog_chrome()
        if chrome is None:
            return
        if self._mode != InteractionMode.EDIT:
            chrome.clear_targets()
            return
        editable = self._editable_catalogs()
        chrome.set_targets([(c.name, c.uuid) for c in editable])

    def _apply_span_creation_state(self) -> None:
        chrome = self._catalog_chrome()
        if chrome is None:
            return
        uuid = chrome.selected_target()
        enabled = self._mode == InteractionMode.EDIT and uuid is not None
        self._panel.set_span_creation_enabled(enabled)
        if enabled:
            if hasattr(self._panel, 'set_span_creation_modifier'):
                self._panel.set_span_creation_modifier(Qt.ShiftModifier)
            self._panel.set_span_creation_color(color_for_catalog(uuid))

    def _on_span_created(self, raw_span) -> None:
        chrome = self._catalog_chrome()
        if self._mode != InteractionMode.EDIT or chrome is None:
            raw_span.deleteLater()
            return
        target_uuid = chrome.selected_target()
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

    def _on_event_clicked(self, event: CatalogEvent, catalog: Catalog | None = None) -> None:
        self.event_clicked.emit(event)
        self.catalog_event_clicked.emit(catalog, event)
