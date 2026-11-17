"""Locks between the SciQLop windows of one person, which share the plugin's folders.

QLockFile holds an OS lock on its file (flock, or an exclusive handle on Windows): a window that
crashes frees it."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QLockFile


def lock_on(path: Path) -> QLockFile:
    """Not taken yet. `tryLock(0)` takes it or says at once that another window holds it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(path))
    # Qt first guesses from the holder's process id whether a lock is left over; past this age
    # it asks the OS lock itself, which a process id used again cannot fool.
    lock.setStaleLockTime(1)
    return lock
