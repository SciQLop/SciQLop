from typing import ClassVar
from pydantic import Field
from SciQLop.components.settings.backend.entry import ConfigEntry, SettingsCategory


class CommandPaletteSettings(ConfigEntry):
    category: ClassVar[str] = SettingsCategory.APPLICATION
    subcategory: ClassVar[str] = "Command Palette"
    max_history_size: int = Field(
        default=50, description="How many recently used commands to remember.",
        json_schema_extra={"advanced": True})
