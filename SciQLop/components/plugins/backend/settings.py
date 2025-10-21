from SciQLop.components.settings.backend import ConfigEntry
from platformdirs import user_data_dir
from typing import List
import os


class SciQLopPluginsSettings(ConfigEntry):
    extra_plugins_folders: List[str] = []


USER_PLUGINS_FOLDERS = os.path.join(user_data_dir(appname="sciqlop", appauthor="LPP", ensure_exists=True), "plugins")

if not os.path.exists(USER_PLUGINS_FOLDERS):
    os.makedirs(USER_PLUGINS_FOLDERS, exist_ok=True)
