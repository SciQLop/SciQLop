# Decouple Examples from Workspace Creation

## Problem

Opening an example currently creates a brand new workspace, copies the example files into it, and starts JupyterLab. This is misleading — examples should be content that a user can add to any workspace, not a workspace factory.

## Design

### Mental model

An example is a directory tree (notebooks + supporting files) that gets copied into a subfolder of an existing workspace. The user chooses which workspace receives it.

### Backend API

**WorkspaceManager** (`workspaces_manager.py`):

- **Remove** `load_example()`
- **Add** `add_example_to_workspace(example_path: str, workspace_dir: Optional[str] = None) -> List[str]`:
  - Resolves target workspace: if `workspace_dir` is None, uses current workspace
  - Loads `Example(example_path)` to read metadata
  - Copies the example directory tree into `<workspace>/<example.name>/`, excluding `example.json` and `image.png` (metadata-only files)
  - Returns list of dependencies from `example.json` that are not already in the workspace's dependency list

**WelcomeBackend** (`backend.py`):

- **Remove** `open_example(directory)` slot
- **Add** `get_active_workspace_dir() -> str`: returns JSON string (workspace dir path) or JSON null
- **Add** `add_example_to_workspace(example_dir: str, workspace_dir: str) -> str`: calls manager, returns JSON `{"missing_dependencies": [...]}`
- **Add** `add_dependencies_to_workspace(workspace_dir: str, dependencies: str) -> None`: records deps (JSON list) in the workspace spec for later installation

### Edge cases

**Example subfolder already exists**: If `<workspace>/<example.name>/` already exists (user added the same example before), overwrite it. Use `shutil.copytree(dirs_exist_ok=True)` for merging.

**Workspace already loaded**: `WorkspaceManager.load_workspace()` raises if called twice. The UI flow handles this: step 1 checks `has_active_workspace()`. If true, skip the workspace picker and use the current workspace directly. The picker only appears when no workspace is loaded.

### File tree copying

Given an example:
```
mms/
  example.json    <- skip (discovery metadata)
  image.png       <- skip (thumbnail for UI)
  index.ipynb     <- copy
  Notebooks/      <- copy recursively
```

The workspace receives:
```
<workspace>/mms/
  index.ipynb
  Notebooks/
    DemoMMS_tags-up_meeting.ipynb
    MMS_dayside_magnetopause.ipynb
```

Subfolder is named after `example.name` (slugified to be filesystem-safe). Multiple examples don't collide.

### Welcome page UI flow

When user clicks "Open example" or double-clicks an example card:

1. Call `get_active_workspace_dir()` to check if a workspace is loaded (returns its dir or null)
2. **If no active workspace**: show a modal overlay with:
   - List of existing workspaces (from `list_workspaces()`)
   - A "Create new workspace" button
   - User picks one -> backend loads/creates it
3. Call `add_example_to_workspace(example_dir, workspace_dir)` -> get `missing_dependencies`
4. **If missing dependencies**: show confirmation dialog listing the packages, ask Yes/No
5. **If yes**: call `add_dependencies_to_workspace(workspace_dir, dependencies)`

The modal is an HTML overlay in the welcome page, styled consistently with the existing detail panel.

### Files modified

| File | Change |
|------|--------|
| `SciQLop/components/workspaces/backend/workspaces_manager.py` | Remove `load_example()`, add `add_example_to_workspace()` |
| `SciQLop/components/welcome/backend.py` | Replace `open_example()` with new slots: `get_active_workspace_dir()`, `add_example_to_workspace()`, `add_dependencies_to_workspace()` |
| `SciQLop/components/welcome/resources/welcome.js` | Replace `backend.open_example()` calls with modal flow |
| `SciQLop/components/welcome/resources/welcome.css` | Add modal overlay styles |
| `SciQLop/components/welcome/resources/welcome.html.j2` | Add modal markup (or generate purely in JS) |
| `SciQLop/components/welcome/sections/ExamplesView.py` | Update `ExampleCard._open_example` and `ExampleDescriptionWidget` button to use new API instead of `load_example()` |

### Files unchanged

- `Example` class, `ExampleSpec` dataclass, `Workspace` class — reused as-is
- Example data files (`example.json`, notebooks) — no changes
- No new files created
