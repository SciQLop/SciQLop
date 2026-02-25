from SciQLop.components.settings import ConfigEntry, SettingsCategory


class SciQLopStyle(ConfigEntry):
    category = SettingsCategory.APPEARANCE
    color_palette: str = "light"
