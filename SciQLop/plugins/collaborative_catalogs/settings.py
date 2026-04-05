from pydantic import Field
from SciQLop.components.settings import SettingsCategory
from SciQLop.components.settings.backend import ConfigEntry
from SciQLop.components.settings.backend.entry import KeyringMapping


class CollaborativeCatalogsSettings(ConfigEntry):
    category = SettingsCategory.PLUGINS
    subcategory = "Collaborative Catalogs"
    _keyring_ = KeyringMapping("server_url", "username", "password")

    server_url: str = Field(
        default="https://sciqlop.lpp.polytechnique.fr/cocat/",
        description="CoCat server URL",
    )
    username: str = Field(
        default="",
        description="CoCat username (email)",
    )
    password: str = Field(
        default="",
        description="CoCat password",
        json_schema_extra={"widget": "password"},
    )
