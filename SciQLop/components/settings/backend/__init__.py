from pydantic import Field

from .entry import ConfigEntry, SettingsCategory


class SciQLopConfigEntry(ConfigEntry):
    category = SettingsCategory.APPLICATION
    subcategory = "general"
    show_advanced_settings: bool = Field(default=False, json_schema_extra={"widget": "hidden"})


# Importing the module registers SciQLopNetworkSettings as a ConfigEntry so it
# appears in the settings UI (Application › network).
from . import network  # noqa: E402,F401
