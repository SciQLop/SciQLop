"""Workspaces public surface — lazy re-exports.

Importing the convenience names (`WorkspaceManager`, `Workspace`, ...) used to
fire eagerly here, which dragged the full workspaces backend (and its
transitive `SciQLop.core` + `speasy.core` chain) into the launcher process
before the splash window could be shown. PEP 562 `__getattr__` defers
each import until first attribute access, so callers like
`from SciQLop.components.workspaces.backend.settings import ...` no longer
pay the cost.
"""
from importlib import import_module
from typing import TYPE_CHECKING, Any


_LAZY: dict[str, tuple[str, str]] = {
    "WorkspaceManager": (".backend.workspaces_manager", "WorkspaceManager"),
    "workspaces_manager_instance": (".backend.workspaces_manager", "workspaces_manager_instance"),
    "Workspace": (".backend.workspace", "Workspace"),
    "SciQLopWorkspacesSettings": (".backend.settings", "SciQLopWorkspacesSettings"),
    "WorkspaceManifest": (".backend.workspace_manifest", "WorkspaceManifest"),
}


def __getattr__(name: str) -> Any:
    target = _LAZY.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_path, attr = target
    return getattr(import_module(module_path, package=__name__), attr)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY))


if TYPE_CHECKING:
    from .backend.workspaces_manager import WorkspaceManager, workspaces_manager_instance
    from .backend.workspace import Workspace
    from .backend.settings import SciQLopWorkspacesSettings
    from .backend.workspace_manifest import WorkspaceManifest
