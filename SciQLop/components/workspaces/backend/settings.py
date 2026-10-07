from typing import Literal

from pydantic import Field
from SciQLop.components.settings.backend import ConfigEntry, SettingsCategory
from platformdirs import user_data_dir
import os

DEFAULT_WORKSPACE_DIR = str(
    os.path.join(user_data_dir(appname="sciqlop", appauthor="LPP", ensure_exists=True), "workspaces"))


LATEST_RELEASE = "Latest release"
INSTALLERS_VERSION = "Installer's version"


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
    sciqlop_version: Literal["Latest release", "Installer's version"] = Field(
        default=LATEST_RELEASE,
        description="SciQLop version for workspaces. \"Latest release\": new workspaces start "
                    "on the newest release your installer can run, and the welcome page offers "
                    "to update a workspace when a newer one is out. \"Installer's version\": "
                    "workspaces use the version that came with your installer, and updates come "
                    "with a new installer.")
