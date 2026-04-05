from .entry import ConfigEntry, SettingsCategory


class SciQLopConfigEntry(ConfigEntry):
    category = SettingsCategory.APPLICATION
    subcategory = "general"
    dummy_settings: bool = True
