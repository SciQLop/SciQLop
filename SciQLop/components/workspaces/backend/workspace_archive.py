"""Export and import SciQLop workspace archives.

Archive format: a zip file with ``.sciqlop-archive`` extension containing
workspace files (manifest, lockfile, notebooks, scripts) but excluding
transient files (.venv, pyproject.toml, __pycache__).
"""

import zipfile
from pathlib import Path

from .workspace_reset import is_reset_leftover

# Rebuilt from the manifest, so never copied: the venv and caches at any depth,
# the generated pyproject.toml only at the root (a nested one is the user's own package),
# and environments a reset renamed aside (see workspace_reset).
EXCLUDED_ANYWHERE = {".venv", ".venv-b", "__pycache__"}
EXCLUDED_AT_ROOT = {"pyproject.toml", ".sciqlop_venv", ".sciqlop_venv_next"}  # see venv_slots

# Marker left by import_workspace() so prepare_workspace() knows to sync
# --locked against the archive's shipped uv.lock, without every caller
# having to pass locked=True. Removed once a sync actually succeeds.
IMPORT_MARKER_NAME = ".sciqlop_imported"


def is_excluded(path: Path) -> bool:
    """Whether *path*, relative to the workspace root, is left out of a copy or archive."""
    return (any(part in EXCLUDED_ANYWHERE for part in path.parts) or str(path) in EXCLUDED_AT_ROOT
            or bool(path.parts) and is_reset_leftover(path.parts[0]))


def export_workspace(workspace_dir: Path | str, archive_path: Path | str) -> None:
    """Create a .sciqlop-archive from a workspace directory."""
    workspace_dir = Path(workspace_dir)
    archive_path = Path(archive_path)

    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in sorted(workspace_dir.rglob("*")):
            if not file.is_file():
                continue
            rel = file.relative_to(workspace_dir)
            if is_excluded(rel):
                continue
            zf.write(file, arcname=str(rel))


def import_workspace(archive_path: Path | str, target_dir: Path | str) -> Path:
    """Extract a .sciqlop-archive to a target directory. Returns target_dir."""
    archive_path = Path(archive_path)
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(archive_path, "r") as zf:
        zf.extractall(target_dir)

    (target_dir / IMPORT_MARKER_NAME).touch()

    return target_dir
