# Core Package Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Slim down `SciQLop/core/` by deleting unused modules and moving workspace/plugin infrastructure into their natural component homes.

**Architecture:** Move workspace files into `components/workspaces/backend/`, `plugin_deps` into `components/plugins/`, `examples/` into `components/workspaces/backend/`, delete unused modules, fix broken `core.icons` imports. All moves require updating import paths in source and tests.

**Tech Stack:** Python, git

---

### Task 1: Delete unused modules

**Files:**
- Delete: `SciQLop/core/check_for_updates.py`
- Delete: `SciQLop/core/common/pip_process.py`
- Delete: `SciQLop/core/common/process.py`
- Delete: `SciQLop/core/ui/drag_and_drop/__init__.py`
- Delete: `SciQLop/core/ui/drag_and_drop/drop_handler.py`
- Delete: `SciQLop/core/ui/drag_and_drop/helper.py`
- Delete: `SciQLop/core/ui/drag_and_drop/placeholder.py`
- Delete: `SciQLop/core/ui/drag_and_drop/place_holder_manager.py`

**Step 1: Delete the files**

```bash
git rm SciQLop/core/check_for_updates.py \
       SciQLop/core/common/pip_process.py \
       SciQLop/core/common/process.py \
       SciQLop/core/ui/drag_and_drop/__init__.py \
       SciQLop/core/ui/drag_and_drop/drop_handler.py \
       SciQLop/core/ui/drag_and_drop/helper.py \
       SciQLop/core/ui/drag_and_drop/placeholder.py \
       SciQLop/core/ui/drag_and_drop/place_holder_manager.py
rmdir SciQLop/core/ui/drag_and_drop
```

**Step 2: Run tests**

```bash
uv run pytest --co -q
```

Expected: all tests collect without import errors.

**Step 3: Commit**

```bash
git commit -m "refactor(core): delete unused modules (check_for_updates, pip_process, process, drag_and_drop)"
```

---

### Task 2: Fix broken `SciQLop.core.icons` imports

**Files:**
- Modify: `SciQLop/components/plotting/ui/mpl_panel.py:7`
- Modify: `SciQLop/components/plotting/backend/easy_provider.py:14`

**Step 1: Update imports**

In both files, replace:
```python
from SciQLop.core.icons import register_icon
```
with:
```python
from SciQLop.components.theming import register_icon
```

**Step 2: Run tests**

```bash
uv run pytest --co -q
```

**Step 3: Commit**

```bash
git commit -m "fix(plotting): use correct import path for register_icon (theming, not core.icons)"
```

---

### Task 3: Move `plugin_deps.py` into `components/plugins/`

**Files:**
- Move: `SciQLop/core/plugin_deps.py` → `SciQLop/components/plugins/plugin_deps.py`
- Modify: `SciQLop/sciqlop_launcher.py` (line ~103)
- Modify: `SciQLop/core/workspace_setup.py` (line ~15) — will move again in Task 4, but fix now for test sanity
- Modify: `tests/test_plugin_deps.py` (line ~6)

**Step 1: Move the file**

```bash
git mv SciQLop/core/plugin_deps.py SciQLop/components/plugins/plugin_deps.py
```

**Step 2: Update all imports**

In each file listed above, replace:
```python
from SciQLop.core.plugin_deps import collect_plugin_dependencies
```
with:
```python
from SciQLop.components.plugins.plugin_deps import collect_plugin_dependencies
```

**Step 3: Run tests**

```bash
uv run pytest tests/test_plugin_deps.py -v
```

Expected: PASS

**Step 4: Commit**

```bash
git commit -m "refactor(plugins): move plugin_deps from core/ to components/plugins/"
```

---

### Task 4: Move workspace modules into `components/workspaces/backend/`

This is the largest task. Six `workspace_*.py` files + `common/uv.py` + `examples/` all move into `components/workspaces/backend/`.

**Files to move:**
- `SciQLop/core/workspace_manifest.py` → `SciQLop/components/workspaces/backend/workspace_manifest.py`
- `SciQLop/core/workspace_project.py` → `SciQLop/components/workspaces/backend/workspace_project.py`
- `SciQLop/core/workspace_venv.py` → `SciQLop/components/workspaces/backend/workspace_venv.py`
- `SciQLop/core/workspace_migration.py` → `SciQLop/components/workspaces/backend/workspace_migration.py`
- `SciQLop/core/workspace_setup.py` → `SciQLop/components/workspaces/backend/workspace_setup.py`
- `SciQLop/core/workspace_archive.py` → `SciQLop/components/workspaces/backend/workspace_archive.py`
- `SciQLop/core/common/uv.py` → `SciQLop/components/workspaces/backend/uv.py`
- `SciQLop/core/examples/example.py` → `SciQLop/components/workspaces/backend/example.py`
- Delete: `SciQLop/core/examples/__init__.py` (was just re-exporting)
- Delete: `SciQLop/core/examples/` directory

**Step 1: Move all files**

```bash
git mv SciQLop/core/workspace_manifest.py SciQLop/components/workspaces/backend/
git mv SciQLop/core/workspace_project.py SciQLop/components/workspaces/backend/
git mv SciQLop/core/workspace_venv.py SciQLop/components/workspaces/backend/
git mv SciQLop/core/workspace_migration.py SciQLop/components/workspaces/backend/
git mv SciQLop/core/workspace_setup.py SciQLop/components/workspaces/backend/
git mv SciQLop/core/workspace_archive.py SciQLop/components/workspaces/backend/
git mv SciQLop/core/common/uv.py SciQLop/components/workspaces/backend/
git mv SciQLop/core/examples/example.py SciQLop/components/workspaces/backend/
git rm SciQLop/core/examples/__init__.py
rmdir SciQLop/core/examples
```

**Step 2: Update internal imports within moved files**

The moved files import each other. Update all cross-references from `SciQLop.core.*` to `SciQLop.components.workspaces.backend.*`:

`workspace_setup.py`:
```python
# Old:
from SciQLop.components.plugins.plugin_deps import collect_plugin_dependencies  # already updated in Task 3
from SciQLop.core.workspace_manifest import WorkspaceManifest
from SciQLop.core.workspace_migration import migrate_workspace
from SciQLop.core.workspace_project import generate_pyproject_toml
from SciQLop.core.workspace_venv import WorkspaceVenv
# New:
from SciQLop.components.plugins.plugin_deps import collect_plugin_dependencies
from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest
from SciQLop.components.workspaces.backend.workspace_migration import migrate_workspace
from SciQLop.components.workspaces.backend.workspace_project import generate_pyproject_toml
from SciQLop.components.workspaces.backend.workspace_venv import WorkspaceVenv
```

`workspace_migration.py`:
```python
# Old:
from SciQLop.core.workspace_manifest import WorkspaceManifest
# New:
from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest
```

`workspace_project.py`:
```python
# Old:
from SciQLop.core.workspace_manifest import WorkspaceManifest
# New:
from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest
```

`workspace_venv.py`:
```python
# Old:
from SciQLop.core.common.uv import uv_command
# New:
from SciQLop.components.workspaces.backend.uv import uv_command
```

**Step 3: Update imports in the launcher**

`SciQLop/sciqlop_launcher.py` has several import locations. Replace all `SciQLop.core.workspace_*` and `SciQLop.core.common.uv` imports:

```python
# Old:
from SciQLop.core.workspace_migration import migrate_workspace
from SciQLop.core.workspace_manifest import WorkspaceManifest
from SciQLop.core.workspace_setup import get_globally_enabled_plugins, get_plugin_folders
from SciQLop.core.workspace_setup import prepare_workspace
from SciQLop.core.workspace_archive import import_workspace
from SciQLop.core.workspace_archive import export_workspace
from SciQLop.core.common.uv import uv_command

# New (same names, new paths):
from SciQLop.components.workspaces.backend.workspace_migration import migrate_workspace
from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest
from SciQLop.components.workspaces.backend.workspace_setup import get_globally_enabled_plugins, get_plugin_folders
from SciQLop.components.workspaces.backend.workspace_setup import prepare_workspace
from SciQLop.components.workspaces.backend.workspace_archive import import_workspace
from SciQLop.components.workspaces.backend.workspace_archive import export_workspace
from SciQLop.components.workspaces.backend.uv import uv_command
```

**Step 4: Update imports in components**

`SciQLop/components/welcome/sections/ExamplesView.py`:
```python
# Old:
from SciQLop.core.examples.example import Example
# New:
from SciQLop.components.workspaces.backend.example import Example
```

`SciQLop/components/workspaces/backend/workspaces_manager.py`:
```python
# Old:
from SciQLop.core.examples import Example
# New:
from SciQLop.components.workspaces.backend.example import Example
```

**Step 5: Update imports in tests**

All test files referencing `SciQLop.core.workspace_*`, `SciQLop.core.common.uv`, or `SciQLop.core.examples`:

- `tests/test_workspace_manifest.py`: `SciQLop.core.workspace_manifest` → `SciQLop.components.workspaces.backend.workspace_manifest`
- `tests/test_workspace_project.py`: same pattern for `workspace_project` and `workspace_manifest`
- `tests/test_workspace_setup.py`: same pattern for `workspace_setup` and `workspace_manifest`
- `tests/test_workspace_migration.py`: same pattern for `workspace_migration` and `workspace_manifest`
- `tests/test_workspace_venv.py`: same pattern for `workspace_venv`
- `tests/test_workspace_archive.py`: same pattern for `workspace_archive`
- `tests/test_launcher.py`: same pattern for `workspace_manifest` and `workspace_archive`
- `tests/test_uv_resolution.py`: `SciQLop.core.common.uv` → `SciQLop.components.workspaces.backend.uv`

**Step 6: Run all tests**

```bash
uv run pytest -v
```

Expected: all tests pass.

**Step 7: Commit**

```bash
git commit -m "refactor(workspaces): move workspace infrastructure and examples from core/ to components/workspaces/backend/"
```

---

### Task 5: Update CLAUDE.md architecture docs

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Update the architecture section**

Remove references to workspace files in `core/`. Update `components/workspaces/` description to mention the new backend modules. Remove `examples/` from the `core/` description if mentioned.

**Step 2: Commit**

```bash
git commit -m "docs: update CLAUDE.md architecture after core/ cleanup"
```

---

### Final state of `core/`

After all tasks, `core/` will contain only shared infrastructure:

```
SciQLop/core/
├── __init__.py              # re-exports (TimeRange, make_utc_datetime, etc.)
├── sciqlop_application.py   # QApplication subclass
├── enums.py                 # shared enums
├── models.py                # shared data models
├── property.py              # Qt property helper
├── unique_names.py          # name generation
├── common/
│   ├── __init__.py          # utility re-exports
│   ├── dataclasses.py
│   ├── ExtraColumnsProxyModel.py
│   ├── python.py
│   ├── signal_rate_limiter.py
│   └── terminal_messages.py
├── data_models/
│   ├── __init__.py
│   ├── models.py
│   └── serialisation.py
├── mime/
│   ├── __init__.py
│   └── types.py
└── ui/
    ├── __init__.py
    ├── datetime_range.py
    ├── flow_layout.py
    ├── mainwindow.py
    └── tree_view.py
```
