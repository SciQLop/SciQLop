from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel

from SciQLop.components.settings.backend.entry import ConfigEntry, SettingsCategory


class CatalogViewState(BaseModel):
    """Per-catalog UI state for the event table."""
    hidden_columns: list[str] = []
    column_order: list[str] = []


class EventTableViewState(ConfigEntry):
    """Persisted column visibility/order per catalog. Keyed by catalog.uuid."""
    category: ClassVar[str] = SettingsCategory.CATALOGS
    subcategory: ClassVar[str] = "Event Table"
    states: dict[str, CatalogViewState] = {}


def get_view_state(catalog_uid: str) -> CatalogViewState:
    with EventTableViewState() as settings:
        return settings.states.get(catalog_uid) or CatalogViewState()


def save_view_state(catalog_uid: str, state: CatalogViewState) -> None:
    with EventTableViewState() as settings:
        settings.states[catalog_uid] = state
