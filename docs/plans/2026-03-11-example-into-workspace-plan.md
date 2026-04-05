# Decouple Examples from Workspace Creation — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make examples addable to any existing workspace instead of creating a new workspace per example.

**Architecture:** Replace `WorkspaceManager.load_example()` with `add_example_to_workspace()` that copies the example tree into a subfolder of the target workspace. The welcome page JS gains a workspace picker modal and dependency confirmation dialog. Backend stays UI-free; the web frontend owns the prompt flow.

**Tech Stack:** Python (PySide6 QWebChannel slots), JavaScript (welcome page), CSS (modal styling)

**Spec:** `docs/plans/2026-03-11-example-into-workspace.md`

---

## Chunk 1: Backend changes + tests

### Task 1: Add `add_example_to_workspace` to WorkspaceManager

**Files:**
- Modify: `SciQLop/components/workspaces/backend/workspaces_manager.py:113-125`
- Test: `tests/test_add_example_to_workspace.py` (create)

- [ ] **Step 1: Write the test file**

Create `tests/test_add_example_to_workspace.py`:

```python
import os
import json
import shutil
from pathlib import Path

import pytest


def _create_example(tmp_path, name="mms", deps=None, extra_files=None):
    """Create a minimal example directory with example.json and some files."""
    example_dir = tmp_path / "examples" / name
    example_dir.mkdir(parents=True)
    spec = {
        "name": name,
        "description": f"Test {name} example",
        "image": "image.png",
        "notebook": "index.ipynb",
        "tags": ["test"],
        "dependencies": deps or [],
    }
    (example_dir / "example.json").write_text(json.dumps(spec))
    (example_dir / "image.png").write_bytes(b"fake-png")
    (example_dir / "index.ipynb").write_text('{"cells": []}')
    if extra_files:
        for rel_path, content in extra_files.items():
            p = example_dir / rel_path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
    return str(example_dir)


def _create_workspace(tmp_path, name="test-ws", deps=None):
    """Create a minimal workspace directory with workspace.json."""
    ws_dir = tmp_path / "workspaces" / name
    ws_dir.mkdir(parents=True)
    spec = {
        "name": name,
        "description": "",
        "image": "",
        "notebooks": [],
        "dependencies": deps or [],
        "python_path": [],
        "last_used": "",
        "last_modified": "",
        "default_workspace": False,
    }
    (ws_dir / "workspace.json").write_text(json.dumps(spec))
    return str(ws_dir)


class TestAddExampleToWorkspace:
    def test_copies_notebook_into_subfolder(self, tmp_path):
        from SciQLop.components.workspaces.backend.workspaces_manager import WorkspaceManager

        example_path = _create_example(tmp_path)
        ws_dir = _create_workspace(tmp_path)

        missing = WorkspaceManager.add_example_to_workspace(example_path, ws_dir)

        assert os.path.exists(os.path.join(ws_dir, "mms", "index.ipynb"))
        assert missing == []

    def test_skips_metadata_files(self, tmp_path):
        from SciQLop.components.workspaces.backend.workspaces_manager import WorkspaceManager

        example_path = _create_example(tmp_path)
        ws_dir = _create_workspace(tmp_path)

        WorkspaceManager.add_example_to_workspace(example_path, ws_dir)

        assert not os.path.exists(os.path.join(ws_dir, "mms", "example.json"))
        assert not os.path.exists(os.path.join(ws_dir, "mms", "image.png"))

    def test_copies_subdirectories(self, tmp_path):
        from SciQLop.components.workspaces.backend.workspaces_manager import WorkspaceManager

        example_path = _create_example(tmp_path, extra_files={
            "Notebooks/demo.ipynb": '{"cells": []}',
        })
        ws_dir = _create_workspace(tmp_path)

        WorkspaceManager.add_example_to_workspace(example_path, ws_dir)

        assert os.path.exists(os.path.join(ws_dir, "mms", "Notebooks", "demo.ipynb"))

    def test_returns_missing_dependencies(self, tmp_path):
        from SciQLop.components.workspaces.backend.workspaces_manager import WorkspaceManager

        example_path = _create_example(tmp_path, deps=["spok", "numpy"])
        ws_dir = _create_workspace(tmp_path, deps=["numpy"])

        missing = WorkspaceManager.add_example_to_workspace(example_path, ws_dir)

        assert missing == ["spok"]

    def test_overwrites_existing_subfolder(self, tmp_path):
        from SciQLop.components.workspaces.backend.workspaces_manager import WorkspaceManager

        example_path = _create_example(tmp_path)
        ws_dir = _create_workspace(tmp_path)

        # Add once
        WorkspaceManager.add_example_to_workspace(example_path, ws_dir)
        # Modify the example notebook
        Path(example_path, "index.ipynb").write_text('{"cells": ["updated"]}')
        # Add again — should overwrite
        WorkspaceManager.add_example_to_workspace(example_path, ws_dir)

        content = Path(ws_dir, "mms", "index.ipynb").read_text()
        assert "updated" in content
```

- [ ] **Step 2: Run the tests — verify they fail**

Run: `uv run pytest tests/test_add_example_to_workspace.py -v`
Expected: All 5 tests FAIL (AttributeError: `WorkspaceManager` has no attribute `add_example_to_workspace`)

- [ ] **Step 3: Implement `add_example_to_workspace` as a static method**

In `SciQLop/components/workspaces/backend/workspaces_manager.py`, add this import at the top:

```python
from re import sub as re_sub
```

Then add this static method to `WorkspaceManager` (after `load_example`, which we'll remove in a later step):

```python
@staticmethod
def add_example_to_workspace(example_path: str, workspace_dir: str) -> List[str]:
    example = Example(example_path)
    slug = re_sub(r'[^\w\-]', '_', example.name).strip('_')
    dest = os.path.join(workspace_dir, slug)
    _copy_example_tree(example_path, dest)
    ws_spec = WorkspaceSpecFile(workspace_dir)
    return [d for d in example.dependencies if d not in ws_spec.dependencies]
```

Add the helper function above the class (after the `_try_load_workspace` function):

```python
_EXAMPLE_METADATA_FILES = {"example.json", "image.png"}


def _copy_example_tree(src: str, dest: str):
    for entry in os.listdir(src):
        if entry in _EXAMPLE_METADATA_FILES:
            continue
        src_path = os.path.join(src, entry)
        dest_path = os.path.join(dest, entry)
        if os.path.isdir(src_path):
            shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
        else:
            os.makedirs(dest, exist_ok=True)
            shutil.copy2(src_path, dest_path)
```

Also add the `WorkspaceSpecFile` import — it's already imported via `from SciQLop.core.data_models import WorkspaceSpecFile`.

Add `from re import sub as re_sub` to the imports at top of file.

- [ ] **Step 4: Run the tests — verify they pass**

Run: `uv run pytest tests/test_add_example_to_workspace.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Remove `load_example` method**

Delete the `load_example` method (lines 113–125) from `WorkspaceManager` in `workspaces_manager.py`.

- [ ] **Step 6: Run full test suite to check nothing else breaks**

Run: `uv run pytest -x -v`
Expected: PASS (nothing else in the test suite calls `load_example` directly)

- [ ] **Step 7: Commit**

```bash
git add tests/test_add_example_to_workspace.py SciQLop/components/workspaces/backend/workspaces_manager.py
git commit -m "feat: replace load_example with add_example_to_workspace static method"
```

---

### Task 2: Update WelcomeBackend slots

**Files:**
- Modify: `SciQLop/components/welcome/backend.py:141-165`

- [ ] **Step 1: Replace `open_example` with new slots**

In `SciQLop/components/welcome/backend.py`, replace the `open_example` slot (lines 163-165) with:

```python
@Slot(result=str)
def get_active_workspace_dir(self) -> str:
    manager = workspaces_manager_instance()
    if manager.has_workspace:
        return json.dumps(manager.workspace.workspace_dir)
    return json.dumps(None)

@Slot(str, str, result=str)
def add_example_to_workspace(self, example_dir: str, workspace_dir: str) -> str:
    missing = WorkspaceManager.add_example_to_workspace(example_dir, workspace_dir)
    return json.dumps({"missing_dependencies": missing})

@Slot(str, str)
def add_dependencies_to_workspace(self, workspace_dir: str, dependencies_json: str) -> None:
    deps = json.loads(dependencies_json)
    ws_spec = WorkspaceSpecFile(workspace_dir)
    existing = set(ws_spec.dependencies)
    new_deps = [d for d in deps if d not in existing]
    if new_deps:
        ws_spec.dependencies = list(existing) + new_deps
```

Add the needed import at the top of the file:

```python
from SciQLop.components.workspaces.backend.workspaces_manager import workspaces_manager_instance, WorkspaceManager
```

(Replace the existing `from SciQLop.components.workspaces.backend.workspaces_manager import workspaces_manager_instance` line.)

Also add at the top:

```python
from SciQLop.core.data_models import WorkspaceSpecFile
```

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest -x -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add SciQLop/components/welcome/backend.py
git commit -m "feat: replace open_example slot with get_active_workspace_dir/add_example/add_deps"
```

---

### Task 3: Update ExamplesView.py (legacy Qt UI)

**Files:**
- Modify: `SciQLop/components/welcome/sections/ExamplesView.py:22-23,59`

- [ ] **Step 1: Update both `load_example` call sites**

In `SciQLop/components/welcome/sections/ExamplesView.py`:

Replace the import line:
```python
from SciQLop.components.workspaces import workspaces_manager_instance
```
with:
```python
from SciQLop.components.workspaces.backend.workspaces_manager import WorkspaceManager, workspaces_manager_instance
```

Replace `ExampleCard._open_example` (line 22-23):
```python
def _open_example(self):
    manager = workspaces_manager_instance()
    ws_dir = manager.workspace.workspace_dir
    WorkspaceManager.add_example_to_workspace(self._example.directory, ws_dir)
```

Replace the button connection in `ExampleDescriptionWidget.__init__` (line 59):
```python
self._open_button.clicked.connect(
    lambda: WorkspaceManager.add_example_to_workspace(
        example.example.directory,
        workspaces_manager_instance().workspace.workspace_dir,
    )
)
```

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest -x -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add SciQLop/components/welcome/sections/ExamplesView.py
git commit -m "fix: update legacy ExamplesView to use add_example_to_workspace"
```

---

## Chunk 2: Welcome page UI (JS/CSS/HTML)

### Task 4: Add workspace picker modal markup and styles

**Files:**
- Modify: `SciQLop/components/welcome/resources/welcome.html.j2:60-64`
- Modify: `SciQLop/components/welcome/resources/welcome.css`

- [ ] **Step 1: Add modal markup to the HTML template**

In `SciQLop/components/welcome/resources/welcome.html.j2`, add the modal overlay before the closing `</body>` tag (before the `<script>` tag, after the `</aside>`):

```html
    <div id="modal-overlay" class="modal-overlay hidden">
        <div class="modal">
            <h2 id="modal-title"></h2>
            <div id="modal-body"></div>
            <div id="modal-actions"></div>
        </div>
    </div>
```

- [ ] **Step 2: Add modal CSS styles**

Append to the end of `SciQLop/components/welcome/resources/welcome.css`:

```css
/* --- Modal overlay --- */

.modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
}

.modal-overlay.hidden {
    display: none;
}

.modal {
    background: var(--base, #2b2b2b);
    border: 1px solid var(--surface0, #444);
    border-radius: 12px;
    padding: 24px;
    min-width: 360px;
    max-width: 500px;
    max-height: 70vh;
    overflow-y: auto;
}

.modal h2 {
    margin: 0 0 16px 0;
    font-size: 1.1rem;
}

.modal-ws-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 16px;
}

.modal-ws-item {
    padding: 10px 14px;
    border: 1px solid var(--surface0, #444);
    border-radius: 8px;
    cursor: pointer;
    transition: background 0.15s;
}

.modal-ws-item:hover {
    background: var(--surface0, #333);
}

.modal-ws-item .ws-name {
    font-weight: 600;
}

.modal-ws-item .ws-sub {
    font-size: 0.85em;
    opacity: 0.7;
}

.modal-dep-list {
    margin: 8px 0 16px 0;
    padding-left: 20px;
    font-size: 0.9em;
    font-family: monospace;
}

#modal-actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
    margin-top: 16px;
}

#modal-actions button {
    padding: 8px 18px;
    border-radius: 6px;
    border: 1px solid var(--surface0, #444);
    background: var(--surface0, #333);
    color: var(--text, #ccc);
    cursor: pointer;
}

#modal-actions button.primary {
    background: var(--blue, #6791c9);
    border-color: var(--blue, #6791c9);
    color: #fff;
}
```

- [ ] **Step 3: Commit**

```bash
git add SciQLop/components/welcome/resources/welcome.html.j2 SciQLop/components/welcome/resources/welcome.css
git commit -m "feat: add modal overlay markup and styles for example workflow"
```

---

### Task 5: Implement the example flow in JavaScript

**Files:**
- Modify: `SciQLop/components/welcome/resources/welcome.js:182-213,263-277`

- [ ] **Step 1: Add modal helper functions**

Append these functions to the end of `welcome.js` (before the final `init();` call):

```javascript
// --- Modal helpers ---

function showModal(title, bodyHtml, actionsHtml) {
    document.getElementById("modal-title").textContent = title;
    document.getElementById("modal-body").innerHTML = bodyHtml;
    document.getElementById("modal-actions").innerHTML = actionsHtml;
    document.getElementById("modal-overlay").classList.remove("hidden");
}

function hideModal() {
    document.getElementById("modal-overlay").classList.add("hidden");
}
```

- [ ] **Step 2: Add the workspace picker function**

Append after the modal helpers:

```javascript
function showWorkspacePicker(onPicked) {
    backend.list_workspaces(function(json_str) {
        var workspaces = JSON.parse(json_str);
        var listHtml = '<div class="modal-ws-list">';
        listHtml += '<div class="modal-ws-item" data-action="new">' +
            '<span class="ws-name">+ Create new workspace</span></div>';
        workspaces.forEach(function(ws) {
            listHtml += '<div class="modal-ws-item" data-dir="' + escapeAttr(ws.directory) + '">' +
                '<span class="ws-name">' + escapeHtml(ws.name) + '</span>' +
                '<span class="ws-sub">' + escapeHtml(ws.last_used) + '</span>' +
                '</div>';
        });
        listHtml += '</div>';
        showModal("Choose a workspace", listHtml,
            '<button onclick="hideModal()">Cancel</button>');

        document.querySelectorAll(".modal-ws-item").forEach(function(item) {
            item.addEventListener("click", function() {
                hideModal();
                if (item.dataset.action === "new") {
                    backend.create_workspace();
                    // After creation, the workspace list refreshes;
                    // use the default workspace as target
                    backend.list_workspaces(function(json2) {
                        var wsList = JSON.parse(json2);
                        if (wsList.length > 0) {
                            wsList.sort(function(a, b) {
                                return b.last_modified.localeCompare(a.last_modified);
                            });
                            onPicked(wsList[0].directory);
                        }
                    });
                } else {
                    backend.open_workspace(item.dataset.dir);
                    onPicked(item.dataset.dir);
                }
            });
        });
    });
}
```

- [ ] **Step 3: Add the dependency confirmation function**

Append:

```javascript
var _pendingDeps = null;

function confirmDependencies(wsDir, deps) {
    if (!deps || deps.length === 0) return;
    _pendingDeps = { wsDir: wsDir, deps: deps };
    var listHtml = '<p>This example needs additional packages:</p><ul class="modal-dep-list">';
    deps.forEach(function(d) { listHtml += '<li>' + escapeHtml(d) + '</li>'; });
    listHtml += '</ul>';
    showModal("Install dependencies?", listHtml, "");

    var actions = document.getElementById("modal-actions");
    var skipBtn = document.createElement("button");
    skipBtn.textContent = "Skip";
    skipBtn.addEventListener("click", hideModal);

    var installBtn = document.createElement("button");
    installBtn.textContent = "Install";
    installBtn.className = "primary";
    installBtn.addEventListener("click", function() {
        hideModal();
        backend.add_dependencies_to_workspace(
            _pendingDeps.wsDir, JSON.stringify(_pendingDeps.deps));
        _pendingDeps = null;
    });

    actions.appendChild(skipBtn);
    actions.appendChild(installBtn);
}
```

- [ ] **Step 4: Add the main `openExample` flow function**

Append:

```javascript
function openExample(exampleDir) {
    backend.get_active_workspace_dir(function(json_str) {
        var wsDir = JSON.parse(json_str);
        if (wsDir) {
            addExampleAndPromptDeps(exampleDir, wsDir);
        } else {
            showWorkspacePicker(function(pickedDir) {
                addExampleAndPromptDeps(exampleDir, pickedDir);
            });
        }
    });
}

function addExampleAndPromptDeps(exampleDir, wsDir) {
    backend.add_example_to_workspace(exampleDir, wsDir, function(json_str) {
        var result = JSON.parse(json_str);
        if (result.missing_dependencies && result.missing_dependencies.length > 0) {
            confirmDependencies(wsDir, result.missing_dependencies);
        }
    });
}
```

- [ ] **Step 5: Update `createExampleCard` to use the new flow**

Replace the double-click handler in `createExampleCard` (line 211):

Change:
```javascript
    card.addEventListener("dblclick", function() {
        backend.open_example(ex.directory);
    });
```
To:
```javascript
    card.addEventListener("dblclick", function() {
        openExample(ex.directory);
    });
```

- [ ] **Step 6: Update `showExampleDetails` to use the new flow**

Replace the button in `showExampleDetails` (line 272):

Change:
```javascript
            '<button onclick="backend.open_example(\'' + escapeAttr(ex.directory) + '\')">Open example</button>' +
```
To:
```javascript
            '<button onclick="openExample(\'' + escapeAttr(ex.directory) + '\')">Add to workspace</button>' +
```

- [ ] **Step 7: Add click-outside-to-close for the modal**

In the `DOMContentLoaded` event listener (around line 330), add:

```javascript
    document.getElementById("modal-overlay").addEventListener("click", function(e) {
        if (e.target === this) hideModal();
    });
```

- [ ] **Step 8: Commit**

```bash
git add SciQLop/components/welcome/resources/welcome.js
git commit -m "feat: implement workspace picker + dep confirmation flow for examples"
```

---

### Task 6: Manual smoke test

- [ ] **Step 1: Run the application**

Run: `uv run sciqlop`

- [ ] **Step 2: Verify the example flow**

1. On the welcome page, click an example card — verify the details panel shows "Add to workspace" (not "Open example")
2. Double-click an example card:
   - If no workspace is loaded → workspace picker modal should appear
   - Pick a workspace → example files should be copied into a subfolder
   - If the example has dependencies → confirmation dialog should appear
3. If a workspace is already loaded, double-clicking should skip the picker and add directly

- [ ] **Step 3: Commit any fixes if needed**
