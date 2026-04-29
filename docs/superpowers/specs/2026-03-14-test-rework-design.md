# Test Rework Design

## Problem

SciQLop tests currently boot the full application (`start_sciqlop()`) per test function.
This takes ~7s per test due to plugin loading (~6.2s) and main window creation (~0.6s).
Tests are slow to run, painful to maintain, and discourage adding new coverage.

### Startup profiling

| Step | Time |
|------|------|
| Import `SciQLopMainWindow` | 300ms (mostly speasy: 911ms first time) |
| Create `SciQLopMainWindow()` | 287ms |
| Show + processEvents | 10ms |
| `load_all` plugins | 6,200ms |
| **Total `start_sciqlop()`** | **~7s** |

Speasy import cost (911ms) breaks down into: astropy.table (191ms), matplotlib.pyplot (182ms), pandas (165ms), astroquery (81ms), diskcache (68ms). This is accepted as-is — fixing it requires upstream speasy changes.

## Design

### Three test tiers

| Tier | Fixture | Scope | Cost | Purpose |
|------|---------|-------|------|---------|
| Unit | none / `tmp_path` | function | 0ms | Pure logic (fuzzy scoring, manifest parsing, config, MIME) |
| Widget | `qapp` + individual widgets | function | ~50ms per test (session pays import cost once) | Single component behavior in isolation |
| Workflow | `main_window` | module | ~7s once per file | End-to-end user stories |

### Workflow-based integration tests

Instead of isolated test functions that each boot the app, tests are grouped into **workflow classes** that mirror real user sessions. Tests within a workflow are ordered and cumulative — they build on each other:

```python
# test_wf_catalog_labeling.py

class TestLabelingWorkflow:
    """User opens SciQLop, plots data, creates a catalog, labels events."""

    catalog = None  # class attributes for passing state between tests

    def test_create_plot_panel(self, main_window, qtbot):
        ...

    def test_plot_product(self, main_window, qtbot):
        ...

    def test_create_catalog(self, main_window, qtbot):
        TestLabelingWorkflow.catalog = ...  # store for next test

    def test_add_event_to_catalog(self, main_window, qtbot):
        catalog = TestLabelingWorkflow.catalog  # retrieve from previous test
        ...

    def test_event_appears_on_plot(self, main_window, qtbot):
        ...
```

**Test ordering:** pytest collects methods in definition order (CPython preserves class body order). This is relied upon — no extra dependency needed. If this ever breaks, add `pytest-order`.

**State sharing:** workflow classes use class attributes to pass Python objects (catalog refs, panel refs, etc.) between ordered tests. The main window itself carries UI state naturally.

The `main_window` fixture is **module-scoped**: one `start_sciqlop()` per workflow file. State accumulates naturally within a workflow, just like a real user session.

### Filesystem isolation

Tests must never write to `~/.config/sciqlop/` or `~/.local/share/sciqlop/`. A session-scoped `sciqlop_test_env` autouse fixture redirects all persistent paths to temp directories:

- `XDG_CONFIG_HOME` → `{tmp}/config` (Linux/macOS)
- `XDG_DATA_HOME` → `{tmp}/data`
- `SCIQLOP_WORKSPACE_DIR` → `{tmp}/workspace`
- `APPDATA` → `{tmp}/config` (Windows)
- `SPEASY_SKIP_INIT_PROVIDERS=1` — this env var exists in speasy (already set by `sciqlop_launcher.py:91`). It skips runtime provider initialization (network calls, inventory loading), NOT the import cost. The 911ms import cost is still paid once per session.

No mocking — real code runs, just pointed at throwaway paths.

### File layout

```
tests/
  conftest.py              # sciqlop_test_env (session, autouse)
  fixtures.py              # qapp_cls, main_window (module-scoped), widget helpers
  helpers.py               # drag_and_drop, mouseMove, etc.

  # Unit tests — no prefix convention needed, they're already fine
  test_workspace_manifest.py
  test_command_palette_fuzzy.py
  test_mime.py
  ...

  # Widget tests — prefix: test_w_
  test_w_command_palette.py
  test_w_settings_panel.py
  ...

  # Workflow tests — prefix: test_wf_
  test_wf_plot_and_navigate.py
  test_wf_virtual_products.py
  test_wf_catalog_labeling.py
  test_wf_drag_and_drop.py
  test_wf_workspace.py
  ...
```

### Fixture dependency chain

```
sciqlop_test_env (session, autouse)
  └── redirects XDG_CONFIG_HOME, XDG_DATA_HOME, SCIQLOP_WORKSPACE_DIR to tmp
  └── sets SPEASY_SKIP_INIT_PROVIDERS=1

qapp_cls (session) — existing, tells pytest-qt to use SciQLopApp
  └── pytest-qt's qapp fixture creates the QApplication singleton

main_window (module)
  └── depends on: qapp (via pytest-qt)
  └── does NOT call start_sciqlop() directly (it creates splash screens,
  │     re-runs setAttribute, etc.). Instead runs the essential subset:
  │     1. SciQLopMainWindow()
  │     2. load_all(main_window)
  │     3. register_builtin_commands(app.command_registry)
  │     4. harvest_qactions(app.command_registry, main_window)
  └── shared across all tests in the workflow file
  └── teardown:
        1. main_window.close()
        2. app.command_registry.clear() — prevent duplicate entries
           from accumulating across workflow files
```

**`qtbot` stays function-scoped** (pytest-qt default). The module-scoped `main_window` fixture does NOT depend on `qtbot`. It uses `QApplication.processEvents()` for any waits during setup. Individual test methods inject `qtbot` as usual for interactions.

**Teardown between workflow files:** the `main_window` fixture's teardown closes the main window (`main_window.close()`). The next workflow file's `main_window` fixture creates a fresh `SciQLopMainWindow` + `load_all()`. The `QApplication` and event loop singletons persist across modules (session-scoped), only the main window is recreated.

### Migration plan

1. Add `sciqlop_test_env` fixture — all existing tests benefit immediately
2. Rewrite `main_window` fixture: module-scoped, no `qtbot` dependency, with teardown. This requires updating the fixture signature and replacing `qtbot.wait()` / `qtbot.addWidget()` calls in the fixture itself with `QApplication.processEvents()`.
3. Reorganize existing integration tests into `test_wf_*` workflow classes
4. Add new workflow tests for uncovered features
5. Add `test_w_*` widget tests for components testable without full app

### CI

- `uv run pytest` runs everything
- Each workflow file pays the ~7s startup cost once
- No special markers needed; skip workflows with `pytest --ignore-glob='tests/test_wf_*'` if desired
- Must run on GitHub Actions with no complex setup beyond `pytest-qt` + `pytest-xvfb`
- Parallel execution (`pytest-xdist`) is out of scope for now
