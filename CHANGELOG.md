# Changelog

## [v0.11.2](https://github.com/SciQlop/SciQLop/tree/v0.11.2) (2026-04-12)

[Full Changelog](https://github.com/SciQlop/SciQLop/compare/v0.11.1...v0.11.2)

### Bug fixes

- Fixed macOS v0.11.1 DMGs failing to launch with `different Team IDs` error: the new codesign pass did not re-sign Qt framework inner Mach-O binaries (e.g. `QtCore.framework/Versions/A/QtCore`), leaving them signed with Qt Company's Team ID while the outer app carried ours. Frameworks are now signed with `codesign --deep` so all inner binaries are re-signed with the Developer ID.

## [v0.11.1](https://github.com/SciQlop/SciQLop/tree/v0.11.1) (2026-04-12)

[Full Changelog](https://github.com/SciQlop/SciQLop/compare/v0.11.0...v0.11.1)

### Bug fixes

- Fixed missing icons for remote catalogs (speasy cloud) and collaborative catalogs (link/link_off) in bundled builds — icon PNGs were referenced but never committed
- Fixed macOS codesign hanging in CI when the build keychain auto-relocked mid-build; switched to `apple-actions/import-codesign-certs` which keeps the keychain unlocked for the entire job
- Fixed flake8 F821 errors on `main` by gating forward-reference imports behind `TYPE_CHECKING` and bumping minimum Python to 3.11
- Fixed appstore picking the wrong plugin version when the version index is not sorted ascending — now uses `packaging.version.parse` max
- Fixed Windows Store MSIX pre-processing rejection (`0x800700C1`) by stripping non-PE artifacts (Unix shell scripts, `.a`/`.o`/`.so`/`.dylib`) from the bundle and validating every `.exe`/`.dll`/`.pyd` has the MZ magic bytes

## [v0.11.0](https://github.com/SciQlop/SciQLop/tree/v0.11.0) (2026-04-11)

[Full Changelog](https://github.com/SciQlop/SciQLop/compare/v0.10.4...v0.11.0)

### New features

- **Catalog system rewrite**: New provider-based catalog architecture with capability-gated UI (create, rename, delete catalogs and events), tree/table split view browser, per-catalog color-coded overlays on plot panels, folder-based catalog paths, dirty tracking with deferred save, and jump-to-event navigation
- **Catalog browser improvements**: Context menu with New Catalog/New Folder, folder creation via placeholders, node type icons, placeholder type enum
- **Catalog user API**: Full CRUD API for catalogs from the Jupyter console — `catalogs.list()`, `catalogs.get()`, `catalogs.create()`, `catalogs.save()`, `catalogs.remove()`
- **Collaborative catalogs**: Real-time catalog co-editing via cocat (CRDT/WebSocket), ported to new provider API
- **Cocat multi-room provider**: Collaborative catalog provider now supports multiple rooms with on-demand joining and path-based catalog creation
- **Welcome page redesign**: Migrated to QWebEngineView + QWebChannel + Jinja2, two-column layout with hero workspace, news feed, featured packages, quickstart shortcuts, example browser with workspace picker modal
- **Welcome page workspace editing**: Workspace name and description editable from the details panel; package management with add/remove controls (installs immediately for active workspace, saves to manifest for inactive ones); resizable details panel; active workspace badge; latest GitHub release banner with update-available alert
- **App Store panel**: New dock panel for browsing community plugins with tab bar, search, tag filtering, sort, and detail panel (mock data, UI ready)
- **Workspace management overhaul**: Migrated workspace metadata from `workspace.json` (JSON) to `workspace.sciqlop` (TOML) with `WorkspaceManifest`, filesystem-based timestamps, auto-migration of old workspaces, auto-start JupyterLab for non-default workspaces
- **Workspace launcher**: Rewritten as workspace-aware supervisor process with venv isolation, plugin dependency resolution via uv, workspace switching (exit code 65), `.sciqlop`/`.sciqlop-archive` file associations, freedesktop MIME type and desktop entry
- **Product tree context menu**: Right-click on products in the tree to plot them ([\#70](https://github.com/SciQLop/SciQLop/issues/70))
- **Fluent plot panel API**: New declarative API for constructing plot panels from the Jupyter console (`user_api`)
- **Speasy plot backend**: SciQLop registers as a `speasy` plot backend — `speasy.plot()` renders directly into SciQLop panels
- **Speasy catalog integration**: Speasy inventory catalogs and timetables exposed as read-only catalog providers
- **Jupyter integration improvements**: Extracted `KernelManager` for kernel lifecycle, adaptive kernel poller, hardened subprocess cleanup with graceful termination escalation
- **Command palette**: Ctrl+K fuzzy command palette with QAction harvesting, multi-step argument chains, LRU history, and product plotting integration
- **Virtual product `%%vp` magic**: Cell magic for defining virtual products with type annotations (`Scalar`, `Vector["Bx","By","Bz"]`), `--debug` workbench mode with diagnostic overlays, hot-reload via `MutableCallback`
- **Settings system**: New Pydantic-based settings with category/subcategory organization, YAML persistence, and type-based UI delegate registry
- **Theming**: Dark palette support with automatic icon inversion based on current palette, styled QSplitter
- Per-event color mapping for catalog overlays: right-click a catalog → "Color by..." to color spans by a metadata column (categorical or continuous with matplotlib colormaps)

### Bug fixes

- Fixed non-deterministic catalog overlay colors — `hash()` replaced with `md5` for stable cross-process results
- Fixed `SignalRateLimiter` double-firing callback when both regular and max-delay timers expired
- Fixed missing `await` on `leave_room()` in collaborative catalog client
- Fixed sorted event list not re-sorted after drag-editing an event range
- Fixed `ConfigEntry` crash when loading an empty YAML file
- Fixed `ReadOnlySpecFile` asserting wrong variable on construction
- Fixed experimental collaboration plugin `self._ws` never assigned (WebSocket unreachable)
- Added `psutil` as declared dependency
- Fixed `logging.debug` call in `ExtraColumnsProxyModel` silently dropping arguments
- Fixed async plugin shutdown — cleanup now happens in `closeEvent` while event loop is alive, not in `aboutToQuit`
- Patched qasync to handle infinite timer delays (`anyio.sleep_forever()`)
- Fixed qasync exit code propagation — store on app instance since `exec()` doesn't return Qt's code
- Fixed workspace switching always landing on default workspace (double-import and env var issues)
- Fixed `list_existing_workspaces` default-dir comparison bug
- Fixed catalog event editing loop, table refresh, and double span creation
- Fixed catalog provider signal disconnection on unregister
- Fixed tscat datetime handling for naive/aware mismatches and ordering validation
- Fixed tscat catalog creation in folders and PySide6 enum deprecation warnings
- Fixed catalog `_folder_path` deduplication and parent expansion before inline edit
- Fixed lazy event loading for large catalogs (>=5000 events)
- Fixed JupyterLab file download support
- Fixed time range forwarding and label propagation in speasy plot backend
- Fixed `datetime64` conversion to epoch seconds in speasy backend
- Clear error message when speasy backend is used outside SciQLop

### Refactoring

- Reorganized codebase from layer-based to component-based structure (`core/` → `components/`)
- Moved workspace infrastructure and examples from `core/` to `components/workspaces/backend/`
- Moved plugin dependency resolution from `core/` to `components/plugins/`
- Removed dead code: old Qt widget welcome page subtree, `WorkspaceSpec`/`WorkspaceSpecFile`, unused core modules (`python.py`, `ExtraColumnsProxyModel.py`, `datetime_range.py`, `flow_layout.py`, `mpl_panel.py`, `time_span.py`), dead functions (`find_available_port`, `combine_colors`, `got_text` signal, 6 unused terminal message functions), simplified `from_json` API
- Renamed Jupyter `IPythonKernel/` to `kernel/`
- Modernized QSS theme to match welcome page design language
- Excluded speasy catalogs and timetables from the product tree (moved to catalog providers)

### Testing

- **Story-driven UI testing framework**: Declarative `@ui_action` decorator with narrative templates, `StoryRunner` for scripted tests and Hypothesis `RuleBasedStateMachine` for fuzzing — produces human-readable failure stories and pseudo-code reproducers
- Migrated plot and command palette workflow tests to story-driven API
- CI uploads fuzzer story artifacts on test failure

### Dependencies

- Bumped PySide6 to 6.10.2
- Added uv as a dependency
- Added hypothesis for stateful UI testing
- Frozen Jupyter packages for stability
- Added keyring for credential storage

## [v0.10.0](https://github.com/SciQlop/SciQLop/tree/v0.10.0) (2025-09-22)

[Full Changelog](https://github.com/SciQlop/SciQLop/compare/v0.9.4...v0.10.0)

**Implemented enhancements:**

- Investigate if BriefCase can be a solution to distribute SciQLop [\#68](https://github.com/SciQLop/SciQLop/issues/68)

## [v0.9.4](https://github.com/SciQlop/SciQLop/tree/v0.9.4) (2025-06-03)

[Full Changelog](https://github.com/SciQlop/SciQLop/compare/v0.9.3...v0.9.4)

**Implemented enhancements:**

- edit curve colors graphically from the inspector [\#41](https://github.com/SciQLop/SciQLop/issues/41)

**Closed issues:**

- Support older versions of numpy for PyHC environment inclusion? [\#67](https://github.com/SciQLop/SciQLop/issues/67)

## [v0.9.3](https://github.com/SciQlop/SciQLop/tree/v0.9.3) (2025-05-20)

[Full Changelog](https://github.com/SciQlop/SciQLop/compare/v0.9.2...v0.9.3)

## [v0.9.2](https://github.com/SciQlop/SciQLop/tree/v0.9.2) (2025-05-15)

[Full Changelog](https://github.com/SciQlop/SciQLop/compare/v0.9.1...v0.9.2)

## [v0.9.1](https://github.com/SciQlop/SciQLop/tree/v0.9.1) (2025-05-13)

[Full Changelog](https://github.com/SciQlop/SciQLop/compare/v0.9.0...v0.9.1)

## [v0.9.0](https://github.com/SciQlop/SciQLop/tree/v0.9.0) (2025-05-09)

[Full Changelog](https://github.com/SciQlop/SciQLop/compare/v0.8.1...v0.9.0)

**Fixed bugs:**

- Dev install and JupyterLab [\#64](https://github.com/SciQLop/SciQLop/issues/64)
- Time ax disappears when I delete the last plot [\#54](https://github.com/SciQLop/SciQLop/issues/54)
- AppImage terminal fork bomb [\#50](https://github.com/SciQLop/SciQLop/issues/50)
- plot list in inspector not synchronized with plot actually displayed  [\#36](https://github.com/SciQLop/SciQLop/issues/36)
- App crash [\#27](https://github.com/SciQLop/SciQLop/issues/27)

**Closed issues:**

- Error launching sciqlop [\#63](https://github.com/SciQLop/SciQLop/issues/63)
- Catalogs disappear after app crashes \#51 [\#51](https://github.com/SciQLop/SciQLop/issues/51)

**Merged pull requests:**

- Plot api v0.10 [\#62](https://github.com/SciQLop/SciQLop/pull/62) ([jeandet](https://github.com/jeandet))

## [v0.8.1](https://github.com/SciQlop/SciQLop/tree/v0.8.1) (2024-06-11)

[Full Changelog](https://github.com/SciQlop/SciQLop/compare/v0.8.0...v0.8.1)

## [v0.8.0](https://github.com/SciQlop/SciQLop/tree/v0.8.0) (2024-06-11)

[Full Changelog](https://github.com/SciQlop/SciQLop/compare/v0.7.1...v0.8.0)

**Implemented enhancements:**

- Delete event from plot [\#31](https://github.com/SciQLop/SciQLop/issues/31)

**Fixed bugs:**

- event marker appears only on 1 plot panel [\#35](https://github.com/SciQLop/SciQLop/issues/35)
- Main app window resized automatically [\#33](https://github.com/SciQLop/SciQLop/issues/33)
- Closing welcome panel causes crash [\#32](https://github.com/SciQLop/SciQLop/issues/32)

## [v0.7.1](https://github.com/SciQlop/SciQLop/tree/v0.7.1) (2024-04-10)

[Full Changelog](https://github.com/SciQlop/SciQLop/compare/v0.7.0...v0.7.1)

## [v0.7.0](https://github.com/SciQlop/SciQLop/tree/v0.7.0) (2024-04-10)

[Full Changelog](https://github.com/SciQlop/SciQLop/compare/v0.6.0...v0.7.0)

## [v0.6.0](https://github.com/SciQlop/SciQLop/tree/v0.6.0) (2024-03-25)

[Full Changelog](https://github.com/SciQlop/SciQLop/compare/v0.5.5...v0.6.0)

**Implemented enhancements:**

- truncated plot legend  [\#30](https://github.com/SciQLop/SciQLop/issues/30)
- speed up events display on data [\#20](https://github.com/SciQLop/SciQLop/issues/20)

## [v0.5.5](https://github.com/SciQlop/SciQLop/tree/v0.5.5) (2024-02-09)

[Full Changelog](https://github.com/SciQlop/SciQLop/compare/v0.5.4...v0.5.5)

**Merged pull requests:**

- update readme [\#28](https://github.com/SciQLop/SciQLop/pull/28) ([nicolasaunai](https://github.com/nicolasaunai))

## [v0.5.4](https://github.com/SciQlop/SciQLop/tree/v0.5.4) (2024-02-07)

[Full Changelog](https://github.com/SciQlop/SciQLop/compare/v0.5.3...v0.5.4)

## [v0.5.3](https://github.com/SciQlop/SciQLop/tree/v0.5.3) (2024-02-07)

[Full Changelog](https://github.com/SciQlop/SciQLop/compare/v0.5.2...v0.5.3)

## [v0.5.2](https://github.com/SciQlop/SciQLop/tree/v0.5.2) (2024-02-07)

[Full Changelog](https://github.com/SciQlop/SciQLop/compare/v0.5.1...v0.5.2)

## [v0.5.1](https://github.com/SciQlop/SciQLop/tree/v0.5.1) (2024-02-07)

[Full Changelog](https://github.com/SciQlop/SciQLop/compare/v0.5.0...v0.5.1)

## [v0.5.0](https://github.com/SciQlop/SciQLop/tree/v0.5.0) (2024-02-07)

[Full Changelog](https://github.com/SciQlop/SciQLop/compare/v0.4.1...v0.5.0)

**Implemented enhancements:**

- delete virtual products  [\#24](https://github.com/SciQLop/SciQLop/issues/24)
- virtual product registration duplicate paths [\#23](https://github.com/SciQLop/SciQLop/issues/23)

## [v0.4.1](https://github.com/SciQlop/SciQLop/tree/v0.4.1) (2023-06-13)

[Full Changelog](https://github.com/SciQlop/SciQLop/compare/v0.4.0...v0.4.1)

**Implemented enhancements:**

- colored span with color per catalog [\#14](https://github.com/SciQLop/SciQLop/issues/14)
- align spectros with time series plots [\#12](https://github.com/SciQLop/SciQLop/issues/12)

## [v0.4.0](https://github.com/SciQlop/SciQLop/tree/v0.4.0) (2023-06-12)

[Full Changelog](https://github.com/SciQlop/SciQLop/compare/v0.3.0...v0.4.0)

**Implemented enhancements:**

- create and edit events graphically [\#11](https://github.com/SciQLop/SciQLop/issues/11)

## [v0.3.0](https://github.com/SciQlop/SciQLop/tree/v0.3.0) (2023-06-04)

[Full Changelog](https://github.com/SciQlop/SciQLop/compare/v0.2.1...v0.3.0)

## [v0.2.1](https://github.com/SciQlop/SciQLop/tree/v0.2.1) (2023-04-25)

[Full Changelog](https://github.com/SciQlop/SciQLop/compare/v0.1.1...v0.2.1)

## [v0.1.1](https://github.com/SciQlop/SciQLop/tree/v0.1.1) (2023-03-15)

[Full Changelog](https://github.com/SciQlop/SciQLop/compare/v0.1.0...v0.1.1)

**Closed issues:**

- Spectrograms [\#2](https://github.com/SciQLop/SciQLop/issues/2)

## [v0.1.0](https://github.com/SciQlop/SciQLop/tree/v0.1.0) (2022-11-29)

[Full Changelog](https://github.com/SciQlop/SciQLop/compare/zenodo-test...v0.1.0)

**Closed issues:**

- test-matrix [\#3](https://github.com/SciQLop/SciQLop/issues/3)

**Merged pull requests:**

- Switch to PySide2 [\#5](https://github.com/SciQLop/SciQLop/pull/5) ([jeandet](https://github.com/jeandet))

## [zenodo-test](https://github.com/SciQlop/SciQLop/tree/zenodo-test) (2020-01-10)

[Full Changelog](https://github.com/SciQlop/SciQLop/compare/5cbbc595e8f3bc4044e55c3ff967e6a4178f5b4d...zenodo-test)



\* *This Changelog was automatically generated by [github_changelog_generator](https://github.com/github-changelog-generator/github-changelog-generator)*
