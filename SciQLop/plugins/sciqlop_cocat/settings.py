from pydantic import Field

from SciQLop.components.settings import SettingsCategory
from SciQLop.components.settings.backend import ConfigEntry


class CocatRsSettings(ConfigEntry):
    """No account fields: signing in happens in the browser, and cocat-rs keeps the token in the
    system keyring."""
    category = SettingsCategory.PLUGINS
    subcategory = "Shared Catalogs (cocat-rs)"

    # The Rust server; production /cocat/ still runs the Python one.
    server_url: str = Field(
        default="https://sciqlop.lpp.polytechnique.fr/cocat-dev/",
        description="CoCat server URL",
        json_schema_extra={"advanced": True},
    )
