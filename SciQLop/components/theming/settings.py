from pydantic import Field
from SciQLop.components.settings import ConfigEntry, SettingsCategory


class SciQLopStyle(ConfigEntry):
    category = SettingsCategory.APPEARANCE
    subcategory = "style"
    color_palette: str = Field(
        default="space",
        description="Color theme of the interface; applies instantly.",
        json_schema_extra={"widget": "combo", "choices": ["light", "dark", "neutral", "space"]},
    )
