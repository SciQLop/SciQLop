"""High-level workspace preparation orchestrator.

Called by the launcher before spawning the Qt application.  Given a workspace
directory it ensures the manifest, pyproject.toml, and virtual environment are
all in place, then returns the path to the venv's Python executable.
"""

from __future__ import annotations

import logging
from pathlib import Path

from SciQLop.components.plugins.backend.loader.loader import plugins_folders
from SciQLop.components.plugins.backend.settings import SciQLopPluginsSettings
from SciQLop.core.plugin_deps import collect_plugin_dependencies
from SciQLop.core.workspace_manifest import WorkspaceManifest
from SciQLop.core.workspace_migration import migrate_workspace
from SciQLop.core.workspace_project import generate_pyproject_toml
from SciQLop.core.workspace_venv import WorkspaceVenv

log = logging.getLogger(__name__)

MANIFEST_FILENAME = "workspace.sciqlop"


def get_globally_enabled_plugins() -> list[str]:
    """Return names of globally enabled plugins from settings."""
    settings = SciQLopPluginsSettings()
    return [name for name, cfg in settings.plugins.items() if cfg.enabled]


def get_plugin_folders() -> list[str]:
    """Return all plugin search folders."""
    return plugins_folders()


def prepare_workspace(
    workspace_dir: Path | str,
    workspace_name: str | None = None,
    locked: bool = False,
) -> Path:
    """Prepare a workspace: ensure manifest, generate pyproject.toml, sync venv.

    Parameters
    ----------
    workspace_dir:
        Path to the workspace directory (created if it does not exist).
    workspace_name:
        Human-readable name for a new workspace.  Ignored when a manifest
        already exists.  Defaults to the directory name.
    locked:
        If ``True``, pass ``locked=True`` to ``venv.sync()`` (useful when
        importing from an archive that ships a lock file).

    Returns
    -------
    Path
        Path to the workspace venv's Python executable.
    """
    workspace_dir = Path(workspace_dir)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    # Migrate from old workspace.json format if needed
    if migrate_workspace(workspace_dir):
        log.info("Workspace migrated from old format in %s", workspace_dir)

    manifest_path = workspace_dir / MANIFEST_FILENAME

    # Step 1: Load or create manifest
    if manifest_path.exists():
        log.info("Loading existing manifest from %s", manifest_path)
        manifest = WorkspaceManifest.load(manifest_path)
    else:
        name = workspace_name or workspace_dir.name
        log.info("Creating default manifest for workspace %r", name)
        manifest = WorkspaceManifest.default(name)
        manifest.save(manifest_path)

    # Step 2: Gather plugin information
    enabled_plugins = get_globally_enabled_plugins()
    plugin_folders = get_plugin_folders()

    # Step 3: Collect plugin dependencies with workspace overrides
    plugin_deps = collect_plugin_dependencies(
        plugin_folders=plugin_folders,
        enabled_plugins=enabled_plugins,
        workspace_plugins_add=manifest.plugins_add,
        workspace_plugins_remove=manifest.plugins_remove,
    )

    # Step 4: Generate pyproject.toml
    pyproject_path = workspace_dir / "pyproject.toml"
    generate_pyproject_toml(manifest, plugin_deps, pyproject_path)

    # Step 5: Ensure venv exists and sync
    venv = WorkspaceVenv(workspace_dir)
    venv.ensure()
    venv.sync(locked=locked)

    return venv.python_path
