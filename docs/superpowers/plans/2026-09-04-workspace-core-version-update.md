# Update SciQLop Core Version Per Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user change which SciQLop version a workspace installs, from a new "SciQLop Core" section in the welcome pane's workspace-details panel.

**Architecture:** Two pure/IO helpers (PyPI release fetch + version validation) in `workspace_project.py`; a small stdlib-only per-workspace lock module; an `apply_core_version()` orchestrator in `workspace_setup.py` that stages the new version in memory and reuses the existing `prepare_workspace()` pipeline (now accepting a pre-loaded manifest and a `strict` flag) so it gets the exact same plugin/AppStore dependency collection and lockfile handling as ordinary launcher startup, only persisting the manifest change after a successful sync; two thin `WelcomeBackend` Qt slots exposing this to the page, matching the existing daemon-thread-plus-one-signal pattern; and welcome.js/css rendering one dropdown + Install button.

**Tech Stack:** Python 3.11+, PySide6 (QObject/Signal/Slot, QWebChannel), `uv` subprocess, PyPI JSON API, `packaging.version`, pytest + pytest-qt, vanilla JS/CSS (no build step, no JS test harness in this repo).

**Spec:** `docs/superpowers/specs/2026-09-04-workspace-core-version-update-design.md`

## Global Constraints

- No new Python dependency — the per-workspace lock is a stdlib-only `O_CREAT|O_EXCL` marker file, not `filelock`/`portalocker`.
- PyPI's JSON API (`https://pypi.org/pypi/SciQLop/json`) is the source of truth for installable versions — never GitHub release tags for this feature (the existing read-only banner keeps using GitHub; the two are not assumed to correspond 1:1).
- The manifest's `sciqlop_version` is only ever persisted to disk *after* the corresponding venv sync has actually succeeded — never before.
- A user-initiated version change must fail loudly on sync failure — never silently fall back to "keep whatever's already installed" and report success (that tolerance is correct for ordinary launcher startup, wrong here).
- No auto-restart, no wiring into `EXIT_RESTART` — only a "restart to apply" status message when the updated workspace is the active one.
- Progress reporting matches the existing pattern used by `add_dependencies_to_workspace`/AppStore install: a daemon `threading.Thread` plus exactly one Qt signal emitted at completion. No streaming/log UI.
- Every new/modified Python function must keep default-argument behavior byte-identical for existing callers when new parameters are omitted.

---

## Task 1: Share `error_detail()` between AppStore and the new welcome slots

**Files:**
- Modify: `SciQLop/components/workspaces/backend/uv.py`
- Modify: `SciQLop/components/appstore/backend.py:1-40,128-137,258,284`
- Modify: `tests/test_uv_resolution.py`
- Modify: `tests/test_appstore_install.py:1-28,81-98`

**Interfaces:**
- Produces: `error_detail(exc: Exception) -> str` in `SciQLop.components.workspaces.backend.uv` — human-readable failure cause, preferring `exc.stderr` (e.g. from `subprocess.CalledProcessError`) over `str(exc)`. Used by Task 5's `apply_core_version` slot.

- [ ] **Step 1: Write the failing test in `tests/test_uv_resolution.py`**

Append to the end of the file:

```python
class TestErrorDetail:
    def test_prefers_subprocess_stderr(self):
        import subprocess
        from SciQLop.components.workspaces.backend.uv import error_detail

        exc = subprocess.CalledProcessError(
            1, ["uv", "pip", "install"],
            stderr="error: TLS connect: certificate verify failed (proxy CA)",
        )
        detail = error_detail(exc)
        assert "certificate verify failed" in detail
        assert "returned non-zero exit status" not in detail

    def test_falls_back_to_str_when_no_stderr(self):
        from SciQLop.components.workspaces.backend.uv import error_detail

        assert "boom" in error_detail(RuntimeError("boom"))

    def test_ignores_empty_stderr(self):
        import subprocess
        from SciQLop.components.workspaces.backend.uv import error_detail

        exc = subprocess.CalledProcessError(1, ["uv"], stderr="")
        assert error_detail(exc).strip() != ""
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_uv_resolution.py::TestErrorDetail -v`
Expected: FAIL with `ImportError: cannot import name 'error_detail'`

- [ ] **Step 3: Add `error_detail()` to `uv.py`**

In `SciQLop/components/workspaces/backend/uv.py`, append after `uv_command()`:

```python
def error_detail(exc: Exception) -> str:
    """Human-readable cause for a failed uv run.

    ``str(CalledProcessError)`` is only "… returned non-zero exit status N";
    the actual reason (proxy/TLS/auth) is in ``.stderr``. Prefer it so the
    failure is diagnosable instead of a bare "Failed".
    """
    stderr = (getattr(exc, "stderr", None) or "").strip()
    return stderr or str(exc)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_uv_resolution.py::TestErrorDetail -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Point AppStore's backend at the shared helper**

In `SciQLop/components/appstore/backend.py`:

1. Delete the local `_error_detail` function (lines 128-136):

```python
def _error_detail(exc: Exception) -> str:
    """Human-readable cause for a failed uv run.

    ``str(CalledProcessError)`` is only "… returned non-zero exit status N";
    the actual reason (proxy/TLS/auth) is in ``.stderr``. Prefer it so the
    failure is diagnosable instead of a bare "Failed".
    """
    stderr = (getattr(exc, "stderr", None) or "").strip()
    return stderr or str(exc)
```

2. Add to the existing import from `workspaces.backend.uv`:

```python
from SciQLop.components.workspaces.backend.uv import error_detail, uv_command
```

(replacing the current `from SciQLop.components.workspaces.backend.uv import uv_command`)

3. In `install_package`'s `_install()` closure and `uninstall_package`'s `_uninstall()` closure, replace both call sites `_error_detail(e)` with `error_detail(e)`.

- [ ] **Step 6: Update `tests/test_appstore_install.py` to import from the new location**

Replace the import block:

```python
from SciQLop.components.appstore.backend import (
    _uv_install_cmd,
    _uv_uninstall_cmd,
    _error_detail,
    _write_requirements_file,
)
from SciQLop.components.workspaces.backend.uv import find_uv
```

with:

```python
from SciQLop.components.appstore.backend import (
    _uv_install_cmd,
    _uv_uninstall_cmd,
    _write_requirements_file,
)
from SciQLop.components.workspaces.backend.uv import error_detail, find_uv
```

And in `TestErrorDetail` (now redundant with Task 1's new test class, but this class currently also imports `_error_detail` — delete the whole `TestErrorDetail` class from this file, lines 81-98, since its coverage now lives in `tests/test_uv_resolution.py`).

- [ ] **Step 7: Run both test files to verify everything still passes**

Run: `uv run pytest tests/test_uv_resolution.py tests/test_appstore_install.py -v`
Expected: PASS, no `_error_detail` references remain

- [ ] **Step 8: Commit**

```bash
git add SciQLop/components/workspaces/backend/uv.py SciQLop/components/appstore/backend.py tests/test_uv_resolution.py tests/test_appstore_install.py
git commit -m "refactor: share error_detail() between AppStore and workspace uv callers"
```

---

## Task 2: Per-workspace update lock

**Files:**
- Create: `SciQLop/components/workspaces/backend/workspace_lock.py`
- Test: `tests/test_workspace_lock.py`

**Interfaces:**
- Produces: `workspace_lock(workspace_dir: Path | str)` — a context manager, and `WorkspaceLockError(RuntimeError)`, both in `SciQLop.components.workspaces.backend.workspace_lock`. Used by Task 5's `apply_core_version`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_workspace_lock.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_workspace_lock.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'SciQLop.components.workspaces.backend.workspace_lock'`

- [ ] **Step 3: Implement `workspace_lock.py`**

Create `SciQLop/components/workspaces/backend/workspace_lock.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_workspace_lock.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/workspaces/backend/workspace_lock.py tests/test_workspace_lock.py
git commit -m "feat: add a per-workspace exclusive update lock"
```

---

## Task 3: PyPI release list + version validation

**Files:**
- Modify: `SciQLop/components/workspaces/backend/workspace_project.py`
- Modify: `tests/test_workspace_project.py`

**Interfaces:**
- Produces: `fetch_available_versions(*, timeout: float = 5.0) -> List[str]` and `validate_core_version(version: str, available: Sequence[str]) -> bool` in `SciQLop.components.workspaces.backend.workspace_project`. Used by Task 6's `WelcomeBackend` slots and Task 5's `apply_core_version`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_workspace_project.py` (add `import json` and `from unittest.mock import MagicMock, patch` to the file's existing imports if not already present — check the top of the file first; currently it only imports `importlib.metadata, os, re, sys, tempfile, Path, pytest` plus the module under test):

```python
class TestFetchAvailableVersions:
    MODULE = "SciQLop.components.workspaces.backend.workspace_project"

    def _pypi_response(self, releases):
        resp = MagicMock()
        resp.read.return_value = json.dumps({"releases": releases}).encode()
        resp.__enter__.return_value = resp
        return resp

    def test_sorts_newest_first(self):
        from SciQLop.components.workspaces.backend.workspace_project import fetch_available_versions

        releases = {
            "0.12.0": [{"yanked": False}],
            "0.13.0": [{"yanked": False}],
            "0.11.0": [{"yanked": False}],
        }
        with patch("urllib.request.urlopen", return_value=self._pypi_response(releases)):
            assert fetch_available_versions() == ["0.13.0", "0.12.0", "0.11.0"]

    def test_excludes_yanked_releases(self):
        from SciQLop.components.workspaces.backend.workspace_project import fetch_available_versions

        releases = {
            "0.13.0": [{"yanked": False}],
            "0.12.0": [{"yanked": True}],
        }
        with patch("urllib.request.urlopen", return_value=self._pypi_response(releases)):
            assert fetch_available_versions() == ["0.13.0"]

    def test_excludes_prerelease_and_dev_releases(self):
        from SciQLop.components.workspaces.backend.workspace_project import fetch_available_versions

        releases = {
            "0.13.0": [{"yanked": False}],
            "0.13.0rc1": [{"yanked": False}],
            "0.13.0.dev0": [{"yanked": False}],
        }
        with patch("urllib.request.urlopen", return_value=self._pypi_response(releases)):
            assert fetch_available_versions() == ["0.13.0"]

    def test_excludes_releases_with_no_files(self):
        from SciQLop.components.workspaces.backend.workspace_project import fetch_available_versions

        releases = {"0.13.0": [{"yanked": False}], "0.12.0": []}
        with patch("urllib.request.urlopen", return_value=self._pypi_response(releases)):
            assert fetch_available_versions() == ["0.13.0"]

    def test_caps_to_recent_n(self):
        from SciQLop.components.workspaces.backend.workspace_project import (
            _MAX_LISTED_VERSIONS,
            fetch_available_versions,
        )

        releases = {f"0.{i}.0": [{"yanked": False}] for i in range(30)}
        with patch("urllib.request.urlopen", return_value=self._pypi_response(releases)):
            result = fetch_available_versions()
            assert len(result) == _MAX_LISTED_VERSIONS
            assert result[0] == "0.29.0"

    def test_network_failure_returns_empty_list(self):
        from SciQLop.components.workspaces.backend.workspace_project import fetch_available_versions

        with patch("urllib.request.urlopen", side_effect=OSError("unreachable")):
            assert fetch_available_versions() == []

    def test_malformed_json_returns_empty_list(self):
        from SciQLop.components.workspaces.backend.workspace_project import fetch_available_versions

        resp = MagicMock()
        resp.read.return_value = b"not json"
        resp.__enter__.return_value = resp
        with patch("urllib.request.urlopen", return_value=resp):
            assert fetch_available_versions() == []


class TestValidateCoreVersion:
    def test_empty_string_is_always_valid(self):
        from SciQLop.components.workspaces.backend.workspace_project import validate_core_version

        assert validate_core_version("", []) is True
        assert validate_core_version("", ["0.13.0"]) is True

    def test_exact_match_is_valid(self):
        from SciQLop.components.workspaces.backend.workspace_project import validate_core_version

        assert validate_core_version("0.13.0", ["0.13.0", "0.12.0"]) is True

    def test_version_not_in_list_is_rejected(self):
        from SciQLop.components.workspaces.backend.workspace_project import validate_core_version

        assert validate_core_version("0.99.0", ["0.13.0"]) is False

    @pytest.mark.parametrize("hostile", [
        "0.13.0; rm -rf /",
        "0.13.0 @ https://evil.example/x.whl",
        "0.13.0\nsciqlop[all] @ git+https://evil.example/repo",
        "../../etc/passwd",
        "0.13.0'",
        "sciqlop[all]==0.13.0",
    ])
    def test_hostile_strings_are_rejected(self, hostile):
        from SciQLop.components.workspaces.backend.workspace_project import validate_core_version

        assert validate_core_version(hostile, ["0.13.0"]) is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_workspace_project.py::TestFetchAvailableVersions tests/test_workspace_project.py::TestValidateCoreVersion -v`
Expected: FAIL with `ImportError: cannot import name 'fetch_available_versions'`

- [ ] **Step 3: Implement in `workspace_project.py`**

Add `json` and `urllib.request` to the stdlib imports at the top (currently `hashlib, importlib.metadata, logging, os, re, sys`):

```python
import hashlib
import importlib.metadata
import json
import logging
import os
import re
import sys
import urllib.request
```

Add a new import line right after those, before the `SciQLop.*` imports:

```python
import packaging.version
```

Add near the other module-level constants (after `_DEV_BUILD_REQUIREMENT`):

```python
# Source of truth for what SciQLop version a workspace can actually install
# -- GitHub release tags (used by the read-only "update available" banner in
# the welcome pane) are not assumed to correspond 1:1 with PyPI releases.
_PYPI_JSON_URL = "https://pypi.org/pypi/SciQLop/json"
_MAX_LISTED_VERSIONS = 15
```

Add at the end of the file:

```python
def fetch_available_versions(*, timeout: float = 5.0) -> List[str]:
    """Recent installable SciQLop releases from PyPI, newest first.

    Excludes yanked and prerelease/dev releases: a workspace's
    ``sciqlop_version`` must be exact-pinnable and reproducible, and neither
    kind of release satisfies that. Returns an empty list on any
    network/parsing failure -- callers decide the UI fallback.
    """
    req = urllib.request.Request(_PYPI_JSON_URL, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except Exception as exc:
        log.debug("Could not fetch PyPI release list: %s", exc)
        return []

    releases = data.get("releases", {})
    versions: List[packaging.version.Version] = []
    for raw, files in releases.items():
        if not files or all(f.get("yanked", False) for f in files):
            continue
        try:
            parsed = packaging.version.Version(raw)
        except packaging.version.InvalidVersion:
            continue
        if parsed.is_prerelease:
            continue
        versions.append(parsed)

    versions.sort(reverse=True)
    return [str(v) for v in versions[:_MAX_LISTED_VERSIONS]]


def validate_core_version(version: str, available: Sequence[str]) -> bool:
    """True if *version* is safe to write into a workspace manifest.

    Accepts only the empty string (installs from ``git+...@main``, see
    ``sciqlop_requirement``) or an exact match against *available* -- which
    must come from ``fetch_available_versions()``, never from unvalidated
    caller input. This is the real security boundary: the dropdown a user
    picks from in the UI is not one, since a QWebChannel caller can invoke
    the backend slot with an arbitrary string, and the value is later
    interpolated into ``sciqlop_requirement()``'s output.
    """
    if version == "":
        return True
    return version in available
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_workspace_project.py -v`
Expected: PASS (all tests in the file, including the pre-existing ones)

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/workspaces/backend/workspace_project.py tests/test_workspace_project.py
git commit -m "feat: fetch installable SciQLop versions from PyPI and validate them"
```

---

## Task 4: `prepare_workspace()` accepts a pre-loaded manifest and a strict sync mode

**Files:**
- Modify: `SciQLop/components/workspaces/backend/workspace_setup.py:43-56,131-180,229-234`
- Modify: `tests/test_workspace_setup.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `prepare_workspace(workspace_dir, workspace_name=None, locked=False, on_output=None, manifest: WorkspaceManifest | None = None, strict: bool = False) -> Path`. When `manifest` is given, it is used as-is instead of loading/creating one from `workspace_dir`'s on-disk `workspace.sciqlop`. When `strict=True`, a sync failure always raises instead of falling back to "keep whatever's already installed". Both default to preserving the exact current behavior. Used by Task 5's `apply_core_version`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_workspace_setup.py`, after the existing `TestPrepareWorkspaceOffline` class:

```python
class TestPrepareWorkspaceWithGivenManifest:
    def test_uses_the_given_manifest_instead_of_loading_from_disk(self, workspace_dir, patches):
        from SciQLop.components.workspaces.backend.workspace_setup import prepare_workspace

        manifest = WorkspaceManifest(name="InMemory", sciqlop_version="9.9.9")

        prepare_workspace(workspace_dir, manifest=manifest)

        gen_call = patches["generate_pyproject_toml"]
        gen_call.assert_called_once()
        assert gen_call.call_args[0][0] is manifest

    def test_does_not_write_a_manifest_file(self, workspace_dir, patches):
        from SciQLop.components.workspaces.backend.workspace_setup import prepare_workspace

        manifest = WorkspaceManifest(name="InMemory")
        prepare_workspace(workspace_dir, manifest=manifest)

        assert not (workspace_dir / "workspace.sciqlop").exists()

    def test_ignores_an_existing_on_disk_manifest(self, workspace_dir, patches):
        """A given manifest wins even if workspace_dir already has a
        different one on disk -- apply_core_version relies on this to stage
        an in-memory version change without a premature disk write."""
        from SciQLop.components.workspaces.backend.workspace_setup import prepare_workspace

        workspace_dir.mkdir(parents=True)
        WorkspaceManifest(name="OnDisk").save(workspace_dir / "workspace.sciqlop")

        manifest = WorkspaceManifest(name="InMemory")
        prepare_workspace(workspace_dir, manifest=manifest)

        gen_call = patches["generate_pyproject_toml"]
        assert gen_call.call_args[0][0].name == "InMemory"


class TestPrepareWorkspaceStrictMode:
    """strict=True is for a user-initiated version change: a sync failure
    must always be reported as a failure, never silently swallowed by
    falling back to whatever venv already exists (issue #115's tolerance is
    correct for ordinary launcher startup, wrong for an explicit update)."""

    def test_strict_raises_even_when_sciqlop_already_installed(self, workspace_dir, patches, tmp_path):
        from SciQLop.components.workspaces.backend.workspace_setup import prepare_workspace

        venv = patches["venv"]
        python_path = tmp_path / "python"
        python_path.write_text("")
        venv.python_path = python_path
        venv.has_sciqlop_installed = True
        venv.sync.side_effect = RuntimeError("uv command failed: offline")

        with pytest.raises(RuntimeError, match="offline"):
            prepare_workspace(workspace_dir, workspace_name="Test", strict=True)

    def test_non_strict_still_tolerates_offline_failure(self, workspace_dir, patches, tmp_path):
        """Default behavior (strict=False) is unchanged from before this
        parameter existed."""
        from SciQLop.components.workspaces.backend.workspace_setup import prepare_workspace

        venv = patches["venv"]
        python_path = tmp_path / "python"
        python_path.write_text("")
        venv.python_path = python_path
        venv.has_sciqlop_installed = True
        venv.sync.side_effect = RuntimeError("offline")

        result = prepare_workspace(workspace_dir, workspace_name="Test")

        assert result == python_path
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_workspace_setup.py::TestPrepareWorkspaceWithGivenManifest tests/test_workspace_setup.py::TestPrepareWorkspaceStrictMode -v`
Expected: FAIL — `TypeError: prepare_workspace() got an unexpected keyword argument 'manifest'`

- [ ] **Step 3: Add the `manifest` and `strict` parameters**

In `SciQLop/components/workspaces/backend/workspace_setup.py`, replace `_sync_workspace_venv`'s signature and its two internal calls:

```python
def _sync_workspace_venv(
    venv: WorkspaceVenv,
    manifest: WorkspaceManifest,
    optional_deps: list[str],
    pyproject_path: Path,
    locked: bool,
    on_output: Callable[[str], None] | None,
    strict: bool = False,
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
    exc = _try_sync(venv, locked=locked, on_output=on_output)
    if exc is None:
        return True
    _report_sync_failure(exc, on_output)

    if locked:
        if on_output is not None:
            on_output("Archive lockfile could not be honored, resolving fresh")
        return _sync_workspace_venv(
            venv, manifest, optional_deps, pyproject_path, False, on_output, strict,
        )

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
```

Replace `prepare_workspace`'s signature, docstring, and Step 1 body:

```python
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
```

Finally, update the `_sync_workspace_venv` call site (Step 6) to thread `strict` through:

```python
    synced = _sync_workspace_venv(
        venv, manifest, plugin_deps + appstore_deps, pyproject_path, effective_locked, on_output,
        strict=strict,
    )
```

Everything else in the function (steps 2-5, the rest of step 6, the docstring's Returns section) is unchanged.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_workspace_setup.py -v`
Expected: PASS — all existing classes in the file (unchanged behavior) plus the two new ones

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/workspaces/backend/workspace_setup.py tests/test_workspace_setup.py
git commit -m "feat: let prepare_workspace() accept a pre-loaded manifest and a strict sync mode"
```

---

## Task 5: `apply_core_version()` orchestrator

**Files:**
- Modify: `SciQLop/components/workspaces/backend/workspace_setup.py` (imports + new function at end of file)
- Modify: `tests/test_workspace_setup.py`

**Interfaces:**
- Consumes: `prepare_workspace(workspace_dir, manifest=..., strict=...)` from Task 4; `workspace_lock(workspace_dir)` / `WorkspaceLockError` from Task 2.
- Produces: `apply_core_version(workspace_dir: Path | str, version: str) -> Path` in `SciQLop.components.workspaces.backend.workspace_setup`. Raises `FileNotFoundError` if no manifest exists yet, `WorkspaceLockError` if another call is already in progress for that workspace, or whatever `prepare_workspace` raises on sync failure. Used by Task 6's `WelcomeBackend.apply_core_version` slot.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_workspace_setup.py`, at the end of the file, and add this import near the top of the file alongside the existing `WorkspaceManifest` import:

```python
from SciQLop.components.workspaces.backend.workspace_lock import WorkspaceLockError, workspace_lock
```

```python
class TestApplyCoreVersion:
    def _make_existing_workspace(self, workspace_dir, sciqlop_version="0.12.0"):
        workspace_dir.mkdir(parents=True)
        WorkspaceManifest(name="My Workspace", sciqlop_version=sciqlop_version).save(
            workspace_dir / "workspace.sciqlop")
        return workspace_dir

    def test_pins_the_new_version_and_saves_the_manifest(self, workspace_dir, patches):
        from SciQLop.components.workspaces.backend.workspace_setup import apply_core_version

        self._make_existing_workspace(workspace_dir)

        apply_core_version(workspace_dir, "0.13.0")

        reloaded = WorkspaceManifest.load(workspace_dir / "workspace.sciqlop")
        assert reloaded.sciqlop_version == "0.13.0"

    def test_preserves_plugin_and_appstore_dependencies_in_the_generated_project(self, workspace_dir, patches):
        """The bug an earlier design draft had: generating the pyproject
        with only SciQLop would silently drop plugin/appstore dependencies
        from the workspace on every core update."""
        from SciQLop.components.workspaces.backend.workspace_setup import apply_core_version

        self._make_existing_workspace(workspace_dir)

        apply_core_version(workspace_dir, "0.13.0")

        gen = patches["generate_pyproject_toml"]
        gen.assert_called_once()
        assert gen.call_args[0][1] == ["numpy>=1.24", "requests"]

    def test_returns_the_venv_python_path(self, workspace_dir, patches):
        from SciQLop.components.workspaces.backend.workspace_setup import apply_core_version

        self._make_existing_workspace(workspace_dir)

        result = apply_core_version(workspace_dir, "0.13.0")
        assert result == patches["venv"].python_path

    def test_empty_string_pins_to_main(self, workspace_dir, patches):
        from SciQLop.components.workspaces.backend.workspace_setup import apply_core_version

        self._make_existing_workspace(workspace_dir)

        apply_core_version(workspace_dir, "")

        reloaded = WorkspaceManifest.load(workspace_dir / "workspace.sciqlop")
        assert reloaded.sciqlop_version == ""

    def test_sync_failure_leaves_the_on_disk_manifest_unchanged(self, workspace_dir, patches):
        from SciQLop.components.workspaces.backend.workspace_setup import apply_core_version

        self._make_existing_workspace(workspace_dir)
        patches["venv"].sync.side_effect = RuntimeError("uv sync failed")

        with pytest.raises(RuntimeError, match="uv sync failed"):
            apply_core_version(workspace_dir, "0.13.0")

        reloaded = WorkspaceManifest.load(workspace_dir / "workspace.sciqlop")
        assert reloaded.sciqlop_version == "0.12.0"

    def test_sync_failure_is_never_swallowed_even_if_a_venv_already_exists(self, workspace_dir, patches):
        """apply_core_version must call prepare_workspace in strict mode --
        the ordinary launcher-startup tolerance for an offline sync failure
        (keep whatever's already installed, report success) would silently
        lie about a user-requested version change."""
        from SciQLop.components.workspaces.backend.workspace_setup import apply_core_version

        self._make_existing_workspace(workspace_dir)
        patches["venv"].has_sciqlop_installed = True
        patches["venv"].sync.side_effect = RuntimeError("offline")

        with pytest.raises(RuntimeError, match="offline"):
            apply_core_version(workspace_dir, "0.13.0")

    def test_missing_manifest_raises_file_not_found(self, tmp_path, patches):
        from SciQLop.components.workspaces.backend.workspace_setup import apply_core_version

        empty_dir = tmp_path / "no_manifest_here"
        empty_dir.mkdir()

        with pytest.raises(FileNotFoundError):
            apply_core_version(empty_dir, "0.13.0")

    def test_concurrent_call_for_the_same_workspace_raises_lock_error(self, workspace_dir, patches):
        from SciQLop.components.workspaces.backend.workspace_setup import apply_core_version

        self._make_existing_workspace(workspace_dir)

        with workspace_lock(workspace_dir):
            with pytest.raises(WorkspaceLockError):
                apply_core_version(workspace_dir, "0.13.0")

        # The lock was held by the test itself, not by apply_core_version,
        # so no sync should have been attempted.
        patches["venv"].sync.assert_not_called()

    def test_manifest_save_failure_after_a_successful_sync_is_a_distinct_error(
        self, workspace_dir, patches, monkeypatch
    ):
        """The venv was actually updated at this point -- this must not look
        like an ordinary sync failure (which the manifest-unchanged test
        above covers), since here the manifest is the thing left behind.

        _make_existing_workspace's own save() call happens before the
        monkeypatch below is applied, so the only save() call that runs
        through flaky_save is apply_core_version's final, post-sync one."""
        from SciQLop.components.workspaces.backend.workspace_setup import apply_core_version
        from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest as WM

        self._make_existing_workspace(workspace_dir)

        def flaky_save(self, path):
            raise OSError("No space left on device")

        monkeypatch.setattr(WM, "save", flaky_save)

        with pytest.raises(RuntimeError, match="recording it in the workspace manifest failed"):
            apply_core_version(workspace_dir, "0.13.0")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_workspace_setup.py::TestApplyCoreVersion -v`
Expected: FAIL with `ImportError: cannot import name 'apply_core_version'`

- [ ] **Step 3: Implement `apply_core_version()`**

In `SciQLop/components/workspaces/backend/workspace_setup.py`, add to the imports:

```python
from SciQLop.components.workspaces.backend.workspace_lock import workspace_lock
```

Add at the end of the file:

```python
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
        python_path = prepare_workspace(workspace_dir, manifest=manifest, strict=True)
        try:
            manifest.save(manifest_path)
        except Exception as exc:
            raise RuntimeError(
                f"SciQLop {version or 'main'} was installed, but recording it "
                f"in the workspace manifest failed: {exc}"
            ) from exc
    return python_path
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_workspace_setup.py -v`
Expected: PASS (whole file, including all earlier tasks' classes)

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/workspaces/backend/workspace_setup.py tests/test_workspace_setup.py
git commit -m "feat: add apply_core_version() to change a workspace's pinned SciQLop version"
```

---

## Task 6: `WelcomeBackend` slots and signals

**Files:**
- Modify: `SciQLop/components/welcome/backend.py:48-60,97-106,375-384`
- Test: `tests/test_welcome_core_version.py`

**Interfaces:**
- Consumes: `fetch_available_versions`, `validate_core_version` from Task 3; `apply_core_version` from Task 5; `error_detail` from Task 1.
- Produces: two new `Signal(str)`s — `core_versions_ready`, `core_update_finished` — and two new `@Slot`s — `fetch_available_core_versions(self, workspace_dir: str) -> None`, `apply_core_version(self, workspace_dir: str, version: str) -> None` — on `WelcomeBackend`. Also `_workspace_to_dict()` gains a `"sciqlop_version"` key. Used by Task 7's welcome.js.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_welcome_core_version.py`:

```python
"""Tests for WelcomeBackend's SciQLop-core-version slots and signals."""

import json
from unittest.mock import patch

import pytest
from PySide6.QtCore import QObject

from SciQLop.components.welcome.backend import WelcomeBackend, _workspace_to_dict
from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest

WORKSPACE_PROJECT_MODULE = "SciQLop.components.workspaces.backend.workspace_project"
WORKSPACE_SETUP_MODULE = "SciQLop.components.workspaces.backend.workspace_setup"


def _make_backend():
    """A WelcomeBackend built without running its heavy __init__.

    WelcomeBackend.__init__ wires QFileSystemWatcher against the real
    workspaces/templates directories and touches sciqlop_app() -- none of
    which the two new slots under test need. Mirrors the same
    __new__-then-init-the-base-class trick tests/test_workspace_add_packages.py
    uses for Workspace.
    """
    backend = WelcomeBackend.__new__(WelcomeBackend)
    QObject.__init__(backend)
    return backend


def _make_manifest(tmp_path, **kwargs):
    manifest = WorkspaceManifest(name="T", **kwargs)
    manifest.save(tmp_path / "workspace.sciqlop")
    return manifest


class TestWorkspaceToDictExposesCoreVersion:
    def test_includes_sciqlop_version(self, tmp_path):
        manifest = _make_manifest(tmp_path, sciqlop_version="0.13.0")
        assert _workspace_to_dict(manifest)["sciqlop_version"] == "0.13.0"

    def test_empty_when_tracking_main(self, tmp_path):
        manifest = _make_manifest(tmp_path)
        assert _workspace_to_dict(manifest)["sciqlop_version"] == ""


class TestFetchAvailableCoreVersionsSlot:
    def test_emits_versions_and_echoes_directory(self, qtbot, tmp_path):
        backend = _make_backend()
        with patch(f"{WORKSPACE_PROJECT_MODULE}.fetch_available_versions", return_value=["0.13.0", "0.12.0"]):
            with qtbot.waitSignal(backend.core_versions_ready, timeout=2000) as blocker:
                backend.fetch_available_core_versions(str(tmp_path))
        payload = json.loads(blocker.args[0])
        assert payload == {"ok": True, "dir": str(tmp_path), "versions": ["0.13.0", "0.12.0"]}

    def test_reports_not_ok_on_empty_list(self, qtbot, tmp_path):
        backend = _make_backend()
        with patch(f"{WORKSPACE_PROJECT_MODULE}.fetch_available_versions", return_value=[]):
            with qtbot.waitSignal(backend.core_versions_ready, timeout=2000) as blocker:
                backend.fetch_available_core_versions(str(tmp_path))
        payload = json.loads(blocker.args[0])
        assert payload["ok"] is False


class TestApplyCoreVersionSlot:
    def test_success_emits_ok_with_version_and_dir(self, qtbot, tmp_path):
        backend = _make_backend()
        with (
            patch(f"{WORKSPACE_PROJECT_MODULE}.fetch_available_versions", return_value=["0.13.0"]),
            patch(f"{WORKSPACE_PROJECT_MODULE}.validate_core_version", return_value=True),
            patch(f"{WORKSPACE_SETUP_MODULE}.apply_core_version", return_value=tmp_path / "python"),
        ):
            with qtbot.waitSignal(backend.core_update_finished, timeout=2000) as blocker:
                backend.apply_core_version(str(tmp_path), "0.13.0")
        payload = json.loads(blocker.args[0])
        assert payload["ok"] is True
        assert payload["dir"] == str(tmp_path)
        assert payload["version"] == "0.13.0"

    def test_invalid_version_never_calls_apply_and_reports_error(self, qtbot, tmp_path):
        backend = _make_backend()
        with (
            patch(f"{WORKSPACE_PROJECT_MODULE}.fetch_available_versions", return_value=["0.13.0"]),
            patch(f"{WORKSPACE_PROJECT_MODULE}.validate_core_version", return_value=False),
            patch(f"{WORKSPACE_SETUP_MODULE}.apply_core_version") as mock_apply,
        ):
            with qtbot.waitSignal(backend.core_update_finished, timeout=2000) as blocker:
                backend.apply_core_version(str(tmp_path), "'; rm -rf /")
            mock_apply.assert_not_called()
        payload = json.loads(blocker.args[0])
        assert payload["ok"] is False

    def test_sync_failure_reports_error_detail(self, qtbot, tmp_path):
        backend = _make_backend()
        exc = RuntimeError("uv sync failed")
        with (
            patch(f"{WORKSPACE_PROJECT_MODULE}.fetch_available_versions", return_value=["0.13.0"]),
            patch(f"{WORKSPACE_PROJECT_MODULE}.validate_core_version", return_value=True),
            patch(f"{WORKSPACE_SETUP_MODULE}.apply_core_version", side_effect=exc),
        ):
            with qtbot.waitSignal(backend.core_update_finished, timeout=2000) as blocker:
                backend.apply_core_version(str(tmp_path), "0.13.0")
        payload = json.loads(blocker.args[0])
        assert payload["ok"] is False
        assert "uv sync failed" in payload["error"]

    def test_active_workspace_flag_reflects_env_var(self, qtbot, tmp_path, monkeypatch):
        monkeypatch.setenv("SCIQLOP_WORKSPACE_DIR", str(tmp_path))
        backend = _make_backend()
        with (
            patch(f"{WORKSPACE_PROJECT_MODULE}.fetch_available_versions", return_value=["0.13.0"]),
            patch(f"{WORKSPACE_PROJECT_MODULE}.validate_core_version", return_value=True),
            patch(f"{WORKSPACE_SETUP_MODULE}.apply_core_version", return_value=tmp_path / "python"),
        ):
            with qtbot.waitSignal(backend.core_update_finished, timeout=2000) as blocker:
                backend.apply_core_version(str(tmp_path), "0.13.0")
        payload = json.loads(blocker.args[0])
        assert payload["is_active_workspace"] is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_welcome_core_version.py -v`
Expected: FAIL — `KeyError: 'sciqlop_version'` for the first class, `AttributeError: 'WelcomeBackend' object has no attribute 'core_versions_ready'` for the rest

- [ ] **Step 3: Implement in `welcome/backend.py`**

Add `"sciqlop_version": ws.sciqlop_version,` to `_workspace_to_dict()`'s returned dict (after `"requires": ws.requires,`):

```python
def _workspace_to_dict(ws: WorkspaceManifest) -> dict:
    ws_dir = ws.directory
    image_path = os.path.join(ws_dir, ws.image) if ws.image else ""
    return {
        "name": ws.name,
        "directory": ws_dir,
        "description": ws.description,
        "last_used": WorkspaceManifest.last_used(ws_dir),
        "last_modified": WorkspaceManifest.last_modified(ws_dir),
        "image": image_path if image_path and os.path.exists(image_path) else "",
        "is_default": ws.default,
        "requires": ws.requires,
        "sciqlop_version": ws.sciqlop_version,
    }
```

Add the two new signals to the class body, after `dependency_install_finished = Signal(str)`:

```python
    core_versions_ready = Signal(str)
    core_update_finished = Signal(str)
```

Add the two new slots after `remove_dependency_from_workspace`:

```python
    @Slot(str)
    def fetch_available_core_versions(self, workspace_dir: str) -> None:
        from SciQLop.components.workspaces.backend.workspace_project import fetch_available_versions

        def _fetch():
            versions = fetch_available_versions()
            self.core_versions_ready.emit(json.dumps({
                "ok": bool(versions),
                "dir": workspace_dir,
                "versions": versions,
            }))

        threading.Thread(target=_fetch, daemon=True).start()

    @Slot(str, str)
    def apply_core_version(self, workspace_dir: str, version: str) -> None:
        from SciQLop.components.workspaces.backend.uv import error_detail
        from SciQLop.components.workspaces.backend.workspace_project import (
            fetch_available_versions, validate_core_version,
        )
        from SciQLop.components.workspaces.backend.workspace_setup import (
            apply_core_version as _apply_core_version,
        )

        active_dir = os.environ.get("SCIQLOP_WORKSPACE_DIR", "")
        is_active = os.path.realpath(workspace_dir) == os.path.realpath(active_dir)

        def _install():
            available = fetch_available_versions()
            if not validate_core_version(version, available):
                self.core_update_finished.emit(json.dumps({
                    "ok": False, "dir": workspace_dir, "version": version,
                    "error": f"{version!r} is not an installable SciQLop version",
                }))
                return
            try:
                _apply_core_version(workspace_dir, version)
            except Exception as e:
                log.error(f"Failed to update SciQLop core version: {e}")
                self.core_update_finished.emit(json.dumps({
                    "ok": False, "dir": workspace_dir, "version": version,
                    "error": error_detail(e),
                }))
                return
            self.core_update_finished.emit(json.dumps({
                "ok": True, "dir": workspace_dir, "version": version,
                "is_active_workspace": is_active,
            }))

        threading.Thread(target=_install, daemon=True).start()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_welcome_core_version.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Run the full backend test suite to check for regressions**

Run: `uv run pytest tests/test_welcome_backend.py tests/test_appstore_install.py tests/test_workspace_setup.py tests/test_workspace_project.py tests/test_uv_resolution.py tests/test_workspace_lock.py tests/test_welcome_core_version.py -v`
Expected: PASS, no failures

- [ ] **Step 6: Commit**

```bash
git add SciQLop/components/welcome/backend.py tests/test_welcome_core_version.py
git commit -m "feat: add WelcomeBackend slots for fetching and applying a workspace's SciQLop version"
```

---

## Task 7: "SciQLop Core" UI in the welcome pane

**Files:**
- Modify: `SciQLop/components/welcome/resources/welcome.js:9-37,433-474`
- Modify: `SciQLop/components/welcome/resources/welcome.css` (append near the existing `.pkg-*` rules, after line 749)

**Interfaces:**
- Consumes: `backend.core_versions_ready` / `backend.core_update_finished` signals and `backend.fetch_available_core_versions(dir)` / `backend.apply_core_version(dir, version)` slots from Task 6. `ws.sciqlop_version` field from Task 6's `_workspace_to_dict()`.
- Produces: nothing consumed by other tasks — this is the leaf UI task.

There is no JS test harness in this repository (no `package.json`/Jest/etc.) — this task is verified manually per Step 4 below rather than with an automated test.

- [ ] **Step 1: Wire the two new signals in `init()`**

In `SciQLop/components/welcome/resources/welcome.js`, inside `init()`, add two lines next to the existing `backend.dependency_install_finished.connect(onDependencyInstallFinished);`:

```javascript
        backend.dependency_install_finished.connect(onDependencyInstallFinished);
        backend.core_versions_ready.connect(onCoreVersionsReady);
        backend.core_update_finished.connect(onCoreUpdateFinished);
```

- [ ] **Step 2: Add the "SciQLop Core" section to the details panel**

In `showWorkspaceDetails()`, add a new `details-section` between the Description field and the Packages section:

```javascript
    var pkgHtml = buildPackageList(ws, isActive, true);
    var coreVersionHtml = buildCoreVersionSection(ws);

    content.innerHTML =
        '<div class="details-field"><label>Name</label>' + nameHtml + '</div>' +
        '<div class="details-field"><label>Last used</label><span>' + escapeHtml(ws.last_used) + '</span></div>' +
        '<div class="details-field"><label>Last modified</label><span>' + escapeHtml(ws.last_modified) + '</span></div>' +
        '<div class="details-field"><label>Description</label>' + descHtml + '</div>' +
        '<div class="details-section"><label>SciQLop Core</label>' + coreVersionHtml + '</div>' +
        '<div class="details-section"><label>Packages</label>' + pkgHtml + '</div>' +
        '<div class="details-actions">' +
            (isActive ? '' : '<button class="primary" onclick="tryOpenWorkspace(\'' + escapeAttr(ws.directory) + '\')">Open workspace</button>') +
            '<div class="details-actions-row">' +
                '<button class="secondary" onclick="backend.duplicate_workspace(\'' + escapeAttr(ws.directory) + '\')">Clone</button>' +
                (ws.is_default || isActive ? '' :
                    '<button class="secondary danger" onclick="confirmDelete(\'' + escapeAttr(ws.directory) + '\', \'' + escapeAttr(ws.name) + '\')">Delete</button>') +
            '</div>' +
        '</div>';
```

(this replaces the existing `content.innerHTML = ...` assignment — only the new `coreVersionHtml` line is inserted, everything else is unchanged)

- [ ] **Step 3: Implement the new JS functions**

Add these functions right before `buildPackageList` in `welcome.js`:

```javascript
function buildCoreVersionSection(ws) {
    var current = ws.sciqlop_version || "";
    var currentLabel = current ? current : "main (development)";
    var html = '<div class="core-version-current">Current: <strong>' +
        escapeHtml(currentLabel) + '</strong></div>';
    html += '<select id="core-version-select" class="core-version-select">' +
        '<option value="' + escapeAttr(current) + '">' + escapeHtml(currentLabel) +
        ' (loading…)</option></select>';
    html += '<button id="core-version-install-btn" class="secondary">Install</button>';
    html += '<div id="core-version-status" class="core-version-status"></div>';

    setTimeout(function() {
        backend.fetch_available_core_versions(ws.directory);
        var btn = document.getElementById("core-version-install-btn");
        if (btn) {
            btn.addEventListener("click", function() {
                doCoreVersionInstall(ws.directory);
            });
        }
    }, 0);

    return html;
}

function onCoreVersionsReady(resultJson) {
    var result = JSON.parse(resultJson);
    if (_currentDetailsWs && _currentDetailsWs.directory === result.dir) {
        populateCoreVersionSelect(result);
    }
}

function populateCoreVersionSelect(result) {
    var select = document.getElementById("core-version-select");
    if (!select) return;
    var current = (_currentDetailsWs && _currentDetailsWs.sciqlop_version) || "";

    var options = result.ok ? result.versions.slice() : (current ? [current] : []);
    if (current && options.indexOf(current) === -1) {
        options.unshift(current);
    }

    select.innerHTML = "";
    options.forEach(function(v) {
        var opt = document.createElement("option");
        opt.value = v;
        opt.textContent = v;
        select.appendChild(opt);
    });
    var mainOpt = document.createElement("option");
    mainOpt.value = "";
    mainOpt.textContent = "main (development)";
    select.appendChild(mainOpt);
    select.value = current;

    var status = document.getElementById("core-version-status");
    if (status && !result.ok) {
        status.textContent = "Could not fetch the release list — showing the current pin only.";
        status.className = "core-version-status core-version-error";
    }
}

function doCoreVersionInstall(dir) {
    var select = document.getElementById("core-version-select");
    var btn = document.getElementById("core-version-install-btn");
    var status = document.getElementById("core-version-status");
    if (!select || !btn) return;
    var version = select.value;
    btn.disabled = true;
    select.disabled = true;
    if (status) {
        status.textContent = "Installing…";
        status.className = "core-version-status";
    }
    backend.apply_core_version(dir, version);
}

function onCoreUpdateFinished(resultJson) {
    var result = JSON.parse(resultJson);
    var isCurrentPanel = _currentDetailsWs && _currentDetailsWs.directory === result.dir;

    var select = document.getElementById("core-version-select");
    var btn = document.getElementById("core-version-install-btn");
    if (isCurrentPanel && select) select.disabled = false;
    if (isCurrentPanel && btn) btn.disabled = false;

    if (!isCurrentPanel) return;
    var status = document.getElementById("core-version-status");
    if (!status) return;

    if (result.ok) {
        _currentDetailsWs.sciqlop_version = result.version;
        var label = document.querySelector(".core-version-current");
        if (label) {
            label.innerHTML = "Current: <strong>" +
                escapeHtml(result.version || "main (development)") + "</strong>";
        }
        status.textContent = result.is_active_workspace
            ? "Installed — restart SciQLop to apply."
            : "Installed.";
        status.className = "core-version-status core-version-success";
    } else {
        status.textContent = "Update failed: " + (result.error || "unknown error");
        status.className = "core-version-status core-version-error";
    }
}
```

- [ ] **Step 4: Add CSS for the new section**

Append to `SciQLop/components/welcome/resources/welcome.css`, after the existing `.pkg-add-row button:hover` rule (around line 749):

```css
.core-version-current {
    font-size: 0.9em;
    margin-bottom: 6px;
}

.core-version-select {
    width: 100%;
    padding: 4px 8px;
    border: 1px solid var(--Borders);
    border-radius: 4px;
    background: var(--Base);
    color: var(--Text);
    font-size: 0.9em;
    margin-bottom: 6px;
}

.core-version-status {
    font-size: 0.85em;
    margin-top: 6px;
    color: var(--UnselectedText);
}

.core-version-success {
    color: #27ae60;
}

.core-version-error {
    color: #c0392b;
}
```

- [ ] **Step 5: Manual verification**

No JS test harness exists in this repo, so verify by hand:

1. Run: `uv run sciqlop`
2. From the welcome page, click "New workspace" to create a throwaway workspace (do not use your main one — the Install step below runs a real `uv sync`, which can take a minute the first time).
3. Click the new workspace's card to open its details panel.
4. Confirm a "SciQLop Core" section appears above "Packages", showing "Current: main (development)" (a freshly created workspace with no dev-build ancestry has no pin) and a dropdown that briefly says "(loading…)" then populates with real PyPI release numbers plus a "main (development)" entry.
5. Pick a different entry (or leave the default) and click "Install". Confirm the button and dropdown disable, then re-enable with either "Installed." or "Installed — restart SciQLop to apply." (the latter only if this happens to be the active workspace).
6. Disconnect from the network and repeat steps 3-4 on another new workspace to confirm the dropdown falls back to showing just the current pin with a "Could not fetch the release list" message, instead of an empty or broken dropdown.
7. Delete the throwaway workspace(s) created for this test via the Delete button in the details panel.

- [ ] **Step 6: Commit**

```bash
git add SciQLop/components/welcome/resources/welcome.js SciQLop/components/welcome/resources/welcome.css
git commit -m "feat: add SciQLop Core version picker to the workspace details panel"
```
