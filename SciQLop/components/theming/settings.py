from pydantic import Field
from SciQLop.components.settings import ConfigEntry, SettingsCategory


class SciQLopStyle(ConfigEntry):
    category = SettingsCategory.APPEARANCE
    subcategory = "style"
    color_palette: str = Field(
        default="light",
        json_schema_extra={"widget": "combo", "choices": ["light", "dark", "neutral", "space"]},
    )
