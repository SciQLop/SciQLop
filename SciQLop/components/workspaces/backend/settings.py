from pydantic import Field
from SciQLop.components.settings.backend import ConfigEntry, SettingsCategory
from platformdirs import user_data_dir
import os

DEFAULT_WORKSPACE_DIR = str(
    os.path.join(user_data_dir(appname="sciqlop", appauthor="LPP", ensure_exists=True), "workspaces"))


class SciQLopWorkspacesSettings(ConfigEntry):
    category = SettingsCategory.WORKSPACES
    subcategory = "general"
    workspaces_dir: str = Field(
        default=DEFAULT_WORKSPACE_DIR,
        description="Folder where workspaces are created.",
        json_schema_extra={"widget": "path_dir"})
    reopen_last_workspace: bool = Field(
        default=True,
        description="Start SciQLop in the workspace you used last.")
