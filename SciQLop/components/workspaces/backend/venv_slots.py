"""A/B workspace environments, like an immutable OS or an Android update.

A workspace has two venv slots. SciQLop runs from the live one; an update is
built into the other while SciQLop keeps running, then made live on the next
start, before anything has loaded from it. uv hard-links (or, on macOS, clones)
packages from its cache, so the second slot costs little disk or time.

Slot A is the historical ``.venv``, so existing workspaces need no migration.
"""
from pathlib import Path
from typing import Optional

from SciQLop.core.common.files import write_text_atomic

SLOTS = (".venv", ".venv-b")
POINTER = ".sciqlop_venv"            # names the live slot; missing means slot A
PENDING = ".sciqlop_venv_next"       # names a slot staged to go live on next start


def _read_slot(path: Path) -> Optional[str]:
    try:
        name = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return name if name in SLOTS else None


def _write_slot(path: Path, slot: str) -> None:
    if slot not in SLOTS:
        raise ValueError(f"unknown venv slot {slot!r}, expected one of {SLOTS}")
    write_text_atomic(path, slot + "\n")


def active_slot(workspace_dir: Path | str) -> str:
    return _read_slot(Path(workspace_dir) / POINTER) or SLOTS[0]


def inactive_slot(workspace_dir: Path | str) -> str:
    active = active_slot(workspace_dir)
    return next(s for s in SLOTS if s != active)


def active_venv_dir(workspace_dir: Path | str) -> Path:
    return Path(workspace_dir) / active_slot(workspace_dir)


def set_active(workspace_dir: Path | str, slot: str) -> None:
    _write_slot(Path(workspace_dir) / POINTER, slot)


def pending_slot(workspace_dir: Path | str) -> Optional[str]:
    return _read_slot(Path(workspace_dir) / PENDING)


def mark_pending(workspace_dir: Path | str, slot: str) -> None:
    _write_slot(Path(workspace_dir) / PENDING, slot)


def clear_pending(workspace_dir: Path | str) -> None:
    (Path(workspace_dir) / PENDING).unlink(missing_ok=True)


def activate_pending(workspace_dir: Path | str) -> Optional[str]:
    """Make the staged slot live; returns it, or None when nothing was staged.

    Only safe while nothing runs from the workspace's venv, i.e. at startup
    before SciQLop is launched from it.
    """
    staged = pending_slot(workspace_dir)
    clear_pending(workspace_dir)
    if staged is None or staged == active_slot(workspace_dir):
        return None
    set_active(workspace_dir, staged)
    return staged
