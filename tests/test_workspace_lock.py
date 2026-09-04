"""Tests for the per-workspace exclusive update lock.

Scoped only to serializing concurrent calls to one operation (apply_core_
version) against the same workspace directory — not a general-purpose
cross-process mutex for the whole workspace subsystem. See
docs/superpowers/specs/2026-09-04-workspace-core-version-update-design.md,
"Non-goals".
"""

import os
import time

import pytest

from SciQLop.components.workspaces.backend.workspace_lock import (
    LOCK_FILENAME,
    WorkspaceLockError,
    workspace_lock,
)


def test_lock_file_exists_during_the_with_block_and_is_removed_after(tmp_path):
    with workspace_lock(tmp_path):
        assert (tmp_path / LOCK_FILENAME).exists()
    assert not (tmp_path / LOCK_FILENAME).exists()


def test_second_concurrent_lock_on_the_same_directory_raises(tmp_path):
    with workspace_lock(tmp_path):
        with pytest.raises(WorkspaceLockError):
            with workspace_lock(tmp_path):
                pass


def test_lock_is_released_even_if_the_block_raises(tmp_path):
    with pytest.raises(RuntimeError, match="boom"):
        with workspace_lock(tmp_path):
            raise RuntimeError("boom")
    assert not (tmp_path / LOCK_FILENAME).exists()


def test_a_stale_lock_is_reclaimed_instead_of_blocking_forever(tmp_path):
    lock_path = tmp_path / LOCK_FILENAME
    lock_path.write_text("99999999")
    old_mtime = time.time() - 3600
    os.utime(lock_path, (old_mtime, old_mtime))

    with workspace_lock(tmp_path):
        assert lock_path.exists()


def test_locks_on_different_directories_do_not_interfere(tmp_path):
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()
    with workspace_lock(dir_a):
        with workspace_lock(dir_b):
            pass  # must not raise
