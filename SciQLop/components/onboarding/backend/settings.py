from typing import ClassVar, Dict

from pydantic import Field

from SciQLop.components.settings.backend.entry import ConfigEntry, SettingsCategory


class OnboardingSettings(ConfigEntry):
    category: ClassVar[str] = SettingsCategory.APPLICATION
    subcategory: ClassVar[str] = "Onboarding"

    completed_tours: Dict[str, bool] = Field(default_factory=dict)
    tour_offered: bool = Field(
        default=False, json_schema_extra={"widget": "hidden"},
        description="The first-start offer to take the tour was shown; it is shown once.")
