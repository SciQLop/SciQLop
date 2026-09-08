from __future__ import annotations

from typing import ClassVar

from pydantic import Field

from SciQLop.components.settings.backend.entry import ConfigEntry, SettingsCategory


class CatalogJumpSettings(ConfigEntry):
    """How far the panel zooms out around an event picked in Jump mode:
    the visible range is ``zoom_out_factor`` times the event duration,
    centered on the event (1 = the event fills the panel)."""
    category: ClassVar[str] = SettingsCategory.CATALOGS
    subcategory: ClassVar[str] = "Jump"
    zoom_out_factor: float = Field(default=2.0, ge=1.0, le=100.0)
