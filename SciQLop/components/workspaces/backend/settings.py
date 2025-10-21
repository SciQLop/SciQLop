from SciQLop.components.settings.backend import ConfigEntry
from platformdirs import user_data_dir
import os

DEFAULT_WORKSPACE_DIR = str(
    os.path.join(user_data_dir(appname="sciqlop", appauthor="LPP", ensure_exists=True), "workspaces"))


class SciQLopWorkspacesSettings(ConfigEntry):
    workspaces_dir: str = DEFAULT_WORKSPACE_DIR
