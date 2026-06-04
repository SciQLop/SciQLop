from .entry import ConfigEntry, SettingsCategory


class SciQLopConfigEntry(ConfigEntry):
    category = SettingsCategory.APPLICATION
    subcategory = "general"


# Importing the module registers SciQLopNetworkSettings as a ConfigEntry so it
# appears in the settings UI (Application › network).
from . import network  # noqa: E402,F401
