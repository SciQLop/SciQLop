"""Per-workspace exclusive lock for serializing venv-mutating operations.

A stdlib-only advisory lock (an ``O_CREAT | O_EXCL`` marker file) — not a
general-purpose cross-process mutex for the whole workspace subsystem (see
docs/superpowers/specs/2026-09-04-workspace-core-version-update-design.md,
"Non-goals"). It only protects one workspace directory against two
concurrent calls to the same operation, e.g. a user double-clicking
"Install" on the SciQLop Core version picker.
"""

from __future__ import annotations

import contextlib
import os
import time
from pathlib import Path
from typing import Iterator

LOCK_FILENAME = ".sciqlop_core_update.lock"

# A real `uv sync` for a full workspace should never take this long; a lock
# file older than this is assumed to be left over from a crashed process
# rather than an operation that is still genuinely running.
_STALE_AFTER_SECONDS = 600


class WorkspaceLockError(RuntimeError):
    """Raised when a workspace's update lock is already held by another call."""


def _is_stale(lock_path: Path) -> bool:
    try:
        age = time.time() - lock_path.stat().st_mtime
    except OSError:
        return True
    return age > _STALE_AFTER_SECONDS


@contextlib.contextmanager
def workspace_lock(workspace_dir: Path | str) -> Iterator[None]:
    """Exclusive lock scoped to *workspace_dir*, held for the ``with`` block.

    Raises ``WorkspaceLockError`` immediately if another process already
    holds the lock — callers report this as "an update is already in
    progress" rather than waiting for it to clear.
    """
    lock_path = Path(workspace_dir) / LOCK_FILENAME
    if lock_path.exists() and _is_stale(lock_path):
        try:
            lock_path.unlink()
        except OSError:
            pass
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise WorkspaceLockError(
            f"An update is already in progress for {workspace_dir}"
        ) from None
    try:
        os.write(fd, str(os.getpid()).encode())
    finally:
        os.close(fd)
    try:
        yield
    finally:
        try:
            lock_path.unlink()
        except OSError:
            pass
