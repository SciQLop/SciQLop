from SciQLop.components.settings.backend import ConfigEntry, SettingsCategory
from platformdirs import user_data_dir
import os

DEFAULT_WORKSPACE_DIR = str(
    os.path.join(user_data_dir(appname="sciqlop", appauthor="LPP", ensure_exists=True), "workspaces"))


class SciQLopWorkspacesSettings(ConfigEntry):
    category = SettingsCategory.WORKSPACES
    workspaces_dir: str = DEFAULT_WORKSPACE_DIR
