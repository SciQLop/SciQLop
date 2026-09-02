"""High-level workspace preparation orchestrator.

Called by the launcher before spawning the Qt application.  Given a workspace
directory it ensures the manifest, pyproject.toml, and virtual environment are
all in place, then returns the path to the venv's Python executable.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from SciQLop.components.plugins.backend.folders import plugins_folders
from SciQLop.components.plugins.backend.settings import SciQLopPluginsSettings
from SciQLop.components.plugins.plugin_deps import collect_plugin_dependencies
from SciQLop.components.workspaces.backend.workspace_archive import IMPORT_MARKER_NAME
from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest
from SciQLop.components.workspaces.backend.workspace_migration import migrate_workspace
from SciQLop.components.workspaces.backend.lab_assets import repair_lab_assets
from SciQLop.components.workspaces.backend.workspace_project import (
    generate_pyproject_toml,
    running_sciqlop_version,
)
from SciQLop.components.workspaces.backend.workspace_venv import WorkspaceVenv

log = logging.getLogger(__name__)

MANIFEST_FILENAME = "workspace.sciqlop"


def get_globally_enabled_plugins() -> list[str]:
    """Return names of globally enabled plugins from settings."""
    settings = SciQLopPluginsSettings()
    return [name for name, cfg in settings.plugins.items() if cfg.enabled]


def get_plugin_folders() -> list[str]:
    """Return all plugin search folders."""
    return plugins_folders()


def _try_sync(venv: WorkspaceVenv, *, locked: bool, on_output) -> Exception | None:
    try:
        venv.sync(locked=locked, on_output=on_output)
        return None
    except Exception as exc:
        return exc


def _report_sync_failure(exc: Exception, on_output, *, core_only: bool = False) -> None:
    label = "Core-only sync" if core_only else "Workspace dependency sync"
    log.warning("%s failed: %s", label, exc)
    if on_output is not None:
        on_output(f"{label} failed: {exc}")


def _sync_workspace_venv(
    venv: WorkspaceVenv,
    manifest: WorkspaceManifest,
    optional_deps: list[str],
    pyproject_path: Path,
    locked: bool,
    on_output: Callable[[str], None] | None,
) -> bool:
    """Sync the workspace venv, isolating a broken plugin/appstore dependency.

    The plugin loader already tolerates one plugin failing to import — it
    logs and skips just that plugin (see loader.load_plugin) — so a single
    incompatible plugin or appstore package (e.g. a published release still
    pinned to an old SciQLop range) must not keep SciQLop itself from
    starting. If the full dependency set fails to resolve, retry with only
    the core app's own dependencies so it can still launch; only if even
    that fails do we fall back to (or give up on) whatever is already in the
    venv.

    ``locked`` (importing a workspace archive) tries to reproduce the exact,
    previously-working environment first. But an archive can outlive the
    SciQLop version that made it (e.g. its pinned ``sciqlop[all]==X`` no
    longer exists), in which case honoring the lock is impossible — a fresh
    venv must never be left empty because of a stale archive lock, so a
    failed locked sync falls back to a normal unlocked one (with its own
    plugin-isolation retry) instead of giving up.

    Returns ``True`` when a sync actually installed the requested
    dependencies, ``False`` when every attempt failed and this instead fell
    through to keeping whatever was already in the venv (offline /
    unreachable index, #115). Callers rely on this to tell "the environment
    now matches what was asked for" from "we're just limping along on the
    old one".
    """
    exc = _try_sync(venv, locked=locked, on_output=on_output)
    if exc is None:
        return True
    _report_sync_failure(exc, on_output)

    if locked:
        if on_output is not None:
            on_output("Archive lockfile could not be honored, resolving fresh")
        return _sync_workspace_venv(venv, manifest, optional_deps, pyproject_path, False, on_output)

    if optional_deps:
        if on_output is not None:
            on_output(
                "Retrying with just the core app (dropping plugin/appstore "
                "dependencies)..."
            )
        generate_pyproject_toml(manifest, [], pyproject_path)
        exc = _try_sync(venv, locked=False, on_output=on_output)
        if exc is None:
            # M1: put the full dependency set back on disk (not synced) so
            # the next launch and the appstore see the intended set again,
            # instead of the core-only one the retry just wrote.
            generate_pyproject_toml(manifest, optional_deps, pyproject_path)
            return True
        _report_sync_failure(exc, on_output, core_only=True)

    if not venv.has_sciqlop_installed:
        # No working install to fall back to.
        raise exc
    # Offline / unreachable index (#115): keep starting with the existing
    # venv so the user can still use bundled features (CDF, local files).
    if on_output is not None:
        on_output(
            "Continuing with existing venv. Run with network to install "
            "missing packages."
        )
    return False


def prepare_workspace(
    workspace_dir: Path | str,
    workspace_name: str | None = None,
    locked: bool = False,
    on_output: Callable[[str], None] | None = None,
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
        importing from an archive that ships a lock file). A workspace
        carrying the ``.sciqlop_imported`` marker (see ``import_workspace``)
        is treated as locked for this run regardless of this argument.

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
        manifest = WorkspaceManifest.load_or_repair(manifest_path)
    else:
        name = workspace_name or workspace_dir.name
        log.info("Creating default manifest for workspace %r", name)
        manifest = WorkspaceManifest.default_manifest(name)
        # Pin the SciQLop this workspace was created against, so it keeps
        # resolving the same environment once the launcher moves on. Left empty
        # for development builds, whose version does not exist on any index.
        version = running_sciqlop_version()
        if version and ".dev" not in version:
            manifest.sciqlop_version = version
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

    # Step 4: Collect appstore-installed packages so they survive venv recreation
    appstore_deps = [pkg.pip for pkg in SciQLopPluginsSettings().installed_packages.values()]

    # Step 5: Generate pyproject.toml
    pyproject_path = workspace_dir / "pyproject.toml"
    generate_pyproject_toml(manifest, plugin_deps + appstore_deps, pyproject_path)

    # H4: an archive import ships its own uv.lock and wants it honored
    # (locked=True) on this first launch, without every caller having to
    # know that — the marker is how import_workspace() communicates it.
    import_marker = workspace_dir / IMPORT_MARKER_NAME
    effective_locked = locked or import_marker.exists()

    # Invalidate uv.lock when it predates pyproject.toml.  generate_pyproject_toml
    # is idempotent, so pyproject.toml's mtime only advances when its content
    # changes (manifest edits, plugin enable/disable, appstore install/remove,
    # or a SciQLop upgrade that ships a new generator).  A lockfile older than
    # the current pyproject would otherwise force uv sync to honor stale
    # resolutions and quietly fail to install newly added deps.
    lockfile = workspace_dir / "uv.lock"
    if (
        not effective_locked
        and lockfile.exists()
        and pyproject_path.exists()
        and lockfile.stat().st_mtime < pyproject_path.stat().st_mtime
    ):
        log.info("Removing stale uv.lock (older than pyproject.toml)")
        try:
            lockfile.unlink()
        except OSError as exc:
            # Windows: antivirus, OneDrive, or a leftover uv process can hold
            # the file open. Don't crash the launcher — uv sync will either
            # cope with the stale lock or surface its own error.
            log.warning("Could not remove stale uv.lock: %s", exc)

    # Step 6: Ensure venv exists and sync
    venv = WorkspaceVenv(workspace_dir)
    venv.ensure(on_output=on_output)
    synced = _sync_workspace_venv(
        venv, manifest, plugin_deps + appstore_deps, pyproject_path, effective_locked, on_output,
    )
    if synced and import_marker.exists():
        import_marker.unlink()

    # Venvs prepared by older SciQLop versions installed both jupyterlab and
    # jupyterlab-js; the sync above may have just uninstalled jupyterlab and
    # taken jupyterlab-js's shared data files with it. Heal before launch.
    repair_lab_assets(venv.venv_dir, on_output=on_output)

    return venv.python_path
