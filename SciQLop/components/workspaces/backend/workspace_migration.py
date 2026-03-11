"""Migration from old workspace.json format to .sciqlop TOML manifest."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest

log = logging.getLogger(__name__)


def migrate_workspace(workspace_dir: Path | str) -> bool:
    """Migrate workspace from old JSON format to .sciqlop TOML.

    Returns True if migration was performed, False if skipped.
    """
    workspace_dir = Path(workspace_dir)
    manifest_path = workspace_dir / "workspace.sciqlop"
    old_path = workspace_dir / "workspace.json"

    # Already migrated
    if manifest_path.exists():
        return False

    # Nothing to migrate
    if not old_path.exists():
        return False

    log.info("Migrating old workspace.json in %s", workspace_dir)

    with open(old_path, "r") as f:
        old_data = json.load(f)

    manifest = WorkspaceManifest(
        name=old_data.get("name", workspace_dir.name),
        description=old_data.get("description", ""),
        image=old_data.get("image", ""),
        default=old_data.get("default_workspace", False),
        requires=old_data.get("dependencies", []),
    )
    manifest.save(manifest_path)
    WorkspaceManifest.touch_last_used(workspace_dir)

    # Backup old file
    old_path.rename(workspace_dir / "workspace.json.bak")

    # Remove old dependencies directory
    deps_dir = workspace_dir / "dependencies"
    if deps_dir.exists():
        shutil.rmtree(deps_dir)

    log.info("Migration complete: %s", manifest_path)
    return True
