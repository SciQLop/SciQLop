from SciQLop.components.settings import SettingsCategory

from SciQLop.components.settings.backend import ConfigEntry
from pydantic import BaseModel, Field
from platformdirs import user_data_dir
from typing import List, Dict
import os


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


USER_PLUGINS_FOLDERS = os.path.join(user_data_dir(appname="sciqlop", appauthor="LPP", ensure_exists=True), "plugins")

if not os.path.exists(USER_PLUGINS_FOLDERS):
    os.makedirs(USER_PLUGINS_FOLDERS, exist_ok=True)
