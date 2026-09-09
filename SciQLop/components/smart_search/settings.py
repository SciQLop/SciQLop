from typing import Literal

from pydantic import Field

from SciQLop.components.settings import SettingsCategory
from SciQLop.components.settings.backend import ConfigEntry

AVAILABLE_MODELS = ("minishlab/potion-base-8M", "minishlab/potion-base-32M")


class SmartSearchSettings(ConfigEntry):
    category = SettingsCategory.APPLICATION
    subcategory = "Smart Search"

    enabled: bool = Field(
        default=False,
        description="Rank product search results by meaning, not only by "
                    "exact words (downloads a small model on first use).")
    model: Literal[
        "minishlab/potion-base-8M", "minishlab/potion-base-32M"
    ] = Field(
        default=AVAILABLE_MODELS[0],
        description="Embedding model used for ranking; the larger one is "
                    "slower but more accurate.")
