"""Tests for workspace archive export and import."""

import zipfile
from pathlib import Path

import pytest

from SciQLop.components.workspaces.backend.workspace_archive import (
    EXCLUDE_PATTERNS,
    export_workspace,
    import_workspace,
)


@pytest.fixture
def workspace_dir(tmp_path: Path) -> Path:
    """Create a minimal workspace directory with typical files."""
    ws = tmp_path / "my_workspace"
    ws.mkdir()

    # Manifest
    (ws / "workspace.sciqlop").write_text('{"name": "demo"}')

    # Lockfile
    (ws / "uv.lock").write_text("# lock content")

    # Notebook
    notebooks = ws / "notebooks"
    notebooks.mkdir()
    (notebooks / "analysis.ipynb").write_text('{"cells": []}')

    # Script
    scripts = ws / "scripts"
    scripts.mkdir()
    (scripts / "helper.py").write_text("print('hello')")

    # Files that should be excluded
    venv = ws / ".venv"
    venv.mkdir()
    (venv / "pyvenv.cfg").write_text("home = /usr/bin")

    (ws / "pyproject.toml").write_text("[project]")

    pycache = ws / "__pycache__"
    pycache.mkdir()
    (pycache / "mod.cpython-312.pyc").write_bytes(b"\x00")

    # Nested __pycache__
    nested_cache = scripts / "__pycache__"
    nested_cache.mkdir()
    (nested_cache / "helper.cpython-312.pyc").write_bytes(b"\x00")

    return ws


@pytest.fixture
def archive_path(tmp_path: Path) -> Path:
    return tmp_path / "output.sciqlop-archive"


class TestExportWorkspace:
    def test_creates_valid_zip(self, workspace_dir: Path, archive_path: Path):
        export_workspace(workspace_dir, archive_path)
        assert archive_path.exists()
        assert zipfile.is_zipfile(archive_path)

    def test_includes_manifest(self, workspace_dir: Path, archive_path: Path):
        export_workspace(workspace_dir, archive_path)
        with zipfile.ZipFile(archive_path) as zf:
            names = zf.namelist()
            assert "workspace.sciqlop" in names

    def test_includes_lockfile(self, workspace_dir: Path, archive_path: Path):
        export_workspace(workspace_dir, archive_path)
        with zipfile.ZipFile(archive_path) as zf:
            assert "uv.lock" in zf.namelist()

    def test_includes_notebooks(self, workspace_dir: Path, archive_path: Path):
        export_workspace(workspace_dir, archive_path)
        with zipfile.ZipFile(archive_path) as zf:
            assert "notebooks/analysis.ipynb" in zf.namelist()

    def test_includes_scripts(self, workspace_dir: Path, archive_path: Path):
        export_workspace(workspace_dir, archive_path)
        with zipfile.ZipFile(archive_path) as zf:
            assert "scripts/helper.py" in zf.namelist()

    def test_excludes_venv(self, workspace_dir: Path, archive_path: Path):
        export_workspace(workspace_dir, archive_path)
        with zipfile.ZipFile(archive_path) as zf:
            for name in zf.namelist():
                assert not name.startswith(".venv")

    def test_excludes_pyproject_toml(self, workspace_dir: Path, archive_path: Path):
        export_workspace(workspace_dir, archive_path)
        with zipfile.ZipFile(archive_path) as zf:
            assert "pyproject.toml" not in zf.namelist()

    def test_excludes_pycache(self, workspace_dir: Path, archive_path: Path):
        export_workspace(workspace_dir, archive_path)
        with zipfile.ZipFile(archive_path) as zf:
            for name in zf.namelist():
                assert "__pycache__" not in name


class TestImportWorkspace:
    def test_extracts_to_target(self, workspace_dir: Path, archive_path: Path, tmp_path: Path):
        export_workspace(workspace_dir, archive_path)
        target = tmp_path / "imported"
        result = import_workspace(archive_path, target)
        assert result == target
        assert (target / "workspace.sciqlop").exists()

    def test_creates_target_dir(self, workspace_dir: Path, archive_path: Path, tmp_path: Path):
        export_workspace(workspace_dir, archive_path)
        target = tmp_path / "nested" / "deep" / "imported"
        import_workspace(archive_path, target)
        assert target.is_dir()
        assert (target / "workspace.sciqlop").exists()

    def test_roundtrip_preserves_files(self, workspace_dir: Path, archive_path: Path, tmp_path: Path):
        export_workspace(workspace_dir, archive_path)
        target = tmp_path / "roundtrip"
        import_workspace(archive_path, target)

        assert (target / "workspace.sciqlop").read_text() == '{"name": "demo"}'
        assert (target / "uv.lock").read_text() == "# lock content"
        assert (target / "notebooks" / "analysis.ipynb").read_text() == '{"cells": []}'
        assert (target / "scripts" / "helper.py").read_text() == "print('hello')"

    def test_roundtrip_excludes_transient(self, workspace_dir: Path, archive_path: Path, tmp_path: Path):
        export_workspace(workspace_dir, archive_path)
        target = tmp_path / "roundtrip2"
        import_workspace(archive_path, target)

        assert not (target / ".venv").exists()
        assert not (target / "pyproject.toml").exists()
        assert not (target / "__pycache__").exists()
        assert not (target / "scripts" / "__pycache__").exists()


class TestExcludePatterns:
    def test_exclude_patterns_contains_expected(self):
        assert ".venv" in EXCLUDE_PATTERNS
        assert "pyproject.toml" in EXCLUDE_PATTERNS
        assert "__pycache__" in EXCLUDE_PATTERNS
