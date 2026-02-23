from .entry import ConfigEntry, SettingsCategory


class SciQLopConfigEntry(ConfigEntry):
    category = SettingsCategory.APPLICATION
    dummy_settings: bool = True
