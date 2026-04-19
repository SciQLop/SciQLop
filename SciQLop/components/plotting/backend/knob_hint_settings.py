from typing import ClassVar

from SciQLop.components.settings.backend.entry import ConfigEntry


class KnobHintSettings(ConfigEntry):
    category: ClassVar[str] = "plotting"
    subcategory: ClassVar[str] = "Knobs"

    parameterized_drop_hint_dismissed: bool = False
