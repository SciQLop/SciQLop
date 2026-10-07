"""Reset a workspace's Python environment so the next sync rebuilds it from scratch.

The environment (``.venv`` and ``uv.lock``) is renamed aside first, then deleted.
Renaming is one cheap operation that rarely fails, whereas deleting thousands of
files on Windows often hits one held open by an antivirus, an indexer or a
leftover process. Once renamed, the workspace has no ``.venv``, so the next sync
builds a fresh one whatever happens to the old one. What can't be deleted now is
retried on every later start.
"""
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, List, Optional

from packaging.version import InvalidVersion, Version

from . import venv_slots
from .workspace_manifest import WorkspaceManifest
from .launcher_compat import preferred_release
from .workspace_project import is_dev_build_version, running_sciqlop_version

log = logging.getLogger(__name__)

ENVIRONMENT_FILES = (*venv_slots.SLOTS, "uv.lock")
RESET_MARK = ".reset-"

Output = Optional[Callable[[str], None]]


def is_reset_leftover(name: str) -> bool:
    """Whether *name* is an environment renamed aside by a reset."""
    return any(name.startswith(f + RESET_MARK) for f in ENVIRONMENT_FILES)


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _say(on_output: Output, message: str) -> None:
    log.info(message)
    if on_output is not None:
        on_output(message)


def _aside_path(path: Path, stamp: str) -> Path:
    base = f"{path.name}{RESET_MARK}{stamp}"
    candidate, n = path.with_name(base), 2
    while candidate.exists() or candidate.is_symlink():
        candidate, n = path.with_name(f"{base}-{n}"), n + 1
    return candidate


def _remove(path: Path) -> List[str]:
    """Delete *path*, carrying on past what can't be deleted; returns what was left."""
    failed: List[str] = []
    try:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path, onexc=lambda _func, p, _exc: failed.append(str(p)))
        else:
            path.unlink(missing_ok=True)
    except OSError as exc:
        failed.append(f"{path}: {exc}")
    return failed


def _rename(src: Path, dst: Path) -> None:
    os.replace(src, dst)


def _move_aside(path: Path, stamp: str, on_output: Output) -> None:
    if not (path.exists() or path.is_symlink()):
        return
    try:
        _rename(path, _aside_path(path, stamp))
    except OSError as exc:
        _say(on_output, f"Could not rename {path.name} ({exc}); deleting it in place")
        if failed := _remove(path):
            _say(on_output, f"{len(failed)} files of {path.name} could not be deleted")


def remove_reset_leftovers(workspace_dir: Path | str, on_output: Output = None) -> List[str]:
    """Delete environments earlier resets renamed aside; returns what is still there."""
    leftovers = [p for p in Path(workspace_dir).iterdir() if is_reset_leftover(p.name)]
    failed = [f for p in leftovers for f in _remove(p)]
    if failed:
        _say(on_output, f"{len(failed)} files of an old environment could not be deleted yet; "
                        "SciQLop will try again on the next start")
        log.debug("Undeleted reset leftovers: %s", failed)
    return failed


def _newer(candidate: str, pinned: str) -> bool:
    try:
        return Version(candidate) > Version(pinned)
    except InvalidVersion:
        return True


def _preferred_release() -> List[str]:
    """The release the "SciQLop version" setting asks for, if any.

    A reset runs in the launcher process, so its own version is the launcher's.
    """
    version = preferred_release(running_sciqlop_version())
    return [version] if version else []


def pin_latest_release(manifest_path: Path, latest_versions: Callable[[], Iterable[str]],
                       on_output: Output = None) -> None:
    """Pin the newest SciQLop release, unless the workspace follows main or we are offline."""
    if not manifest_path.exists():
        return
    manifest = WorkspaceManifest.load_or_repair(manifest_path)
    pinned = manifest.sciqlop_version
    if pinned and is_dev_build_version(pinned):
        return
    newest = next(iter(latest_versions()), None)
    if newest is None or (pinned and not _newer(newest, pinned)):
        return
    manifest.sciqlop_version = newest
    manifest.save(manifest_path)
    _say(on_output, f"Workspace moved to SciQLop {newest}" + (f" (was {pinned})" if pinned else ""))


def reset_environment(workspace_dir: Path | str, on_output: Output = None,
                      latest_versions: Optional[Callable[[], Iterable[str]]] = None) -> None:
    """Move the workspace's environment aside, delete it, and pin the newest SciQLop.

    Notebooks, settings and the manifest are kept; the next sync rebuilds the rest.
    """
    workspace_dir = Path(workspace_dir)
    _say(on_output, "Resetting the workspace's Python environment")
    stamp = _stamp()
    for name in ENVIRONMENT_FILES:
        _move_aside(workspace_dir / name, stamp, on_output)
    venv_slots.clear_pending(workspace_dir)
    venv_slots.set_active(workspace_dir, venv_slots.SLOTS[0])
    remove_reset_leftovers(workspace_dir, on_output)
    pin_latest_release(workspace_dir / "workspace.sciqlop", latest_versions or _preferred_release,
                       on_output)
