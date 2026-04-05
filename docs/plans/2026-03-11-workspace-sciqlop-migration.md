# Migrate workspace metadata from workspace.json to workspace.sciqlop

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `WorkspaceSpecFile` (JSON) with `WorkspaceManifest` (TOML) as the single source of workspace metadata, using filesystem timestamps for last-used/last-modified.

**Architecture:** Extend `WorkspaceManifest` with `image` and `default` fields. Add a `.last_used` marker file (touched on workspace load) and read `workspace.sciqlop` mtime for last-modified. Update all consumers to use `WorkspaceManifest` instead of `WorkspaceSpecFile`. Remove `WorkspaceSpec`/`WorkspaceSpecFile` after migration.

**Tech Stack:** Python dataclasses, tomllib/tomli_w (TOML), PySide6, pytest

**Design doc:** `docs/plans/2026-03-05-uv-environment-management-design.md`

---

## File structure

| File | Action | Responsibility |
|------|--------|---------------|
| `SciQLop/components/workspaces/backend/workspace_manifest.py` | Modify | Add `image`, `default` fields; add `directory` property; add timestamp helpers |
| `SciQLop/components/workspaces/backend/workspaces_manager.py` | Modify | Replace all `WorkspaceSpecFile` usage with `WorkspaceManifest` |
| `SciQLop/components/workspaces/backend/workspace.py` | Modify | Use `WorkspaceManifest` instead of `WorkspaceSpecFile` |
| `SciQLop/components/workspaces/backend/workspace_migration.py` | Modify | Carry over `image` and `default_workspace` fields |
| `SciQLop/components/welcome/backend.py` | Modify | Use `WorkspaceManifest` for workspace data |
| `SciQLop/components/workspaces/__init__.py` | Modify | Update re-exports |
| `SciQLop/core/data_models/models.py` | Modify | Remove `WorkspaceSpec`, `WorkspaceSpecFile`, `WorkspaceSpecROFile` |
| `SciQLop/components/welcome/welcome_page.py` | Delete | Dead code — replaced by `web_welcome_page.py` |
| `SciQLop/components/welcome/sections/recent_workspaces.py` | Delete | Dead code — only imported by old `welcome_page.py` |
| `tests/test_workspace_manifest.py` | Modify | Test new fields and timestamp helpers |
| `tests/test_workspace_migration.py` | Modify | Test image/default field migration |
| `tests/test_add_example_to_workspace.py` | Modify | Use `workspace.sciqlop` instead of `workspace.json` |

### Notes on intentional removals

- **`notebooks` field**: Dropped. The old auto-start-JupyterLab-on-workspace-load behavior (checking `workspace_spec.notebooks`) is removed. JupyterLab is started explicitly by the user via quickstart shortcut. The design doc defers notebook management: "Notebook list management in workspace manifest (deferred)."
- **`python_path` field**: Dropped. Legacy `sys.path` manipulation is superseded by workspace venvs.
- **`dependencies_installed` and `kernel_started` signals** on `Workspace`: Dropped — declared but never connected anywhere.
- **`workspace_spec()` static method** on `WorkspaceManager`: Dropped — never called.

---

## Chunk 1: Extend WorkspaceManifest

### Task 1: Add image, default, and directory to WorkspaceManifest

**Files:**
- Modify: `SciQLop/components/workspaces/backend/workspace_manifest.py`
- Test: `tests/test_workspace_manifest.py`

- [ ] **Step 1: Write failing tests for new fields**

```python
# tests/test_workspace_manifest.py — add these tests

def test_roundtrip_with_image_and_default(tmp_path):
    m = WorkspaceManifest(name="Study", image="image.png", default=True)
    m.save(tmp_path / "workspace.sciqlop")
    loaded = WorkspaceManifest.load(tmp_path / "workspace.sciqlop")
    assert loaded.name == "Study"
    assert loaded.image == "image.png"
    assert loaded.default is True


def test_load_without_image_defaults_empty(tmp_path):
    WorkspaceManifest(name="Bare").save(tmp_path / "workspace.sciqlop")
    loaded = WorkspaceManifest.load(tmp_path / "workspace.sciqlop")
    assert loaded.image == ""
    assert loaded.default is False


def test_directory_set_on_load(tmp_path):
    WorkspaceManifest(name="X").save(tmp_path / "workspace.sciqlop")
    loaded = WorkspaceManifest.load(tmp_path / "workspace.sciqlop")
    assert loaded.directory == str(tmp_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_workspace_manifest.py -v`
Expected: FAIL — `image` and `default` not recognized, `directory` attribute missing

- [ ] **Step 3: Implement new fields in WorkspaceManifest**

Update `SciQLop/components/workspaces/backend/workspace_manifest.py`:

```python
@dataclass
class WorkspaceManifest:
    name: str
    description: str = ""
    image: str = ""
    default: bool = False
    plugins_add: list[str] = field(default_factory=list)
    plugins_remove: list[str] = field(default_factory=list)
    requires: list[str] = field(default_factory=list)
    _directory: str = field(default="", repr=False, compare=False, init=False)

    @property
    def directory(self) -> str:
        return self._directory

    @classmethod
    def load(cls, path: Path | str) -> WorkspaceManifest:
        path = Path(path)
        with open(path, "rb") as f:
            data = tomllib.load(f)
        workspace = data.get("workspace", {})
        plugins = data.get("plugins", {})
        dependencies = data.get("dependencies", {})
        manifest = cls(
            name=workspace["name"],
            description=workspace.get("description", ""),
            image=workspace.get("image", ""),
            default=workspace.get("default", False),
            plugins_add=plugins.get("add", []),
            plugins_remove=plugins.get("remove", []),
            requires=dependencies.get("requires", []),
        )
        manifest._directory = str(path.parent)
        return manifest

    def save(self, path: Path | str) -> None:
        path = Path(path)
        self._directory = str(path.parent)
        data: dict = {
            "workspace": {
                "name": self.name,
                "description": self.description,
            },
        }
        if self.image:
            data["workspace"]["image"] = self.image
        if self.default:
            data["workspace"]["default"] = self.default
        # ... rest of save unchanged (plugins, dependencies sections)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_workspace_manifest.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/workspaces/backend/workspace_manifest.py tests/test_workspace_manifest.py
git commit -m "feat(workspaces): add image, default, directory to WorkspaceManifest"
```

### Task 2: Add filesystem timestamp helpers

**Files:**
- Modify: `SciQLop/components/workspaces/backend/workspace_manifest.py`
- Test: `tests/test_workspace_manifest.py`

- [ ] **Step 1: Write failing tests for timestamps**

```python
import time

def test_last_modified_from_manifest_mtime(tmp_path):
    m = WorkspaceManifest(name="X")
    m.save(tmp_path / "workspace.sciqlop")
    assert m.last_modified(tmp_path) != ""


def test_last_used_empty_before_touch(tmp_path):
    m = WorkspaceManifest(name="X")
    m.save(tmp_path / "workspace.sciqlop")
    assert m.last_used(tmp_path) == ""


def test_touch_then_read_last_used(tmp_path):
    m = WorkspaceManifest(name="X")
    m.save(tmp_path / "workspace.sciqlop")
    WorkspaceManifest.touch_last_used(tmp_path)
    assert m.last_used(tmp_path) != ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_workspace_manifest.py -v -k "last_"`
Expected: FAIL — methods don't exist

- [ ] **Step 3: Implement timestamp helpers**

Add to `WorkspaceManifest`:

```python
LAST_USED_MARKER = ".last_used"

@staticmethod
def touch_last_used(workspace_dir: Path | str) -> None:
    (Path(workspace_dir) / LAST_USED_MARKER).touch()

@staticmethod
def last_used(workspace_dir: Path | str) -> str:
    marker = Path(workspace_dir) / LAST_USED_MARKER
    if marker.exists():
        return datetime.fromtimestamp(marker.stat().st_mtime).isoformat()
    return ""

@staticmethod
def last_modified(workspace_dir: Path | str) -> str:
    manifest = Path(workspace_dir) / "workspace.sciqlop"
    if manifest.exists():
        return datetime.fromtimestamp(manifest.stat().st_mtime).isoformat()
    return ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_workspace_manifest.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/workspaces/backend/workspace_manifest.py tests/test_workspace_manifest.py
git commit -m "feat(workspaces): add filesystem timestamp helpers to WorkspaceManifest"
```

---

## Chunk 2: Update migration and workspace discovery

### Task 3: Update migration to carry over image and default fields

**Files:**
- Modify: `SciQLop/components/workspaces/backend/workspace_migration.py`
- Test: `tests/test_workspace_migration.py`

- [ ] **Step 1: Write failing test for image/default migration**

```python
def test_migrate_carries_image_and_default(tmp_path):
    old_spec = {
        "name": "My Study",
        "description": "desc",
        "dependencies": ["scipy"],
        "image": "image.png",
        "default_workspace": True,
    }
    (tmp_path / "workspace.json").write_text(json.dumps(old_spec))
    migrate_workspace(tmp_path)
    m = WorkspaceManifest.load(tmp_path / "workspace.sciqlop")
    assert m.image == "image.png"
    assert m.default is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_workspace_migration.py::test_migrate_carries_image_and_default -v`
Expected: FAIL — image/default not migrated

- [ ] **Step 3: Update migration to include new fields and touch `.last_used`**

In `workspace_migration.py`, update the `WorkspaceManifest` construction and touch the last-used marker so migrated workspaces don't appear as "never used":

```python
manifest = WorkspaceManifest(
    name=old_data.get("name", workspace_dir.name),
    description=old_data.get("description", ""),
    image=old_data.get("image", ""),
    default=old_data.get("default_workspace", False),
    requires=old_data.get("dependencies", []),
)
manifest.save(manifest_path)

# Preserve last-used state for migrated workspaces
WorkspaceManifest.touch_last_used(workspace_dir)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_workspace_migration.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/workspaces/backend/workspace_migration.py tests/test_workspace_migration.py
git commit -m "feat(workspaces): migrate image and default fields to workspace.sciqlop"
```

### Task 4: Replace WorkspaceSpecFile in workspace discovery and auto-load

**Files:**
- Modify: `SciQLop/components/workspaces/backend/workspaces_manager.py`

- [ ] **Step 1: Update `list_existing_workspaces` to use `workspace.sciqlop`**

Replace the function:

```python
def list_existing_workspaces() -> list[WorkspaceManifest]:
    workspaces_dir = SciQLopWorkspacesSettings().workspaces_dir
    if not os.path.exists(workspaces_dir):
        return []
    results = []
    for entry in os.listdir(workspaces_dir):
        ws_dir = os.path.join(workspaces_dir, entry)
        manifest_path = os.path.join(ws_dir, "workspace.sciqlop")
        if os.path.isdir(ws_dir) and os.path.exists(manifest_path):
            try:
                results.append(WorkspaceManifest.load(manifest_path))
            except Exception as e:
                log.error(f"Error loading workspace {ws_dir}: {e}")
    return results
```

Note: this also fixes the old `d != 'default'` bug (was comparing full path to bare name — always True).

- [ ] **Step 2: Update `_auto_load_workspace` to check `workspace.sciqlop`**

```python
def _auto_load_workspace(self):
    target = os.environ.get("SCIQLOP_WORKSPACE_DIR")
    if not target:
        return
    default_dir = os.path.join(SciQLopWorkspacesSettings().workspaces_dir, "default")
    if os.path.realpath(target) == os.path.realpath(default_dir):
        return
    manifest_path = os.path.join(target, "workspace.sciqlop")
    if os.path.exists(manifest_path):
        log.info(f"Auto-loading workspace: {target}")
        self.load_workspace(WorkspaceManifest.load(manifest_path))
```

- [ ] **Step 3: Run existing tests**

Run: `uv run pytest tests/ -v -k "workspace"`
Expected: Some tests may fail due to downstream `load_workspace` signature changes — that's expected, fixed in Task 5.

- [ ] **Step 4: Commit**

```bash
git add SciQLop/components/workspaces/backend/workspaces_manager.py
git commit -m "refactor(workspaces): use workspace.sciqlop for discovery and auto-load"
```

---

## Chunk 3: Update Workspace class and WorkspaceManager

### Task 5: Update Workspace class to use WorkspaceManifest

**Files:**
- Modify: `SciQLop/components/workspaces/backend/workspace.py`

The `Workspace` class currently wraps `WorkspaceSpecFile`. Update it to wrap `WorkspaceManifest`.

- [ ] **Step 1: Rewrite Workspace to use WorkspaceManifest**

Key changes:
- Constructor accepts `WorkspaceManifest` instead of `WorkspaceSpecFile`
- `name` setter saves manifest to TOML
- `dependencies` reads `manifest.requires`
- Remove `python_path` property and `add_to_python_path` (legacy, per design doc)
- `install_dependency` appends to `manifest.requires` and saves
- Touch `.last_used` on construction

```python
from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest

class Workspace(QObject):
    name_changed = Signal(str)

    def __init__(self, manifest: WorkspaceManifest, parent=None):
        super().__init__(parent)
        self._manifest = manifest
        self._manifest_path = Path(manifest.directory) / "workspace.sciqlop"
        os.chdir(manifest.directory)
        sys.path.insert(0, manifest.directory)
        WorkspaceManifest.touch_last_used(manifest.directory)

    @property
    def workspace_dir(self) -> str:
        return self._manifest.directory

    @property
    def name(self) -> str:
        return self._manifest.name

    @name.setter
    def name(self, value: str):
        self._manifest.name = value
        self._manifest.save(self._manifest_path)
        self.name_changed.emit(value)

    @property
    def dependencies(self) -> list[str]:
        return self._manifest.requires

    def install_dependency(self, dep: str):
        if dep not in self._manifest.requires:
            self._manifest.requires.append(dep)
            self._manifest.save(self._manifest_path)

    def install_dependencies(self, deps: list[str]):
        added = [d for d in deps if d not in self._manifest.requires]
        if added:
            self._manifest.requires.extend(added)
            self._manifest.save(self._manifest_path)

    def add_files(self, files: list[str], destination: str = ""):
        for f in files:
            dest = os.path.join(self.workspace_dir, destination, os.path.basename(f))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(f, dest)

    def add_directory(self, directory: str, destination: str = ""):
        dest = os.path.join(self.workspace_dir, destination)
        shutil.copytree(directory, dest, dirs_exist_ok=True)

    def __str__(self):
        return self.name
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/ -v -k "workspace"`

- [ ] **Step 3: Commit**

```bash
git add SciQLop/components/workspaces/backend/workspace.py
git commit -m "refactor(workspaces): Workspace wraps WorkspaceManifest instead of WorkspaceSpecFile"
```

### Task 6: Update WorkspaceManager to use WorkspaceManifest throughout

**Files:**
- Modify: `SciQLop/components/workspaces/backend/workspaces_manager.py`

- [ ] **Step 1: Update all methods**

Key changes:

`_ensure_default_workspace_exists` — create `workspace.sciqlop` (not `workspace.json`):
```python
def _ensure_default_workspace_exists(self) -> WorkspaceManifest:
    default_dir = os.path.join(SciQLopWorkspacesSettings().workspaces_dir, "default")
    manifest_path = os.path.join(default_dir, "workspace.sciqlop")
    if not os.path.exists(manifest_path):
        os.makedirs(default_dir, exist_ok=True)
        manifest = WorkspaceManifest(name="default", default=True)
        manifest.save(manifest_path)
        dest = os.path.join(default_dir, "image.png")
        QFile.copy(":/splash.png", dest)
        os.chmod(dest, 0o644)
        manifest.image = "image.png"
        manifest.save(manifest_path)
        return WorkspaceManifest.load(manifest_path)
    return WorkspaceManifest.load(manifest_path)
```

`_create_workspace` — create manifest:
```python
@staticmethod
def _create_workspace(name: str, path: str, **kwargs) -> WorkspaceManifest:
    os.makedirs(path, exist_ok=True)
    manifest = WorkspaceManifest(name=name, **kwargs)
    manifest_path = os.path.join(path, "workspace.sciqlop")
    manifest.save(manifest_path)
    dest = os.path.join(path, "image.png")
    if not os.path.exists(dest):
        QFile.copy(":/splash.png", dest)
        os.chmod(dest, 0o644)
        manifest.image = "image.png"
        manifest.save(manifest_path)
    return WorkspaceManifest.load(manifest_path)
```

`load_workspace` — accept `WorkspaceManifest`:
```python
def load_workspace(self, manifest: WorkspaceManifest | None) -> Workspace:
    if self._workspace is not None:
        raise Exception("Workspace already created")
    if manifest is None:
        manifest = self._default_workspace
    self._workspace = Workspace(manifest=manifest)
    self.workspace_loaded.emit(self._workspace)
    self.push_variables({"workspace": self._workspace})
    return self._workspace
```

`add_example_to_workspace` — use manifest for dependency check:
```python
@staticmethod
def add_example_to_workspace(example_path: str, workspace_dir: str) -> list[str]:
    example = Example(example_path)
    slug = re_sub(r'[^\w\-]', '_', example.name).strip('_')
    dest = os.path.join(workspace_dir, slug)
    _copy_example_tree(example_path, dest)
    manifest = WorkspaceManifest.load(os.path.join(workspace_dir, "workspace.sciqlop"))
    return [d for d in example.dependencies if d not in manifest.requires]
```

`duplicate_workspace` — use manifest:
```python
@Slot(str)
def duplicate_workspace(self, workspace: str, background: bool = False):
    def duplicate(directory: str):
        shutil.copytree(directory, directory + "_copy")
        manifest = WorkspaceManifest.load(os.path.join(directory + "_copy", "workspace.sciqlop"))
        manifest.name = f"Copy of {manifest.name}"
        manifest.save(os.path.join(directory + "_copy", "workspace.sciqlop"))
    duplicate(workspace)
```

`list_workspaces` — return manifests:
```python
@staticmethod
def list_workspaces() -> list[WorkspaceManifest]:
    return list_existing_workspaces()
```

- [ ] **Step 2: Remove `_try_load_workspace` helper (no longer needed)**

- [ ] **Step 3: Remove imports of `WorkspaceSpecFile` from this file**

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/ -v -k "workspace"`

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/workspaces/backend/workspaces_manager.py
git commit -m "refactor(workspaces): WorkspaceManager uses WorkspaceManifest throughout"
```

---

## Chunk 4: Update welcome backend and clean up

### Task 7: Update welcome backend

**Files:**
- Modify: `SciQLop/components/welcome/backend.py`

- [ ] **Step 1: Update `_workspace_to_dict`**

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
    }
```

- [ ] **Step 2: Update `add_dependencies_to_workspace`**

```python
@Slot(str, str)
def add_dependencies_to_workspace(self, workspace_dir: str, dependencies_json: str) -> None:
    deps = json.loads(dependencies_json)
    manifest_path = os.path.join(workspace_dir, "workspace.sciqlop")
    manifest = WorkspaceManifest.load(manifest_path)
    new_deps = [d for d in deps if d not in manifest.requires]
    if new_deps:
        manifest.requires.extend(new_deps)
        manifest.save(manifest_path)
        try:
            cmd = uv_command("pip", "install", *new_deps)
            subprocess.run(cmd, check=True)
        except Exception as e:
            log.error(f"Failed to install dependencies: {e}")
```

- [ ] **Step 3: Update `update_workspace_field`**

```python
@Slot(str, str)
def update_workspace_field(self, directory: str, field_json: str) -> None:
    update = json.loads(field_json)
    manifest_path = os.path.join(directory, "workspace.sciqlop")
    try:
        manifest = WorkspaceManifest.load(manifest_path)
        field, value = update["field"], update["value"]
        if hasattr(manifest, field):
            setattr(manifest, field, value)
            manifest.save(manifest_path)
    except Exception as e:
        log.error(f"Failed to update workspace field: {e}")
```

- [ ] **Step 4: Update `get_hero_workspace`**

The `default_workspace` field is now `default` on the manifest:
```python
@Slot(result=str)
def get_hero_workspace(self) -> str:
    workspaces = workspaces_manager_instance().list_workspaces()
    non_default = [ws for ws in workspaces if not ws.default]
    if not non_default:
        return "null"
    non_default.sort(key=lambda ws: WorkspaceManifest.last_used(ws.directory), reverse=True)
    return json.dumps(_workspace_to_dict(non_default[0]))
```

- [ ] **Step 5: Update `list_workspaces` slot**

Sort uses timestamp helper now:
```python
@Slot(result=str)
def list_workspaces(self) -> str:
    workspaces = workspaces_manager_instance().list_workspaces()
    workspaces.sort(key=lambda ws: WorkspaceManifest.last_used(ws.directory), reverse=True)
    return json.dumps([_workspace_to_dict(ws) for ws in workspaces])
```

- [ ] **Step 6: Remove `WorkspaceSpecFile` import, add `WorkspaceManifest` import**

- [ ] **Step 7: Commit**

```bash
git add SciQLop/components/welcome/backend.py
git commit -m "refactor(welcome): use WorkspaceManifest for workspace data"
```

### Task 8: Update re-exports and remove WorkspaceSpec

**Files:**
- Modify: `SciQLop/components/workspaces/__init__.py`
- Modify: `SciQLop/core/data_models/models.py`

- [ ] **Step 1: Update `__init__.py` re-exports**

Replace `WorkspaceSpecFile` with `WorkspaceManifest` in:
`SciQLop/components/workspaces/__init__.py`

- [ ] **Step 2: Remove WorkspaceSpec and related factories from models.py**

In `SciQLop/core/data_models/models.py`, remove:
- `WorkspaceSpec` dataclass
- `WorkspaceSpecFile = register_spec_file(WorkspaceSpec, "workspace.json")`
- `WorkspaceSpecROFile = register_spec_file_readonly(WorkspaceSpec, "workspace.json")`
- Update `__all__`

Keep `ExampleSpec`, `ExampleSpecFile`, `ExampleSpecROFile` (still used).

- [ ] **Step 3: Delete dead code from old Qt widget welcome page**

These files are dead code — the old Qt widget welcome page was fully replaced by the QWebEngine-based `WebWelcomePage`. The `__init__.py` already imports from `web_welcome_page.py`.

```bash
rm SciQLop/components/welcome/welcome_page.py
rm SciQLop/components/welcome/sections/recent_workspaces.py
```

Also remove the `workspace_spec()` static method from `WorkspaceManager` (never called).

- [ ] **Step 4: Check for any remaining references**

Run: `grep -rn "WorkspaceSpecFile\|WorkspaceSpecROFile\|WorkspaceSpec" --include="*.py" SciQLop/`

Fix any remaining imports.

- [ ] **Step 5: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A SciQLop/components/workspaces/__init__.py SciQLop/core/data_models/models.py SciQLop/components/welcome/welcome_page.py SciQLop/components/welcome/sections/recent_workspaces.py
git commit -m "cleanup: remove WorkspaceSpec/WorkspaceSpecFile and dead welcome page code"
```

### Task 9: Update test fixtures

**Files:**
- Modify: `tests/test_add_example_to_workspace.py`

- [ ] **Step 1: Update test fixtures to create `workspace.sciqlop` instead of `workspace.json`**

Replace `workspace.json` fixture creation with `WorkspaceManifest`:

```python
from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest

@pytest.fixture
def workspace_dir(tmp_path):
    ws_dir = tmp_path / "ws"
    ws_dir.mkdir()
    manifest = WorkspaceManifest(name="test-ws", requires=["numpy"])
    manifest.save(ws_dir / "workspace.sciqlop")
    return ws_dir
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/test_add_example_to_workspace.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_add_example_to_workspace.py
git commit -m "test: update example-to-workspace tests for workspace.sciqlop"
```

### Task 10: Final verification

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Grep for any remaining workspace.json references in app code**

Run: `grep -rn "workspace\.json" --include="*.py" SciQLop/`

Only acceptable hits: `workspace_migration.py` (reads old format for migration).

- [ ] **Step 3: Commit any remaining fixes**
