from typing import ClassVar, Literal
from .entry import ConfigEntry, SettingsCategory


class PlotBackendSettings(ConfigEntry):
    category: ClassVar[str] = SettingsCategory.APPLICATION
    subcategory: ClassVar[str] = "Plotting"

    default_speasy_backend: Literal["matplotlib", "sciqlop"] = "matplotlib"
    default_zoom_limit: Literal["1h", "1d", "1w", "1y", "Unlimited"] = "1d"
