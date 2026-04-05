from pydantic import Field
from SciQLop.components.settings import SettingsCategory
from SciQLop.components.settings.backend import ConfigEntry


class ExperimentalCollaborationSettings(ConfigEntry):
    category = SettingsCategory.PLUGINS
    subcategory = "Experimental Collaboration"
    server_url: str = Field(
        default="https://sciqlop.lpp.polytechnique.fr/cache-dev",
        description="Collaboration WebSocket server URL",
    )
