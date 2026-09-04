# Update SciQLop core version per workspace — design

Date: 2026-09-04
Status: approved for planning

## Motivation

Every workspace now installs SciQLop itself into its own self-contained venv
(`sciqlop[all]` pinned via `WorkspaceManifest.sciqlop_version`, resolved and
installed by `uv sync`). There is currently no UI to change which version a
workspace has installed — a user can only see a **read-only** "update
available" banner in the welcome pane that links out to the GitHub release
page. This spec adds an actual update/manage action, placed in the workspace
details panel (welcome pane) next to the existing "Packages" list, since that
panel is already where per-workspace pip dependencies are added/removed.

## Existing system (facts, verified against source)

- `WorkspaceManifest.sciqlop_version` (`workspace_manifest.py`) is the pin.
  Empty string already means "install from `git+...@main`" — this is
  existing, established behavior (`workspace_project.py:sciqlop_requirement`),
  not something this feature invents. A non-empty value is pinned exactly:
  `f"sciqlop[all]=={version}"`.
- `prepare_workspace()` (`workspace_setup.py:131`) is the single function that
  correctly prepares *any* workspace directory: it loads/repairs the
  manifest, collects plugin dependencies (`collect_plugin_dependencies`) and
  AppStore-installed dependencies (`SciQLopPluginsSettings().installed_packages`),
  regenerates `pyproject.toml` via `generate_pyproject_toml(manifest,
  plugin_deps + appstore_deps, pyproject_path)`, invalidates a stale
  `uv.lock`, and syncs the venv. It only pins `sciqlop_version` itself when
  creating a brand-new manifest (manifest file doesn't exist yet); for an
  existing manifest it uses whatever is already on disk. This makes it the
  correct, already-tested primitive to reuse — not something to reimplement.
- `WorkspaceManifest.save()` already writes atomically (`write_text_atomic`).
- `uv_command()` (`workspaces/backend/uv.py`) returns an argument list; all
  `uv` invocations use `subprocess` without `shell=True` — no shell-injection
  surface for this feature to worry about.
- No locking of any kind (file lock, `threading.Lock`, etc.) exists anywhere
  in the workspace/venv/AppStore backends today. Concurrent mutation of the
  same workspace's venv (e.g. two SciQLop processes on the same workspace, or
  launcher startup racing a welcome-pane edit) is an existing, pre-existing
  gap in the whole system — not introduced by this feature. Fully solving it
  is out of scope here (see Non-goals).
- Two existing UI-triggered install flows establish the pattern to follow:
  welcome pane's `add_dependencies_to_workspace`/`remove_dependency_from_workspace`
  (`welcome/backend.py:332-383`) and AppStore's `install_package`/`uninstall_package`
  (`appstore/backend.py`). Both: daemon thread, `subprocess.run(...,
  capture_output=True)`, a single Qt signal emitted once at completion (no
  streaming progress).

## Goals

- Let the user change which SciQLop version a workspace installs, from the
  welcome pane's workspace-details panel.
- Offer a small set of recent PyPI releases (source of truth for what's
  actually installable) plus a "main (development)" entry that tracks
  `git+...@main`.
- Work for any workspace on disk, not only the currently active one.
- Match the existing simple progress-reporting pattern (spinner + one
  completion signal) — no new streaming-log UI.
- Never leave the manifest pointing at a version that wasn't actually
  installed.

## Non-goals (explicitly deferred)

- **Whole-system locking.** A proper cross-process lock shared by launcher
  startup, AppStore install, the dependency list, and this new action would
  retrofit safety onto paths well outside this feature's scope. This spec
  adds a lock scoped only to serializing concurrent uses of *this* new
  action against the *same* workspace (e.g. a double-click, or two welcome
  panes open on the same workspace). The broader gap is a separate,
  pre-existing hardening item.
- **Auto-restart after updating the active workspace.** The running process
  keeps its already-loaded code regardless of what changes on disk. This
  feature only surfaces a "restart to apply" notice; it does not wire into
  the launcher's reserved-but-unused `EXIT_RESTART` exit code.
- **Streaming install progress.** Matches the existing spinner/single-signal
  pattern used by the Packages list and AppStore install.
- **Full atomic environment swap** (temp venv + swap-on-success). The
  manifest write is transactional (see below); a partially-applied venv sync
  failure is left in the same state a normal launcher-startup sync failure
  would leave it in today — not worse than the status quo.

## UI

New "SciQLop Core" section in the workspace details panel
(`welcome/resources/welcome.js`, `showWorkspaceDetails()`), visually matching
the existing `pkg-list` section:

- A label showing the current pinned version, or "main (development)" when
  `sciqlop_version` is empty.
- One `<select>` populated from `fetch_available_core_versions()`: recent
  PyPI releases (newest first, capped to ~15) plus a "main (development)"
  entry, preselected to the newest release (or to "main" if that's what's
  currently pinned). One control, not separate "quick update" vs "pick
  version" buttons — the default selection already covers the quick-update
  case.
- One "Install" button. Disabled + spinner while an install is in flight for
  that workspace. A status line reports success/error afterward. On success,
  if the updated workspace is the one currently running
  (`SCIQLOP_WORKSPACE_DIR` match via the existing realpath comparison used
  elsewhere), the status line says "Installed — restart SciQLop to apply"
  instead of a plain success message.

## Backend

### `workspace_project.py` (pure helpers)

- `fetch_available_versions() -> list[str]`: query PyPI's JSON API
  (`https://pypi.org/pypi/SciQLop/json`) with a bounded timeout. Parse
  releases with `packaging.version.Version` (not string sort), exclude
  yanked and prerelease/dev versions, sort descending, cap to recent N
  (~15). Raise/return empty on malformed response or network failure — the
  caller decides the fallback (see Error handling).
- `validate_core_version(version: str, available: list[str]) -> bool`: the
  Python-side re-validation boundary. Accepts only the literal empty string
  ("main") or an exact match against `available` (the list this same
  request's PyPI fetch just returned, or a freshly re-fetched one — not a
  client-supplied list). Rejects anything else, including any string with
  whitespace, `@`, `/`, or PEP 440 specifier/URL/VCS syntax. This exists
  because the dropdown is not a security boundary: a QWebChannel caller can
  invoke the backend slot with an arbitrary string, and the value is later
  interpolated into `sciqlop_requirement()`'s output.

### `workspace_setup.py`

- `prepare_workspace()` gains an optional parameter:
  `manifest: WorkspaceManifest | None = None`. When given, skip the internal
  `WorkspaceManifest.load_or_repair()` load and use the passed-in manifest
  object instead (still going through the same migration/mkdir/plugin/appstore
  dependency collection/pyproject generation/lock invalidation/sync steps).
  Existing callers (launcher, dev prepare) are unaffected — the parameter
  defaults to `None` and behavior is byte-identical when omitted.
- New `apply_core_version(workspace_dir, version: str) -> Path`: loads the
  manifest, stages `manifest.sciqlop_version = version` **in memory only**,
  calls `prepare_workspace(workspace_dir, manifest=manifest)`. Only if that
  call succeeds does it call `manifest.save(manifest_path)` to persist the
  pin. On any exception from `prepare_workspace`, the on-disk manifest is
  never touched, and the exception propagates to the caller. This makes the
  manifest side of the operation transactional: a failed sync never leaves
  the manifest pointing at a version that isn't installed.
- Per-workspace serialization: `apply_core_version` acquires a simple
  exclusive lock scoped to the workspace directory (stdlib-only — e.g. an
  `O_CREAT | O_EXCL` marker file with a stale-lock check via PID/mtime, no
  new dependency) before touching the manifest, and releases it in a
  `finally`. A second concurrent call for the *same* workspace directory
  fails fast with a clear "update already in progress" error instead of
  racing `uv sync`/`uv.lock`.

### `welcome/backend.py`

Two new thin `WelcomeBackend` slots, matching the existing pattern exactly
(daemon thread, one Qt signal at completion):

- `fetch_available_core_versions()` → background thread calls
  `fetch_available_versions()`, emits `core_versions_ready(json)` with
  `{ok, versions, error}`.
- `apply_core_version(workspace_dir, version)` → background thread
  re-validates `version` via `validate_core_version()` against a fresh
  `fetch_available_versions()` result (or "main"), then calls
  `workspace_setup.apply_core_version()`, emits `core_update_finished(json)`
  with `{ok, workspace_dir, version, is_active_workspace, error}`.

`_workspace_to_dict()` (`welcome/backend.py:48`) gains a `sciqlop_version`
field so the UI can render the current pin without a separate round-trip.

## Data flow

1. User opens a workspace's details panel → JS calls
   `fetch_available_core_versions()` (parallel to the existing latest-release
   GitHub check) → renders the dropdown, preselected to latest (or "main" if
   currently pinned to it).
2. User optionally changes the selection, clicks Install → JS calls
   `apply_core_version(workspace_dir, selected_version)`, disables the
   control, shows a spinner.
3. Backend: validate → acquire per-workspace lock → stage manifest → call
   `prepare_workspace(workspace_dir, manifest=staged)` → on success, save
   manifest, release lock, emit `core_update_finished` with `ok: true`.
4. JS renders success (with "restart to apply" if this is the active
   workspace) or the error detail.

## Error handling

- PyPI fetch failure (network/timeout/malformed JSON/empty release list) →
  `core_versions_ready` reports `ok: false`; JS falls back to showing only
  the currently-pinned version (still selectable/re-installable) plus
  "main", with an inline retry — never silently presents an incomplete list
  as if it were the full one.
- Version validation failure (should not happen from the UI itself, but
  covers a direct QWebChannel call) → `core_update_finished` with a clear
  `error`, no manifest touched.
- Lock-already-held → fails fast with "update already in progress" error, no
  manifest touched.
- `uv sync` / `prepare_workspace` failure → surface the tail of
  `subprocess.CalledProcessError.stderr` (reuse the existing
  `_error_detail`-style extraction from AppStore's backend rather than a
  second implementation), manifest left unchanged.
- Post-sync `manifest.save()` failure (disk full, permissions) → distinct
  error surfaced as "installed but failed to record the change" rather than
  silently reported as success, since this is the one case where disk state
  and manifest state can genuinely diverge.

## Testing

- `workspace_project.py`: `fetch_available_versions()` — final-version
  sorting, prerelease/dev/yanked filtering, malformed PyPI data, timeout,
  empty-result guard (stub the HTTP call). `validate_core_version()` —
  accepts exact matches and empty string, rejects hostile strings (quotes,
  newlines, `;`, `@`, URLs, path-like values, arbitrary PEP 440 specifiers).
- `workspace_setup.py`: `apply_core_version()` against a temp workspace dir
  (stub the `uv` subprocess) —
  - successful update preserves plugin and AppStore dependencies in the
    generated `pyproject.toml`;
  - sync failure leaves `manifest.sciqlop_version` unchanged on disk;
  - manifest-save failure after a successful sync is reported distinctly;
  - concurrent calls for the same workspace: one succeeds, the other fails
    fast with the lock error (deterministic test, not timing-based);
  - `prepare_workspace(manifest=...)` produces identical output to the
    existing no-argument call for an unrelated existing workspace (guards
    against regressing current callers).
- `welcome/backend.py`: pytest-qt test on the new slots and signals,
  covering the Python slot/result contract directly (not just "a signal
  fired") — including active-workspace detection and the current-pin field
  in `_workspace_to_dict()`.

## Open items for the implementation plan

- Exact lock-file mechanism (stdlib `O_CREAT|O_EXCL` + staleness check vs. a
  small new dependency) — decide during implementation; no new dependency
  unless the hand-rolled version proves awkward.
- Whether to add a short in-memory cache for `fetch_available_versions()` to
  avoid a PyPI request every time the details panel opens — nice-to-have,
  not required for v1.
