"""High-level workspace preparation orchestrator.

Called by the launcher before spawning the Qt application.  Given a workspace
directory it ensures the manifest, pyproject.toml, and virtual environment are
all in place, then returns the path to the venv's Python executable.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path

from SciQLop.components.plugins.backend.folders import plugins_folders
from SciQLop.components.plugins.backend.settings import SciQLopPluginsSettings
from SciQLop.components.plugins.plugin_deps import collect_plugin_dependencies
from SciQLop.components.workspaces.backend.workspace_archive import IMPORT_MARKER_NAME
from SciQLop.components.workspaces.backend.workspace_lock import workspace_lock
from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest
from SciQLop.components.workspaces.backend.workspace_migration import migrate_workspace
from SciQLop.components.workspaces.backend.lab_assets import repair_lab_assets
from SciQLop.components.workspaces.backend.workspace_project import (
    _extract_package_name,
    _normalize_url_requirement,
    generate_pyproject_toml,
    is_dev_build_version,
    running_sciqlop_version,
)
from SciQLop.components.workspaces.backend.workspace_venv import WorkspaceVenv
from SciQLop.core.common.files import write_text_atomic

log = logging.getLogger(__name__)

MANIFEST_FILENAME = "workspace.sciqlop"
DROPPED_DEPS_FILENAME = ".sciqlop_dropped_deps.json"
_DROPPED_DEPS_ERROR_MAX_LINES = 20


def get_globally_enabled_plugins() -> list[str]:
    """Return names of globally enabled plugins from settings."""
    settings = SciQLopPluginsSettings()
    return [name for name, cfg in settings.plugins.items() if cfg.enabled]


def get_plugin_folders() -> list[str]:
    """Return all plugin search folders."""
    return plugins_folders()


def _fold_dep_name(name: str) -> str:
    return name.replace("_", "-").lower()


def culprit_dependencies(optional_deps: list[str], error_text: str) -> list[str]:
    """Return the *optional_deps* entries uv's resolver error text names.

    simplify: this is text matching on uv's resolver message, not a query of
    our own -- it can miss a differently-phrased error or over-match a
    coincidental substring. Upgrade path: probe each optional dep with its
    own ``uv lock`` call and see which one alone fails to resolve.
    """
    folded_error = _fold_dep_name(error_text)
    return [
        dep for dep in optional_deps
        if _fold_dep_name(_extract_package_name(_normalize_url_requirement(dep))) in folded_error
    ]


def _dropped_deps_path(workspace_dir: Path | str) -> Path:
    return Path(workspace_dir) / DROPPED_DEPS_FILENAME


def read_dropped_dependencies(workspace_dir: Path | str) -> dict | None:
    """The persisted drop-notice for *workspace_dir*, or None.

    None covers both "no retry ever dropped anything" (no file) and a
    corrupt/unreadable file -- both cases the caller should treat as
    "nothing to report".
    """
    try:
        return json.loads(_dropped_deps_path(workspace_dir).read_text())
    except (OSError, ValueError):
        return None


def _write_dropped_dependencies(workspace_dir: Path, dropped: list[str], error_text: str) -> None:
    payload = {
        "dropped": dropped,
        "error": "\n".join(str(error_text).splitlines()[:_DROPPED_DEPS_ERROR_MAX_LINES]),
    }
    write_text_atomic(_dropped_deps_path(workspace_dir), json.dumps(payload))


def _clear_dropped_dependencies(workspace_dir: Path) -> None:
    path = _dropped_deps_path(workspace_dir)
    if not path.exists():
        return
    try:
        path.unlink()
    except OSError as exc:
        log.warning("Could not remove dropped-deps notice: %s", exc)


def _try_sync(
    venv: WorkspaceVenv, *, locked: bool, upgrade_package: str | None = None, on_output
) -> Exception | None:
    # A locked sync (archive import) means to reproduce the shipped lock
    # exactly, so it never requests an upgrade -- see WorkspaceVenv.sync.
    kwargs = {"upgrade_package": upgrade_package} if upgrade_package and not locked else {}
    try:
        venv.sync(locked=locked, on_output=on_output, **kwargs)
        return None
    except Exception as exc:
        return exc


def _report_sync_failure(exc: Exception, on_output, *, core_only: bool = False) -> None:
    label = "Core-only sync" if core_only else "Workspace dependency sync"
    log.warning("%s failed: %s", label, exc)
    if on_output is not None:
        on_output(f"{label} failed: {exc}")


def _retry_without_culprits(
    venv: WorkspaceVenv,
    manifest: WorkspaceManifest,
    optional_deps: list[str],
    pyproject_path: Path,
    on_output: Callable[[str], None] | None,
    upgrade_package: str | None,
    error: Exception,
) -> list[str] | None:
    """Retry the sync with just the deps ``culprit_dependencies`` names dropped.

    Returns the dropped deps on success, or ``None`` when no single-cause
    culprit could be pinned down, every optional dep was implicated (no
    point in a retry identical to the core-only one), or dropping just the
    culprits still didn't fix the sync -- the caller then falls back to
    dropping every optional dep instead.
    """
    culprits = culprit_dependencies(optional_deps, str(error))
    if not culprits or len(culprits) >= len(optional_deps):
        return None
    remaining = [dep for dep in optional_deps if dep not in culprits]
    if on_output is not None:
        on_output(f"Retrying without {', '.join(culprits)} (suspected incompatible)...")
    generate_pyproject_toml(manifest, remaining, pyproject_path)
    exc = _try_sync(venv, locked=False, upgrade_package=upgrade_package, on_output=on_output)
    if exc is not None:
        _report_sync_failure(exc, on_output, core_only=False)
        return None
    return culprits


def _sync_workspace_venv(
    venv: WorkspaceVenv,
    manifest: WorkspaceManifest,
    optional_deps: list[str],
    pyproject_path: Path,
    locked: bool,
    on_output: Callable[[str], None] | None,
    strict: bool = False,
    upgrade_package: str | None = None,
) -> bool:
    """Sync the workspace venv, isolating a broken plugin/appstore dependency.

    The plugin loader already tolerates one plugin failing to import — it
    logs and skips just that plugin (see loader.load_plugin) — so a single
    incompatible plugin or appstore package (e.g. a published release still
    pinned to an old SciQLop range) must not keep SciQLop itself from
    starting. If the full dependency set fails to resolve, this first tries
    to isolate the culprit (``culprit_dependencies``) and retry with just
    that dep dropped, so the rest of the plugins/appstore packages survive;
    only if no culprit can be pinned down, or dropping it still doesn't fix
    the sync, does it fall back to dropping every optional dep so the core
    app can still launch. Only if even that fails do we fall back to (or
    give up on) whatever is already in the venv. Whenever a retry actually
    drops something, that is recorded to ``DROPPED_DEPS_FILENAME`` (cleared
    again on a sync that needs no retry) for the app to warn about at
    startup.

    ``locked`` (importing a workspace archive) tries to reproduce the exact,
    previously-working environment first. But an archive can outlive the
    SciQLop version that made it (e.g. its pinned ``sciqlop[all]==X`` no
    longer exists), in which case honoring the lock is impossible — a fresh
    venv must never be left empty because of a stale archive lock, so a
    failed locked sync falls back to a normal unlocked one (with its own
    plugin-isolation retry) instead of giving up.

    ``strict``, when ``True``, disables the final "keep whatever is already
    installed" fallback below and raises instead. That fallback exists for
    ordinary launcher startup (issue #115: don't block the app over a
    transient offline error); a user-initiated version change must fail
    loudly instead of silently keeping the old version and reporting
    success (see workspace_setup.apply_core_version).

    Returns ``True`` when a sync actually installed the requested
    dependencies, ``False`` when every attempt failed and this instead fell
    through to keeping whatever was already in the venv (offline /
    unreachable index, #115). Callers rely on this to tell "the environment
    now matches what was asked for" from "we're just limping along on the
    old one".
    """
    workspace_dir = pyproject_path.parent
    exc = _try_sync(venv, locked=locked, upgrade_package=upgrade_package, on_output=on_output)
    if exc is None:
        _clear_dropped_dependencies(workspace_dir)
        return True
    _report_sync_failure(exc, on_output)

    if locked:
        if on_output is not None:
            on_output("Archive lockfile could not be honored, resolving fresh")
        return _sync_workspace_venv(
            venv, manifest, optional_deps, pyproject_path, False, on_output, strict,
            upgrade_package,
        )

    if optional_deps:
        first_failure = exc
        dropped = _retry_without_culprits(
            venv, manifest, optional_deps, pyproject_path, on_output, upgrade_package, exc,
        )
        if dropped is None:
            if on_output is not None:
                on_output(
                    "Retrying with just the core app (dropping plugin/appstore "
                    "dependencies)..."
                )
            generate_pyproject_toml(manifest, [], pyproject_path)
            exc = _try_sync(venv, locked=False, upgrade_package=upgrade_package, on_output=on_output)
            if exc is None:
                dropped = optional_deps
            else:
                _report_sync_failure(exc, on_output, core_only=True)
        if dropped is not None:
            # M1: put the full dependency set back on disk (not synced) so
            # the next launch and the appstore see the intended set again,
            # instead of the reduced one the retry just wrote.
            generate_pyproject_toml(manifest, optional_deps, pyproject_path)
            _write_dropped_dependencies(workspace_dir, dropped, str(first_failure))
            return True

    if strict or not venv.has_sciqlop_installed:
        # No working install to fall back to (or the caller demanded strict
        # failure regardless).
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
    manifest: WorkspaceManifest | None = None,
    strict: bool = False,
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
    manifest:
        A pre-loaded manifest to use instead of loading/creating one from
        disk. When given, *workspace_dir*'s on-disk manifest (if any) is
        never read — the caller owns loading and (if desired) saving it.
        Used by ``apply_core_version`` to stage an in-memory version change
        and only persist it after a successful sync.
    strict:
        If ``True``, a sync failure always raises instead of falling back
        to whatever is already installed in the venv. The default
        (permissive) behavior exists so ordinary launcher startup can still
        start offline with a stale-but-working venv; that permissiveness is
        wrong for an explicit, user-requested version change, which must
        fail loudly rather than silently keep the old version.

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

    # Step 1: Use the given manifest, or load/create one
    if manifest is not None:
        pass
    elif manifest_path.exists():
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
    # A dev-build workspace's SciQLop dependency is `git+...@main` -- text
    # that never changes between pushes, so plain `uv sync` would otherwise
    # keep honoring whatever commit uv.lock first resolved, forever (see
    # pitfall-uv-lock-freezes-git-main-forever). Force a fresh resolve of
    # just that one package on every launch instead.
    resolved_version = manifest.sciqlop_version or running_sciqlop_version()
    upgrade_package = "sciqlop" if is_dev_build_version(resolved_version) else None
    synced = _sync_workspace_venv(
        venv, manifest, plugin_deps + appstore_deps, pyproject_path, effective_locked, on_output,
        strict=strict, upgrade_package=upgrade_package,
    )
    if synced and import_marker.exists():
        try:
            import_marker.unlink()
        except OSError as exc:
            log.warning("Could not remove import marker: %s", exc)

    # Venvs prepared by older SciQLop versions installed both jupyterlab and
    # jupyterlab-js; the sync above may have just uninstalled jupyterlab and
    # taken jupyterlab-js's shared data files with it. Heal before launch.
    repair_lab_assets(venv.venv_dir, on_output=on_output)

    return venv.python_path


def apply_core_version(workspace_dir: Path | str, version: str) -> Path:
    """Change the SciQLop version pinned for *workspace_dir* and sync its venv.

    *version* must already be validated by the caller (see
    ``workspace_project.validate_core_version``) — this trusts it and writes
    it straight into the manifest's ``sciqlop_version``.

    Reuses ``prepare_workspace`` in strict mode so the full dependency set
    (plugins + appstore packages, not just SciQLop itself) is preserved, and
    only saves the manifest change after the sync actually succeeds — a
    failed update never leaves the manifest pointing at a version that
    isn't installed. Serializes against other calls for the same
    *workspace_dir* via ``workspace_lock``.

    Raises ``FileNotFoundError`` if *workspace_dir* has no existing
    manifest, ``WorkspaceLockError`` if another update is already in
    progress for it, or whatever ``prepare_workspace`` raises on sync
    failure. A failure saving the manifest *after* a successful sync (disk
    full, permissions) is re-raised as a distinctly worded ``RuntimeError``,
    since at that point the venv genuinely was updated and the failure is
    not the ordinary "nothing changed" case.
    """
    workspace_dir = Path(workspace_dir)
    manifest_path = workspace_dir / MANIFEST_FILENAME
    if not manifest_path.exists():
        raise FileNotFoundError(f"No workspace manifest at {manifest_path}")

    with workspace_lock(workspace_dir):
        manifest = WorkspaceManifest.load_or_repair(manifest_path)
        manifest.sciqlop_version = version
        output_lines: list[str] = []
        python_path = prepare_workspace(
            workspace_dir, manifest=manifest, strict=True, on_output=output_lines.append,
        )
        try:
            manifest.save(manifest_path)
        except Exception as exc:
            raise RuntimeError(
                f"SciQLop {version or 'main'} was installed, but recording it "
                f"in the workspace manifest failed: {exc}"
            ) from exc
    return python_path


def pin_core_version(workspace_dir: Path | str, version: str) -> None:
    """Update *workspace_dir*'s pinned SciQLop version without syncing now.

    For the workspace the running process itself launched from: syncing its
    venv while the interpreter is using it would rewrite the running
    process's own site-packages underneath it. This only updates the
    manifest -- the actual venv sync happens naturally the next time this
    workspace launches, through the ordinary (non-strict) prepare_workspace()
    call every startup already makes.

    Raises ``FileNotFoundError`` if *workspace_dir* has no existing
    manifest, ``WorkspaceLockError`` if another update is already in
    progress for it.
    """
    workspace_dir = Path(workspace_dir)
    manifest_path = workspace_dir / MANIFEST_FILENAME
    if not manifest_path.exists():
        raise FileNotFoundError(f"No workspace manifest at {manifest_path}")

    with workspace_lock(workspace_dir):
        manifest = WorkspaceManifest.load_or_repair(manifest_path)
        manifest.sciqlop_version = version
        manifest.save(manifest_path)
