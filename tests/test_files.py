"""Tests for SciQLop.core.common.files."""

import shutil
from unittest.mock import patch

import pytest

from SciQLop.core.common import files
from SciQLop.core.common.files import remove_tree


def _tree(tmp_path):
    root = tmp_path / "tree"
    (root / "a" / "b").mkdir(parents=True)
    (root / "a" / "b" / "f.txt").write_text("x")
    return root


def _rmtree_flaky(failures: int):
    real = shutil.rmtree
    calls = {"n": 0}

    def fake(path, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] <= failures:
            raise OSError(41, "The directory is not empty", str(path), 145)
        real(path, *args, **kwargs)

    return fake, calls


class TestRemoveTree:
    def test_removes_tree(self, tmp_path):
        root = _tree(tmp_path)
        remove_tree(root)
        assert not root.exists()

    def test_retries_after_transient_windows_delete_pending(self, tmp_path):
        """CPython gh-84324: a scanner holding a just-unlinked file open makes
        the parent rmdir fail with ERROR_DIR_NOT_EMPTY until it lets go."""
        root = _tree(tmp_path)
        fake, calls = _rmtree_flaky(failures=2)
        with patch.object(shutil, "rmtree", fake), patch.object(files.time, "sleep") as sleep:
            remove_tree(root)
        assert not root.exists()
        assert calls["n"] == 3
        assert sleep.call_count == 2

    def test_raises_when_failure_persists(self, tmp_path):
        root = _tree(tmp_path)
        fake, calls = _rmtree_flaky(failures=100)
        with patch.object(shutil, "rmtree", fake), patch.object(files.time, "sleep"):
            with pytest.raises(OSError):
                remove_tree(root)
        assert calls["n"] == 6

    def test_returns_when_tree_vanished_underneath(self, tmp_path):
        root = _tree(tmp_path)
        real = shutil.rmtree

        def fake(path, *args, **kwargs):
            real(path)
            raise OSError(41, "The directory is not empty", str(path), 145)

        with patch.object(shutil, "rmtree", fake), patch.object(files.time, "sleep") as sleep:
            remove_tree(root)
        assert not root.exists()
        sleep.assert_not_called()
