from .workspace import Workspace
from .workspaces_manager import WorkspaceManager


def existing_workspaces():
    return [os.path.basename(d) for d in os.listdir(WORKSPACES_DIR_CONFIG_ENTRY.get()) if os.path.isdir(os.path.join(WORKSPACES_DIR_CONFIG_ENTRY.get(), d))]