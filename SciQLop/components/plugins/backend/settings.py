from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.components.settings import SettingsCategory

from SciQLop.components.settings.backend import ConfigEntry
from pydantic import BaseModel, Field, model_validator
from platformdirs import user_data_dir
from typing import List, Dict
import os

log = getLogger(__name__)


def canonical_package_name(name: str) -> str:
    """Fold a distribution name to its canonical form, e.g. ``My_Plugin`` ->
    ``my-plugin``. This is the key `installed_packages` is stored under."""
    return name.lower().replace("_", "-")


class PluginConfig(BaseModel):
    enabled: bool = True


class InstalledPackage(BaseModel):
    pip: str
    name: str


class SciQLopPluginsSettings(ConfigEntry):
    category = SettingsCategory.PLUGINS
    subcategory = "general"
    extra_plugins_folders: List[str] = Field(default=[], json_schema_extra={"widget": "list_path"})
    plugins: Dict[str, PluginConfig] = Field(default={}, json_schema_extra={"widget": "plugins_dict"})
    installed_packages: Dict[str, InstalledPackage] = Field(default={}, json_schema_extra={"widget": "hidden"})

    @model_validator(mode="after")
    def _rekey_installed_packages_by_canonical_name(self) -> "SciQLopPluginsSettings":
        """Heal entries left keyed by the store's display name (pre-fix
        YAML) so every lookup, on load or on fresh construction, finds them
        under their canonical distribution name.

        Two entries can canonicalise to the same key -- a stale display-name
        entry left behind next to a fresh one after a store rename. YAML
        preserves write order, so the later entry is the freshest; it wins,
        and the collision is logged rather than silently dropped.
        """
        rekeyed: Dict[str, InstalledPackage] = {}
        for pkg in self.installed_packages.values():
            key = canonical_package_name(pkg.name)
            if key in rekeyed:
                log.warning(f"Duplicate installed_packages entry for {key!r}; keeping the later one")
            rekeyed[key] = pkg
        self.installed_packages = rekeyed
        return self


USER_PLUGINS_FOLDERS = os.path.join(user_data_dir(appname="sciqlop", appauthor="LPP", ensure_exists=True), "plugins")

if not os.path.exists(USER_PLUGINS_FOLDERS):
    os.makedirs(USER_PLUGINS_FOLDERS, exist_ok=True)
