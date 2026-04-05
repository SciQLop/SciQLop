# uv-based Environment Management Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace pip-based runtime dependency installation with uv-managed workspace virtual environments that inherit from the base SciQLop install via `--system-site-packages`.

**Architecture:** The `sciqlop` launcher becomes a supervisor that resolves/creates workspace venvs before spawning the Qt app. Each workspace has a `.sciqlop` TOML manifest (source of truth) from which a `pyproject.toml` is generated. The launcher runs `uv sync` then execs the Qt app under the workspace venv's Python. Workspace switching uses exit codes.

**Tech Stack:** uv (bundled binary or pip-installed), TOML (tomllib stdlib + tomli_w for writing), PySide6 (Qt subprocess management)

**Design doc:** `docs/plans/2026-03-05-uv-environment-management-design.md`

---

### Task 1: uv binary resolution utility

**Files:**
- Create: `SciQLop/core/common/uv.py`
- Test: `tests/test_uv_resolution.py`
- Read: `SciQLop/core/common/python.py` (reference for AppImage path handling pattern)

**Step 1: Write the failing test**

```python
# tests/test_uv_resolution.py
import os
import shutil
from unittest.mock import patch
from SciQLop.core.common.uv import get_uv


def test_get_uv_from_path():
    """When uv is on PATH, get_uv returns its path."""
    uv_path = shutil.which("uv")
    if uv_path is None:
        pytest.skip("uv not on PATH")
    result = get_uv()
    assert result is not None
    assert os.path.isfile(result)


def test_get_uv_appimage():
    """When APPDIR is set, get_uv returns the bundled uv binary."""
    with patch.dict(os.environ, {"APPDIR": "/fake/appdir"}):
        with patch("os.path.isfile", return_value=True):
            result = get_uv()
            assert result == "/fake/appdir/opt/uv/uv"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_uv_resolution.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'SciQLop.core.common.uv'`

**Step 3: Write minimal implementation**

```python
# SciQLop/core/common/uv.py
import os
import shutil
from typing import Optional


def get_uv() -> Optional[str]:
    """Resolve the uv binary path. Checks APPDIR for bundled installs first."""
    appdir = os.environ.get("APPDIR")
    if appdir:
        bundled = os.path.join(appdir, "opt", "uv", "uv")
        if os.path.isfile(bundled):
            return bundled
    return shutil.which("uv")


def uv_command(*args: str) -> list[str]:
    """Build a uv command list. Raises RuntimeError if uv is not found."""
    uv = get_uv()
    if uv is None:
        raise RuntimeError("uv binary not found. Install uv or ensure it is on PATH.")
    return [uv, *args]
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_uv_resolution.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add SciQLop/core/common/uv.py tests/test_uv_resolution.py
git commit -m "feat: add uv binary resolution utility"
```

---

### Task 2: `.sciqlop` manifest reader/writer

**Files:**
- Create: `SciQLop/core/workspace_manifest.py`
- Test: `tests/test_workspace_manifest.py`

**Step 1: Write the failing test**

```python
# tests/test_workspace_manifest.py
import os
import tempfile
from SciQLop.core.workspace_manifest import WorkspaceManifest


def test_create_default_manifest():
    m = WorkspaceManifest.default("My Study")
    assert m.name == "My Study"
    assert m.description == ""
    assert m.plugins_add == []
    assert m.plugins_remove == []
    assert m.requires == []


def test_roundtrip(tmp_path):
    path = tmp_path / "workspace.sciqlop"
    m = WorkspaceManifest(
        name="Test",
        description="A test workspace",
        plugins_add=["extra_plugin"],
        plugins_remove=["experimental_collaboration"],
        requires=["matplotlib>=3.8", "scipy"],
    )
    m.save(path)
    loaded = WorkspaceManifest.load(path)
    assert loaded.name == "Test"
    assert loaded.description == "A test workspace"
    assert loaded.plugins_add == ["extra_plugin"]
    assert loaded.plugins_remove == ["experimental_collaboration"]
    assert loaded.requires == ["matplotlib>=3.8", "scipy"]


def test_load_minimal(tmp_path):
    """A manifest with only [workspace] name should load with defaults."""
    path = tmp_path / "workspace.sciqlop"
    path.write_text('[workspace]\nname = "Minimal"\n')
    m = WorkspaceManifest.load(path)
    assert m.name == "Minimal"
    assert m.requires == []
    assert m.plugins_add == []
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_workspace_manifest.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# SciQLop/core/workspace_manifest.py
"""Reader/writer for .sciqlop workspace manifest files (TOML format)."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

try:
    import tomli_w
except ImportError:
    tomli_w = None  # type: ignore[assignment]


@dataclass
class WorkspaceManifest:
    name: str
    description: str = ""
    plugins_add: list[str] = field(default_factory=list)
    plugins_remove: list[str] = field(default_factory=list)
    requires: list[str] = field(default_factory=list)

    @classmethod
    def default(cls, name: str) -> WorkspaceManifest:
        return cls(name=name)

    @classmethod
    def load(cls, path: Path | str) -> WorkspaceManifest:
        path = Path(path)
        with open(path, "rb") as f:
            data = tomllib.load(f)
        ws = data.get("workspace", {})
        plugins = data.get("plugins", {})
        deps = data.get("dependencies", {})
        return cls(
            name=ws.get("name", ""),
            description=ws.get("description", ""),
            plugins_add=plugins.get("add", []),
            plugins_remove=plugins.get("remove", []),
            requires=deps.get("requires", []),
        )

    def save(self, path: Path | str) -> None:
        if tomli_w is None:
            raise RuntimeError("tomli_w is required to write manifests. Install it with: pip install tomli-w")
        path = Path(path)
        data = {
            "workspace": {
                "name": self.name,
                "description": self.description,
            },
            "plugins": {
                "add": self.plugins_add,
                "remove": self.plugins_remove,
            },
            "dependencies": {
                "requires": self.requires,
            },
        }
        with open(path, "wb") as f:
            tomli_w.dump(data, f)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_workspace_manifest.py -v`
Expected: PASS (may need `uv pip install tomli-w` first; add `tomli_w` to `[project.optional-dependencies]` or main deps in pyproject.toml)

**Step 5: Commit**

```bash
git add SciQLop/core/workspace_manifest.py tests/test_workspace_manifest.py
git commit -m "feat: add .sciqlop workspace manifest reader/writer"
```

---

### Task 3: pyproject.toml generator from manifest + plugin metadata

**Files:**
- Create: `SciQLop/core/workspace_project.py`
- Test: `tests/test_workspace_project.py`
- Read: `SciQLop/components/plugins/backend/loader/plugin_desc.py` (for `PluginDesc` model)
- Read: `SciQLop/components/plugins/backend/loader/loader.py` (for `plugins_folders()`)

This module generates the `pyproject.toml` that uv will use to sync the workspace venv. It merges plugin `python_dependencies` with workspace `requires`.

**Step 1: Write the failing test**

```python
# tests/test_workspace_project.py
from SciQLop.core.workspace_project import generate_pyproject_toml
from SciQLop.core.workspace_manifest import WorkspaceManifest


def test_generate_pyproject_basic(tmp_path):
    manifest = WorkspaceManifest(
        name="Test Study",
        description="",
        requires=["matplotlib>=3.8", "scipy"],
    )
    plugin_deps = ["speasy>=1.6.1", "tscat>=0.4.0"]
    output = tmp_path / "pyproject.toml"

    generate_pyproject_toml(manifest, plugin_deps, output)

    content = output.read_text()
    assert "matplotlib>=3.8" in content
    assert "scipy" in content
    assert "speasy>=1.6.1" in content
    assert "tscat>=0.4.0" in content
    assert "sciqlop-workspace-test-study" in content


def test_generate_pyproject_no_deps(tmp_path):
    manifest = WorkspaceManifest(name="Empty")
    output = tmp_path / "pyproject.toml"

    generate_pyproject_toml(manifest, [], output)

    content = output.read_text()
    assert "dependencies = []" in content or "dependencies" in content


def test_generate_pyproject_deduplicates(tmp_path):
    manifest = WorkspaceManifest(
        name="Dedup",
        requires=["speasy>=1.6.1"],  # same as plugin dep
    )
    plugin_deps = ["speasy>=1.6.1"]
    output = tmp_path / "pyproject.toml"

    generate_pyproject_toml(manifest, plugin_deps, output)

    content = output.read_text()
    # Should not have duplicate entries
    assert content.count("speasy") == 1
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_workspace_project.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# SciQLop/core/workspace_project.py
"""Generate a pyproject.toml for a workspace venv from manifest + plugin deps."""

from __future__ import annotations

import re
from pathlib import Path

from SciQLop.core.workspace_manifest import WorkspaceManifest


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _deduplicate_requirements(reqs: list[str]) -> list[str]:
    """Deduplicate requirements by package name (keeps last occurrence)."""
    seen: dict[str, str] = {}
    for req in reqs:
        pkg_name = re.split(r"[><=!~\[]", req)[0].strip().lower()
        seen[pkg_name] = req
    return list(seen.values())


def generate_pyproject_toml(
    manifest: WorkspaceManifest,
    plugin_deps: list[str],
    output_path: Path | str,
) -> None:
    output_path = Path(output_path)
    slug = _slugify(manifest.name) or "sciqlop-workspace"
    project_name = f"sciqlop-workspace-{slug}"

    all_deps = _deduplicate_requirements(plugin_deps + manifest.requires)

    deps_lines = ",\n".join(f'    "{dep}"' for dep in all_deps)
    if deps_lines:
        deps_section = f"[\n{deps_lines},\n]"
    else:
        deps_section = "[]"

    content = f"""\
# Auto-generated by SciQLop launcher. Do not edit manually.
# Source of truth: workspace.sciqlop manifest

[project]
name = "{project_name}"
version = "0.0.0"
requires-python = ">=3.10"
dependencies = {deps_section}
"""
    output_path.write_text(content)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_workspace_project.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add SciQLop/core/workspace_project.py tests/test_workspace_project.py
git commit -m "feat: add pyproject.toml generator for workspace venvs"
```

---

### Task 4: Workspace venv manager (create + sync via uv)

**Files:**
- Create: `SciQLop/core/workspace_venv.py`
- Test: `tests/test_workspace_venv.py`
- Read: `SciQLop/core/common/uv.py` (from Task 1)

This module handles creating workspace venvs with `--system-site-packages` and syncing them via `uv sync`.

**Step 1: Write the failing test**

```python
# tests/test_workspace_venv.py
import os
import subprocess
from unittest.mock import patch, MagicMock
from SciQLop.core.workspace_venv import WorkspaceVenv


def test_venv_python_path(tmp_path):
    """WorkspaceVenv exposes the venv python path."""
    venv = WorkspaceVenv(tmp_path)
    python_path = venv.python_path
    assert "python" in str(python_path)
    assert str(tmp_path / ".venv") in str(python_path)


def test_create_venv(tmp_path):
    """Creating a venv calls uv with --system-site-packages."""
    venv = WorkspaceVenv(tmp_path)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        venv.create()
        args = mock_run.call_args[0][0]
        assert "venv" in args
        assert "--system-site-packages" in args


def test_sync_venv(tmp_path):
    """Syncing calls uv sync in the workspace directory."""
    venv = WorkspaceVenv(tmp_path)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        venv.sync()
        args = mock_run.call_args[0][0]
        assert "sync" in args
        assert mock_run.call_args[1].get("cwd") == str(tmp_path)


def test_sync_locked(tmp_path):
    """Syncing with locked=True passes --locked flag."""
    venv = WorkspaceVenv(tmp_path)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        venv.sync(locked=True)
        args = mock_run.call_args[0][0]
        assert "--locked" in args
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_workspace_venv.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# SciQLop/core/workspace_venv.py
"""Manage workspace virtual environments using uv."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from SciQLop.core.common.uv import uv_command


class WorkspaceVenv:
    def __init__(self, workspace_dir: Path | str):
        self._workspace_dir = Path(workspace_dir)
        self._venv_dir = self._workspace_dir / ".venv"

    @property
    def python_path(self) -> Path:
        return self._venv_dir / "bin" / "python"

    @property
    def exists(self) -> bool:
        return self._venv_dir.exists() and self.python_path.exists()

    def create(self) -> None:
        """Create the workspace venv with --system-site-packages."""
        cmd = uv_command(
            "venv",
            str(self._venv_dir),
            "--system-site-packages",
            "--python", sys.executable,
        )
        subprocess.run(cmd, check=True)

    def sync(self, locked: bool = False) -> None:
        """Run uv sync in the workspace directory."""
        cmd = uv_command("sync")
        if locked:
            cmd.append("--locked")
        subprocess.run(cmd, check=True, cwd=str(self._workspace_dir))

    def ensure(self) -> None:
        """Create the venv if it doesn't exist."""
        if not self.exists:
            self.create()
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_workspace_venv.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add SciQLop/core/workspace_venv.py tests/test_workspace_venv.py
git commit -m "feat: add workspace venv manager using uv"
```

---

### Task 5: Plugin dependency collector

**Files:**
- Create: `SciQLop/core/plugin_deps.py`
- Test: `tests/test_plugin_deps.py`
- Read: `SciQLop/components/plugins/backend/loader/plugin_desc.py:12-26`
- Read: `SciQLop/components/plugins/backend/loader/loader.py:15-19` (`plugins_folders()`)
- Read: `SciQLop/components/plugins/backend/settings.py:14-18`

Collects `python_dependencies` from enabled plugins, applying workspace overrides.

**Step 1: Write the failing test**

```python
# tests/test_plugin_deps.py
from SciQLop.core.plugin_deps import collect_plugin_dependencies


def test_collect_from_plugin_dirs(tmp_path):
    """Reads plugin.json files and collects python_dependencies."""
    plugin_dir = tmp_path / "my_plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text(
        '{"name": "my_plugin", "version": "1.0", "python_dependencies": ["requests>=2.0"]}'
    )
    deps = collect_plugin_dependencies(
        plugin_folders=[tmp_path],
        enabled_plugins=["my_plugin"],
    )
    assert "requests>=2.0" in deps


def test_skip_disabled_plugin(tmp_path):
    """Disabled plugins' deps are not collected."""
    plugin_dir = tmp_path / "disabled_plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text(
        '{"name": "disabled_plugin", "version": "1.0", "python_dependencies": ["numpy"]}'
    )
    deps = collect_plugin_dependencies(
        plugin_folders=[tmp_path],
        enabled_plugins=[],  # nothing enabled
    )
    assert deps == []


def test_workspace_plugin_overrides(tmp_path):
    """Workspace add/remove overrides modify the effective plugin list."""
    for name, dep in [("plugA", "aaa"), ("plugB", "bbb"), ("plugC", "ccc")]:
        d = tmp_path / name
        d.mkdir()
        (d / "plugin.json").write_text(
            f'{{"name": "{name}", "version": "1.0", "python_dependencies": ["{dep}"]}}'
        )
    deps = collect_plugin_dependencies(
        plugin_folders=[tmp_path],
        enabled_plugins=["plugA", "plugB"],
        workspace_plugins_add=["plugC"],
        workspace_plugins_remove=["plugB"],
    )
    assert "aaa" in deps
    assert "bbb" not in deps
    assert "ccc" in deps
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_plugin_deps.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# SciQLop/core/plugin_deps.py
"""Collect python_dependencies from enabled plugins."""

from __future__ import annotations

import json
from pathlib import Path


def collect_plugin_dependencies(
    plugin_folders: list[Path | str],
    enabled_plugins: list[str],
    workspace_plugins_add: list[str] | None = None,
    workspace_plugins_remove: list[str] | None = None,
) -> list[str]:
    effective = set(enabled_plugins)
    if workspace_plugins_add:
        effective.update(workspace_plugins_add)
    if workspace_plugins_remove:
        effective -= set(workspace_plugins_remove)

    deps: list[str] = []
    for folder in plugin_folders:
        folder = Path(folder)
        if not folder.is_dir():
            continue
        for plugin_dir in folder.iterdir():
            if not plugin_dir.is_dir():
                continue
            if plugin_dir.name not in effective:
                continue
            desc_path = plugin_dir / "plugin.json"
            if not desc_path.exists():
                continue
            try:
                desc = json.loads(desc_path.read_text())
                deps.extend(desc.get("python_dependencies", []))
            except (json.JSONDecodeError, OSError):
                continue
    return deps
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_plugin_deps.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add SciQLop/core/plugin_deps.py tests/test_plugin_deps.py
git commit -m "feat: add plugin dependency collector with workspace overrides"
```

---

### Task 6: Workspace preparation orchestrator

**Files:**
- Create: `SciQLop/core/workspace_setup.py`
- Test: `tests/test_workspace_setup.py`
- Read: `SciQLop/core/workspace_manifest.py` (Task 2)
- Read: `SciQLop/core/workspace_project.py` (Task 3)
- Read: `SciQLop/core/workspace_venv.py` (Task 4)
- Read: `SciQLop/core/plugin_deps.py` (Task 5)

This is the high-level function the launcher calls: given a workspace directory, prepare everything and return the Python path to use.

**Step 1: Write the failing test**

```python
# tests/test_workspace_setup.py
from unittest.mock import patch, MagicMock
from pathlib import Path
from SciQLop.core.workspace_setup import prepare_workspace
from SciQLop.core.workspace_manifest import WorkspaceManifest


def test_prepare_workspace_creates_manifest_if_missing(tmp_path):
    """If no manifest exists, creates a default one."""
    with patch("SciQLop.core.workspace_setup.WorkspaceVenv") as MockVenv:
        mock_venv = MagicMock()
        mock_venv.python_path = tmp_path / ".venv" / "bin" / "python"
        MockVenv.return_value = mock_venv
        with patch("SciQLop.core.workspace_setup.collect_plugin_dependencies", return_value=[]):
            with patch("SciQLop.core.workspace_setup.get_globally_enabled_plugins", return_value=[]):
                with patch("SciQLop.core.workspace_setup.get_plugin_folders", return_value=[]):
                    prepare_workspace(tmp_path, workspace_name="New Study")

    manifest_path = tmp_path / "workspace.sciqlop"
    assert manifest_path.exists()
    m = WorkspaceManifest.load(manifest_path)
    assert m.name == "New Study"


def test_prepare_workspace_generates_pyproject(tmp_path):
    """Generates pyproject.toml from manifest + plugin deps."""
    manifest = WorkspaceManifest(name="Test", requires=["scipy"])
    manifest.save(tmp_path / "workspace.sciqlop")

    with patch("SciQLop.core.workspace_setup.WorkspaceVenv") as MockVenv:
        mock_venv = MagicMock()
        mock_venv.python_path = tmp_path / ".venv" / "bin" / "python"
        MockVenv.return_value = mock_venv
        with patch("SciQLop.core.workspace_setup.collect_plugin_dependencies", return_value=["speasy>=1.6.1"]):
            with patch("SciQLop.core.workspace_setup.get_globally_enabled_plugins", return_value=[]):
                with patch("SciQLop.core.workspace_setup.get_plugin_folders", return_value=[]):
                    prepare_workspace(tmp_path)

    pyproject = tmp_path / "pyproject.toml"
    assert pyproject.exists()
    content = pyproject.read_text()
    assert "scipy" in content
    assert "speasy>=1.6.1" in content
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_workspace_setup.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# SciQLop/core/workspace_setup.py
"""High-level workspace preparation: manifest -> pyproject.toml -> venv sync."""

from __future__ import annotations

from pathlib import Path

from SciQLop.core.workspace_manifest import WorkspaceManifest
from SciQLop.core.workspace_project import generate_pyproject_toml
from SciQLop.core.workspace_venv import WorkspaceVenv
from SciQLop.core.plugin_deps import collect_plugin_dependencies
from SciQLop.components.plugins.backend.loader.loader import plugins_folders
from SciQLop.components.plugins.backend.settings import SciQLopPluginsSettings


def get_globally_enabled_plugins() -> list[str]:
    settings = SciQLopPluginsSettings()
    return [name for name, enabled in settings.plugins.items() if enabled]


def get_plugin_folders() -> list[str]:
    return plugins_folders()


def prepare_workspace(
    workspace_dir: Path | str,
    workspace_name: str | None = None,
    locked: bool = False,
) -> Path:
    """Prepare a workspace: ensure manifest, generate pyproject.toml, sync venv.

    Returns the path to the workspace venv's Python executable.
    """
    workspace_dir = Path(workspace_dir)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = workspace_dir / "workspace.sciqlop"
    if manifest_path.exists():
        manifest = WorkspaceManifest.load(manifest_path)
    else:
        manifest = WorkspaceManifest.default(workspace_name or workspace_dir.name)
        manifest.save(manifest_path)

    # Collect plugin dependencies
    plugin_folders = get_plugin_folders()
    enabled = get_globally_enabled_plugins()
    plugin_deps = collect_plugin_dependencies(
        plugin_folders=plugin_folders,
        enabled_plugins=enabled,
        workspace_plugins_add=manifest.plugins_add,
        workspace_plugins_remove=manifest.plugins_remove,
    )

    # Generate pyproject.toml
    pyproject_path = workspace_dir / "pyproject.toml"
    generate_pyproject_toml(manifest, plugin_deps, pyproject_path)

    # Create and sync venv
    venv = WorkspaceVenv(workspace_dir)
    venv.ensure()
    venv.sync(locked=locked)

    return venv.python_path
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_workspace_setup.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add SciQLop/core/workspace_setup.py tests/test_workspace_setup.py
git commit -m "feat: add workspace preparation orchestrator"
```

---

### Task 7: Refactor launcher as workspace-aware supervisor

**Files:**
- Modify: `SciQLop/sciqlop_launcher.py` (lines 53-81)
- Modify: `SciQLop/app.py` (lines 1-4, add argparse)
- Read: `SciQLop/components/workspaces/backend/settings.py` (for workspace dir)
- Test: `tests/test_launcher.py`

The launcher gains `--workspace` argument handling and spawns the Qt app under the workspace venv's Python.

**Step 1: Write the failing test**

```python
# tests/test_launcher.py
from unittest.mock import patch, MagicMock
from SciQLop.sciqlop_launcher import resolve_workspace_dir, parse_args


def test_parse_args_default():
    args = parse_args([])
    assert args.workspace is None
    assert args.sciqlop_file is None


def test_parse_args_workspace_name():
    args = parse_args(["--workspace", "my-study"])
    assert args.workspace == "my-study"


def test_parse_args_sciqlop_file():
    args = parse_args(["study.sciqlop"])
    assert args.sciqlop_file == "study.sciqlop"


def test_resolve_default_workspace():
    with patch("SciQLop.sciqlop_launcher.SciQLopWorkspacesSettings") as MockSettings:
        MockSettings.return_value.workspaces_dir = "/fake/workspaces"
        d = resolve_workspace_dir(workspace_name=None, sciqlop_file=None)
        assert d.name == "default"
        assert "/fake/workspaces" in str(d)


def test_resolve_named_workspace():
    with patch("SciQLop.sciqlop_launcher.SciQLopWorkspacesSettings") as MockSettings:
        MockSettings.return_value.workspaces_dir = "/fake/workspaces"
        d = resolve_workspace_dir(workspace_name="my-study", sciqlop_file=None)
        assert d.name == "my-study"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_launcher.py -v`
Expected: FAIL with `ImportError` (functions don't exist yet)

**Step 3: Rewrite launcher**

Replace the core of `sciqlop_launcher.py`. Keep the restart loop but add workspace resolution and venv-based subprocess launch.

```python
# SciQLop/sciqlop_launcher.py
"""SciQLop launcher — workspace-aware supervisor process.

Resolves the target workspace, prepares its venv via uv, and launches
the Qt application as a subprocess under the workspace venv's Python.
Handles restart (exit 64) and workspace switching (exit 65).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from SciQLop.components.workspaces.backend.settings import SciQLopWorkspacesSettings
from SciQLop.core.workspace_manifest import WorkspaceManifest
from SciQLop.core.workspace_setup import prepare_workspace

EXIT_RESTART = 64
EXIT_SWITCH_WORKSPACE = 65
SWITCH_WORKSPACE_FILE = ".sciqlop_switch_target"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SciQLop launcher")
    parser.add_argument("--workspace", "-w", type=str, default=None,
                        help="Workspace name or path")
    parser.add_argument("sciqlop_file", nargs="?", default=None,
                        help="Path to a .sciqlop or .sciqlop-archive file")
    return parser.parse_args(argv)


def resolve_workspace_dir(
    workspace_name: str | None,
    sciqlop_file: str | None,
) -> Path:
    settings = SciQLopWorkspacesSettings()
    workspaces_root = Path(settings.workspaces_dir)

    if sciqlop_file:
        sciqlop_path = Path(sciqlop_file)
        if sciqlop_path.suffix == ".sciqlop":
            # .sciqlop file: use its parent as workspace dir
            return sciqlop_path.parent
        # TODO: handle .sciqlop-archive (Task 9)

    if workspace_name:
        # Check if it's an absolute path
        candidate = Path(workspace_name)
        if candidate.is_absolute():
            return candidate
        return workspaces_root / workspace_name

    return workspaces_root / "default"


def _read_switch_target(workspace_dir: Path) -> str | None:
    switch_file = workspace_dir / SWITCH_WORKSPACE_FILE
    if switch_file.exists():
        target = switch_file.read_text().strip()
        switch_file.unlink()
        return target
    return None


def run_sciqlop(python_path: Path) -> int:
    """Launch the SciQLop Qt app under the given Python and return exit code."""
    env = os.environ.copy()
    result = subprocess.run(
        [str(python_path), "-m", "SciQLop.sciqlop_app"],
        env=env,
    )
    return result.returncode


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    workspace_dir = resolve_workspace_dir(args.workspace, args.sciqlop_file)

    while True:
        python_path = prepare_workspace(workspace_dir)
        exit_code = run_sciqlop(python_path)

        if exit_code == EXIT_RESTART:
            continue
        elif exit_code == EXIT_SWITCH_WORKSPACE:
            target = _read_switch_target(workspace_dir)
            if target:
                workspace_dir = resolve_workspace_dir(
                    workspace_name=target, sciqlop_file=None
                )
            continue
        else:
            sys.exit(exit_code)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_launcher.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add SciQLop/sciqlop_launcher.py tests/test_launcher.py
git commit -m "feat: refactor launcher as workspace-aware supervisor"
```

---

### Task 8: Workspace switching protocol in the Qt app

**Files:**
- Modify: `SciQLop/sciqlop_app.py` (around line 71-72, `RESTART_SCIQLOP` handling)
- Read: `SciQLop/components/workspaces/ui/workspace_manager_ui.py`
- Read: `SciQLop/components/workspaces/backend/workspaces_manager.py`

Add a mechanism for the Qt app to signal "switch to workspace X" back to the launcher.

**Step 1: Add the switch workspace function**

In `SciQLop/sciqlop_app.py`, add a function that writes the target workspace to the switch file and sets the exit code:

```python
# Add to sciqlop_app.py

EXIT_SWITCH_WORKSPACE = 65
SWITCH_WORKSPACE_FILE = ".sciqlop_switch_target"


def switch_workspace(workspace_name: str) -> None:
    """Signal the launcher to restart with a different workspace."""
    from SciQLop.components.workspaces.backend.settings import SciQLopWorkspacesSettings
    settings = SciQLopWorkspacesSettings()
    # Write the target workspace name to current workspace dir
    workspace_dir = Path(os.environ.get("SCIQLOP_WORKSPACE_DIR", "."))
    (workspace_dir / SWITCH_WORKSPACE_FILE).write_text(workspace_name)
    # Tell Qt to exit with the switch code
    from PySide6.QtWidgets import QApplication
    QApplication.exit(EXIT_SWITCH_WORKSPACE)
```

**Step 2: Pass workspace dir as env var from launcher**

In the launcher's `run_sciqlop()` (Task 7), add:

```python
env["SCIQLOP_WORKSPACE_DIR"] = str(workspace_dir)
```

**Step 3: Wire workspace selection UI to `switch_workspace()`**

This depends on the existing workspace picker UI. Read the welcome panel code and connect the workspace selection signal to `switch_workspace()`. The exact wiring depends on the current UI structure — inspect and adapt.

**Step 4: Test manually**

Run: `uv run sciqlop --workspace default`
- In welcome panel, select a different workspace
- Verify the app exits and relaunches with the new workspace

**Step 5: Commit**

```bash
git add SciQLop/sciqlop_app.py SciQLop/sciqlop_launcher.py
git commit -m "feat: add workspace switching protocol between Qt app and launcher"
```

---

### Task 9: Archive export and import

**Files:**
- Create: `SciQLop/core/workspace_archive.py`
- Test: `tests/test_workspace_archive.py`

**Step 1: Write the failing test**

```python
# tests/test_workspace_archive.py
import zipfile
from pathlib import Path
from SciQLop.core.workspace_manifest import WorkspaceManifest
from SciQLop.core.workspace_archive import export_workspace, import_workspace


def test_export_creates_archive(tmp_path):
    ws_dir = tmp_path / "my-workspace"
    ws_dir.mkdir()
    manifest = WorkspaceManifest(name="Export Test", requires=["scipy"])
    manifest.save(ws_dir / "workspace.sciqlop")
    (ws_dir / "uv.lock").write_text("# lockfile")
    nb_dir = ws_dir / "notebooks"
    nb_dir.mkdir()
    (nb_dir / "analysis.ipynb").write_text("{}")

    archive_path = tmp_path / "export.sciqlop-archive"
    export_workspace(ws_dir, archive_path)

    assert archive_path.exists()
    with zipfile.ZipFile(archive_path) as zf:
        names = zf.namelist()
        assert "workspace.sciqlop" in names
        assert "uv.lock" in names
        assert "notebooks/analysis.ipynb" in names
        # .venv and pyproject.toml should be excluded
        assert not any(n.startswith(".venv") for n in names)
        assert "pyproject.toml" not in names


def test_import_creates_workspace(tmp_path):
    # Create an archive first
    ws_dir = tmp_path / "source"
    ws_dir.mkdir()
    manifest = WorkspaceManifest(name="Import Test", requires=["numpy"])
    manifest.save(ws_dir / "workspace.sciqlop")
    (ws_dir / "uv.lock").write_text("# lockfile")

    archive_path = tmp_path / "test.sciqlop-archive"
    export_workspace(ws_dir, archive_path)

    # Import it
    target_dir = tmp_path / "imported"
    import_workspace(archive_path, target_dir)

    assert (target_dir / "workspace.sciqlop").exists()
    assert (target_dir / "uv.lock").exists()
    m = WorkspaceManifest.load(target_dir / "workspace.sciqlop")
    assert m.name == "Import Test"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_workspace_archive.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# SciQLop/core/workspace_archive.py
"""Export and import SciQLop workspace archives."""

from __future__ import annotations

import zipfile
from pathlib import Path

EXCLUDE_PATTERNS = {".venv", "pyproject.toml", "__pycache__"}


def export_workspace(workspace_dir: Path | str, archive_path: Path | str) -> None:
    workspace_dir = Path(workspace_dir)
    archive_path = Path(archive_path)

    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in workspace_dir.rglob("*"):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(workspace_dir)
            # Skip excluded paths
            if any(part in EXCLUDE_PATTERNS for part in rel.parts):
                continue
            zf.write(file_path, str(rel))


def import_workspace(archive_path: Path | str, target_dir: Path | str) -> Path:
    archive_path = Path(archive_path)
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(archive_path, "r") as zf:
        zf.extractall(target_dir)

    return target_dir
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_workspace_archive.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add SciQLop/core/workspace_archive.py tests/test_workspace_archive.py
git commit -m "feat: add workspace archive export/import"
```

---

### Task 10: Handle `.sciqlop-archive` in launcher

**Files:**
- Modify: `SciQLop/sciqlop_launcher.py` (in `resolve_workspace_dir()`)
- Test: update `tests/test_launcher.py`

**Step 1: Add test for archive import**

```python
# Add to tests/test_launcher.py

def test_resolve_sciqlop_archive(tmp_path):
    """Opening a .sciqlop-archive extracts and returns the workspace dir."""
    from SciQLop.core.workspace_manifest import WorkspaceManifest
    from SciQLop.core.workspace_archive import export_workspace

    # Create a source workspace and archive it
    src = tmp_path / "src"
    src.mkdir()
    WorkspaceManifest(name="Archived").save(src / "workspace.sciqlop")
    archive = tmp_path / "test.sciqlop-archive"
    export_workspace(src, archive)

    with patch("SciQLop.sciqlop_launcher.SciQLopWorkspacesSettings") as MockSettings:
        MockSettings.return_value.workspaces_dir = str(tmp_path / "workspaces")
        d = resolve_workspace_dir(workspace_name=None, sciqlop_file=str(archive))
        assert (d / "workspace.sciqlop").exists()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_launcher.py::test_resolve_sciqlop_archive -v`
Expected: FAIL (archive handling not implemented yet)

**Step 3: Add archive handling to `resolve_workspace_dir()`**

```python
# In sciqlop_launcher.py, update resolve_workspace_dir():

from SciQLop.core.workspace_archive import import_workspace

def resolve_workspace_dir(...) -> Path:
    ...
    if sciqlop_file:
        sciqlop_path = Path(sciqlop_file)
        if sciqlop_path.suffix == ".sciqlop":
            return sciqlop_path.parent
        elif sciqlop_path.suffix == ".sciqlop-archive":
            settings = SciQLopWorkspacesSettings()
            workspaces_root = Path(settings.workspaces_dir)
            # Use archive stem as workspace name
            target_dir = workspaces_root / sciqlop_path.stem
            if not (target_dir / "workspace.sciqlop").exists():
                import_workspace(sciqlop_path, target_dir)
            return target_dir
    ...
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_launcher.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add SciQLop/sciqlop_launcher.py tests/test_launcher.py
git commit -m "feat: handle .sciqlop-archive files in launcher"
```

---

### Task 11: Migration from old workspace format

**Files:**
- Create: `SciQLop/core/workspace_migration.py`
- Test: `tests/test_workspace_migration.py`
- Read: `SciQLop/core/data_models/models.py:10-19` (`WorkspaceSpec` dataclass)

**Step 1: Write the failing test**

```python
# tests/test_workspace_migration.py
import json
from SciQLop.core.workspace_migration import migrate_workspace
from SciQLop.core.workspace_manifest import WorkspaceManifest


def test_migrate_old_workspace(tmp_path):
    """Converts workspace.json to workspace.sciqlop."""
    old_spec = {
        "name": "Old Study",
        "description": "Legacy workspace",
        "dependencies": ["matplotlib", "scipy>=1.10"],
        "python_path": ["/some/old/path"],
        "notebooks": ["nb1.ipynb"],
        "last_used": "2025-01-01",
        "last_modified": "2025-01-01",
        "image": "",
        "default_workspace": False,
    }
    (tmp_path / "workspace.json").write_text(json.dumps(old_spec))
    deps_dir = tmp_path / "dependencies"
    deps_dir.mkdir()

    migrated = migrate_workspace(tmp_path)

    assert migrated is True
    assert (tmp_path / "workspace.sciqlop").exists()
    m = WorkspaceManifest.load(tmp_path / "workspace.sciqlop")
    assert m.name == "Old Study"
    assert m.description == "Legacy workspace"
    assert "matplotlib" in m.requires
    assert "scipy>=1.10" in m.requires
    # Old files should be renamed, not deleted (safety)
    assert (tmp_path / "workspace.json.bak").exists()


def test_skip_already_migrated(tmp_path):
    """If workspace.sciqlop exists, skip migration."""
    WorkspaceManifest(name="Already New").save(tmp_path / "workspace.sciqlop")
    migrated = migrate_workspace(tmp_path)
    assert migrated is False
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_workspace_migration.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# SciQLop/core/workspace_migration.py
"""Migrate old workspace.json format to .sciqlop manifest."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from SciQLop.core.workspace_manifest import WorkspaceManifest


def migrate_workspace(workspace_dir: Path | str) -> bool:
    """Migrate a workspace from old JSON format to .sciqlop TOML format.

    Returns True if migration was performed, False if skipped.
    """
    workspace_dir = Path(workspace_dir)
    manifest_path = workspace_dir / "workspace.sciqlop"
    old_spec_path = workspace_dir / "workspace.json"

    if manifest_path.exists():
        return False

    if not old_spec_path.exists():
        return False

    with open(old_spec_path) as f:
        old_spec = json.load(f)

    manifest = WorkspaceManifest(
        name=old_spec.get("name", workspace_dir.name),
        description=old_spec.get("description", ""),
        requires=old_spec.get("dependencies", []),
    )
    manifest.save(manifest_path)

    # Rename old files as backup (don't delete)
    old_spec_path.rename(old_spec_path.with_suffix(".json.bak"))

    # Remove old dependencies dir if empty
    deps_dir = workspace_dir / "dependencies"
    if deps_dir.exists():
        try:
            shutil.rmtree(deps_dir)
        except OSError:
            pass  # Non-empty or permission issue, leave it

    return True
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_workspace_migration.py -v`
Expected: PASS

**Step 5: Wire migration into workspace preparation**

In `SciQLop/core/workspace_setup.py`, add migration call before reading the manifest:

```python
from SciQLop.core.workspace_migration import migrate_workspace

def prepare_workspace(...) -> Path:
    workspace_dir = Path(workspace_dir)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    # Migrate old format if needed
    migrate_workspace(workspace_dir)

    manifest_path = workspace_dir / "workspace.sciqlop"
    ...
```

**Step 6: Commit**

```bash
git add SciQLop/core/workspace_migration.py SciQLop/core/workspace_setup.py tests/test_workspace_migration.py
git commit -m "feat: add workspace migration from old JSON format to .sciqlop"
```

---

### Task 12: Add `tomli-w` dependency and clean up old code

**Files:**
- Modify: `pyproject.toml` (add `tomli-w` to dependencies)
- Modify: `SciQLop/components/workspaces/backend/workspace.py` (remove pip-based installation)
- Read: `SciQLop/core/common/pip_process.py` (assess if still needed elsewhere)

**Step 1: Add tomli-w to pyproject.toml**

Add `"tomli-w"` to `[project] dependencies` in `pyproject.toml`.

For Python < 3.11 support, also add `"tomli; python_version < '3.11'"`.

**Step 2: Update workspace.py**

Remove `_ensure_all_dependencies_installed()` and the `pip_install_requirements` import. The workspace class should no longer install packages at runtime — this is handled pre-launch by the launcher.

Remove `add_to_python_path()` calls for the dependencies dir — the workspace venv handles this via `--system-site-packages`.

Keep the `Workspace` class for managing workspace metadata, notebooks, scripts, and the `workspace_spec` (which will transition to using `WorkspaceManifest`).

**Step 3: Assess pip_process.py**

Check if `pip_process.py` is used anywhere else. If not, it can be deprecated (leave in place but add a deprecation comment). Don't delete it yet in case it's needed for fallback.

**Step 4: Run existing tests**

Run: `uv run pytest -v`
Expected: All existing tests pass (workspace runtime behavior may need adjustment)

**Step 5: Commit**

```bash
git add pyproject.toml SciQLop/components/workspaces/backend/workspace.py
git commit -m "chore: add tomli-w dependency, remove runtime pip installation from workspace"
```

---

### Task 13: File association registration (Linux)

**Files:**
- Create: `scripts/desktop/sciqlop-mime.xml`
- Create: `scripts/desktop/sciqlop.desktop` (update if exists)
- Read: existing `.desktop` file if any

This is platform-specific. Start with Linux (freedesktop).

**Step 1: Create MIME type definition**

```xml
<!-- scripts/desktop/sciqlop-mime.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="application/x-sciqlop-workspace">
    <comment>SciQLop Workspace</comment>
    <glob pattern="*.sciqlop"/>
  </mime-type>
  <mime-type type="application/x-sciqlop-archive">
    <comment>SciQLop Workspace Archive</comment>
    <glob pattern="*.sciqlop-archive"/>
  </mime-type>
</mime-info>
```

**Step 2: Update .desktop file**

```ini
# scripts/desktop/sciqlop.desktop
[Desktop Entry]
Name=SciQLop
Exec=sciqlop %f
Icon=sciqlop
Type=Application
Categories=Science;Education;
MimeType=application/x-sciqlop-workspace;application/x-sciqlop-archive;
```

**Step 3: Document installation**

Add install instructions to README or a setup script:

```bash
# Install MIME types
xdg-mime install scripts/desktop/sciqlop-mime.xml
# Install desktop entry
xdg-desktop-menu install scripts/desktop/sciqlop.desktop
# Update MIME database
update-mime-database ~/.local/share/mime
```

**Step 4: Commit**

```bash
git add scripts/desktop/
git commit -m "feat: add freedesktop MIME types and .desktop entry for file associations"
```

---

## Task dependency graph

```
Task 1 (uv resolution)
    └── Task 4 (venv manager) ─┐
Task 2 (manifest) ─────────────┤
Task 3 (pyproject gen) ────────┤
Task 5 (plugin deps) ──────────┤
                                └── Task 6 (orchestrator)
                                        └── Task 7 (launcher refactor)
                                                ├── Task 8 (workspace switching)
                                                └── Task 10 (archive in launcher)
Task 9 (archive export/import) ─── Task 10
Task 11 (migration) ─────────────── Task 6 (wired in)
Task 12 (cleanup) ─── after Task 7
Task 13 (file associations) ─── independent
```

Tasks 1, 2, 3, 5, 9, 13 can be done in parallel.
Tasks 4, 6, 7 are sequential.
Tasks 8, 10, 11, 12 depend on 7.
