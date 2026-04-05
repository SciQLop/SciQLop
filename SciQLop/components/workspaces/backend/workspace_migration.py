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

    # Keep old workspace.json for backward compatibility with older SciQLop versions
    # old_path.rename(workspace_dir / "workspace.json.bak")

    # Remove old dependencies directory
    deps_dir = workspace_dir / "dependencies"
    if deps_dir.exists():
        shutil.rmtree(deps_dir)

    log.info("Migration complete: %s", manifest_path)
    return True


def _manifest_to_legacy_json(manifest: WorkspaceManifest) -> dict:
    return {
        "name": manifest.name,
        "description": manifest.description,
        "image": manifest.image,
        "default_workspace": manifest.default,
        "dependencies": manifest.requires,
    }


def restore_legacy_json(workspace_dir: Path | str) -> bool:
    """Re-create workspace.json from workspace.sciqlop for backward compatibility.

    Useful for workspaces that were already migrated (workspace.json was renamed
    to .bak or deleted). No-op if workspace.json already exists.

    Returns True if workspace.json was (re)created, False if skipped.
    """
    workspace_dir = Path(workspace_dir)
    old_path = workspace_dir / "workspace.json"
    bak_path = workspace_dir / "workspace.json.bak"
    manifest_path = workspace_dir / "workspace.sciqlop"

    if old_path.exists() or not manifest_path.exists():
        return False

    if bak_path.exists():
        bak_path.rename(old_path)
        log.info("Restored workspace.json from .bak in %s", workspace_dir)
        return True

    manifest = WorkspaceManifest.load(manifest_path)
    old_path.write_text(json.dumps(_manifest_to_legacy_json(manifest), indent=2))
    log.info("Re-created workspace.json for backward compatibility in %s", workspace_dir)
    return True
