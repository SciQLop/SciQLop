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
    extra_plugins_folders: List[str] = Field(
        default=[],
        description="Additional folders scanned for plugins at startup.",
        json_schema_extra={"widget": "list_path"})
    plugins: Dict[str, PluginConfig] = Field(
        default={},
        description="Enable or disable installed plugins; changes take "
                    "effect after restart.",
        json_schema_extra={"widget": "plugins_dict"})
    installed_packages: Dict[str, InstalledPackage] = Field(default={}, json_schema_extra={"widget": "hidden"})

    @model_validator(mode="after")
    def _rekey_installed_packages_by_canonical_name(self) -> "SciQLopPluginsSettings":
        """Heal entries left keyed by the store's display name (pre-fix
        YAML) so every lookup, on load or on fresh construction, finds them
        under their canonical distribution name.

        Two entries can canonicalise to the same key -- a stale display-name
        entry left behind next to a fresh, canonical-keyed one after a store
        rename. ``ConfigEntry.save()`` dumps with ``sort_keys=True`` (the
        default), so on-disk order is alphabetical by the OLD key, not
        write order -- it cannot be used to tell which entry is "freshest".
        Instead, prefer whichever entry's own key already equals the
        canonical name: it was written by this fixed code, so it is the
        trustworthy one. Between two non-canonically-keyed entries (both
        pre-fix), fall back to keeping the last one seen. Either way the
        collision is logged rather than silently dropped.
        """
        rekeyed: Dict[str, InstalledPackage] = {}
        winner_is_canonical_keyed: Dict[str, bool] = {}
        for key, pkg in self.installed_packages.items():
            canonical = canonical_package_name(pkg.name)
            this_is_canonical_keyed = key == canonical
            if canonical in rekeyed:
                if winner_is_canonical_keyed[canonical] and not this_is_canonical_keyed:
                    log.warning(
                        f"Duplicate installed_packages entry for {canonical!r}; "
                        "keeping the canonical-keyed one"
                    )
                    continue
                log.warning(f"Duplicate installed_packages entry for {canonical!r}; keeping the later one")
            rekeyed[canonical] = pkg
            winner_is_canonical_keyed[canonical] = this_is_canonical_keyed
        self.installed_packages = rekeyed
        return self


USER_PLUGINS_FOLDERS = os.path.join(user_data_dir(appname="sciqlop", appauthor="LPP", ensure_exists=True), "plugins")

if not os.path.exists(USER_PLUGINS_FOLDERS):
    os.makedirs(USER_PLUGINS_FOLDERS, exist_ok=True)
