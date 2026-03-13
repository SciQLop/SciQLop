from typing import ClassVar
from SciQLop.components.settings.backend.entry import ConfigEntry, SettingsCategory


class CommandPaletteSettings(ConfigEntry):
    category: ClassVar[str] = SettingsCategory.APPLICATION
    subcategory: ClassVar[str] = "Command Palette"
    keybinding: str = "Ctrl+K"
    max_history_size: int = 50
