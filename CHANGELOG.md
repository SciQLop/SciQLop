# Changelog

## Unreleased

### Bug fixes

- Fixed SciQLop aborting startup with an error dialog when the workspace dependency sync cannot reach the network (closes #115). `prepare_workspace` now treats a `uv sync` failure as a recoverable warning when the workspace venv exists, so users can still launch offline (e.g. on a plane) and use bundled features such as the CDF plugin and local files. A real venv breakage (no `python` executable) still propagates as before.

### Catalogs

- Removed the standalone "Open Catalogue Explorer" toolbar action shipped by the tscat plugin. The embedded TSCatGUI window duplicated functionality already covered (and surpassed) by SciQLop's native catalog browser, and was misleading for users who expected the two surfaces to stay in sync. The dedicated TSCatGUI window is still reachable on demand via right-click on the *My Catalogs* row in the catalog browser → "Open in TSCat editor…", routed through the existing `CatalogProvider.actions()` extension point so any provider can publish its own backend-specific UI the same way.
- Drag & drop events between catalogs. Default = link (event appears in both catalogs, single UUID; tscat's many-to-many is honored). Hold **Shift** to move (remove from source). Hold **Ctrl** to duplicate (new UUID, independent copy). Cross-provider drops always duplicate. Implemented via a new `EVENT_LIST_MIME_TYPE`, a `CatalogProvider.handle_event_drop(target_catalog, events, action, source_catalog)` hook, and a dispatcher in the catalog tree that derives the action from the keyboard modifiers held during the drop.

### Snippet generation refactor (Jinja2 templates)

- "Copy Python code" snippets (Speasy notebook + reproducer, VP reproducer, panel/plot reproducers) are now rendered from Jinja2 templates under `SciQLop/core/snippets/templates/` instead of inline string concatenation. Public surface: `SciQLop.core.snippets.render_snippet` and `SciQLop.core.snippets.format_product_path`.
- Generated snippets emit the double-slash-joined product path (`"speasy//amda//ACE//b_gsm"`) instead of a Python list literal, and drop the implicit `"root"` prefix. `//` is required because product names can contain `/` (e.g. AMDA's `"final / prelim"`); `to_product_path` prefers `//` when present so the round-trip stays lossless. `ProductsModel::node` strips a leading `"root"` — purely a producer-side cleanup.

### Editable event metadata in the catalog browser

- Made the event table the primary surface for inspecting *and* editing per-event metadata. Cells become editable when the provider declares `Capability.EDIT_EVENTS`; tscat and cocat write through to their respective backends (tscat via `SetAttributeAction`, cocat via CRDT `set_attributes`). Speasy events stay read-only.
- Type-aware editor widgets reused from the settings delegate registry: `bool`/`int`/`float`/`str` columns get the matching `SettingDelegate`; `start`/`stop` get a `QDateTimeEdit`. Column types are inferred from current values and cached.
- Multi-row selection with bulk-edit propagation: edit one cell with N rows selected and the value is applied to every selected row in the same column via `provider.set_events_meta`. Bulk delete removes every selected event in one operation. Re-entry guard prevents propagation from re-triggering itself.
- "Columns" toolbar button (and right-click on the table header) opens a popover with a search box, a checkable + drag-reorderable list of columns, and Show all / Hide all / Reset actions. Frozen columns (`start`, `stop`) are listed but cannot be hidden.
- Per-catalog column visibility and order persisted in a new `EventTableViewState` `ConfigEntry` keyed by `catalog.uuid`, written to user settings (YAML). Pure UI concern — does not sync via cocat CRDT.
- "+ Attribute" toolbar button prompts for a new metadata key and applies it (with empty value) to the selected events, or to every event if no selection is active. New keys auto-extend the table via `event_meta_changed` + `beginInsertColumns` (selection and scroll position survive).
- Backend additions on `CatalogProvider`: new `event_meta_changed = Signal(catalog, event, key)`, plus `set_event_meta`, `remove_event_meta`, `set_events_meta` (default delegates to `set_event_meta` so subclass overrides apply transparently). `CatalogEvent` gains `meta_changed = Signal(str)` and `set_meta` / `remove_meta` methods. Closes backlog items #21 (multi-selection + bulk edit) and #22 (event metadata display/edition).

### Knobs (parameterized data products)

- Added runtime-tunable parameters to virtual products and speasy templated parameters. Python VP callbacks can declare `Annotated[T, Knob(...)]` kwargs; speasy-templated parameters auto-expose their `ArgumentIndex` choices. Spec: `docs/superpowers/specs/2026-04-18-parameterized-virtual-products-design.md`.
- Public API surface: `SciQLop.user_api.knobs` (`Knob`, `KnobSpec`, `IntKnob`, `FloatKnob`, `BoolKnob`, `ChoiceKnob`, `StringKnob`, `validate_dict`, `canonical_hash`, `defaults_for`). Providers pass knob values through the existing `plot_product` callback; re-fetch is signal-driven.
- Inspector "Parameters" section with per-knob delegates (debounced or manual-apply) and a reset-to-defaults action in the panel context menu.
- `%%vp --debug` preserves knob values across re-plots by snapshotting `GraphKnobState` entries before clearing and restoring them after, so the user's tuning survives cell re-evaluation. When a Jupyter widget comm is attached, the magic also emits a best-effort `ipywidgets` strip bound bidirectionally to the graph state.
- Beyond scalar/choice knobs, added widget-bound variants: `TimeRangeKnob` renders as a panel-wide vertical span anchored to the view (the fractional default is re-resolved when the time axis changes), `ThresholdKnob` renders as a draggable horizontal line, and `DatetimeKnob` provides a datetime editor reused as a catalog attribute type.

### Annotation layers

- New annotation-layer system: a callable can be registered as a *layer* that receives data and returns a list of `Marker(time, value)`, `Span(start, stop)` or `HLine(value)` annotations to draw on a plot. Public types live in `SciQLop.user_api.layers` (`Marker`, `Span`, `HLine`, `register_layer`, `LayerProvider`).
- Three entry points: `@register_layer("path/in/tree")` decorator (auto-registers in the product tree as a `LayerProvider`), the `%%layer` cell magic that wraps the cell body into a registered layer, and the fluent `panel.layer(layer_callable, source=graph_or_product)` / `panel.add_layer(...)` API on `PlotPanel`. Layers can also be drag-and-dropped from the product tree onto a plot; the existing `ProductDnDCallback` routes them to the renderer.
- Runtime layer registry with hot-reload: re-evaluating a `%%layer` cell (or re-importing a module that uses `@register_layer`) replaces the layer in place without leaving stale entries in the product tree.
- Layer callbacks are typed by their data container: `Marker[float]`, `Span[float]`, `HLine[float]` accept either raw `SpeasyVariable` slices, plain ndarrays, or knob-tunable inputs (`Annotated[T, Knob(...)]` works inside layers too). The renderer infers the annotation type from the return value at first call and stays scope-aware so layers attached at the panel level vs. the graph level render in the right axes.
- Bug fixes shipped alongside: orphaned span widgets are now removed when a layer is deleted, scatter markers honor color overrides, the inspector reads the layer's user-visible name correctly, and speasy-attached layers re-fetch their data when their knobs change.

### Graph context metadata + "Copy Python code"

- Every plotted graph now carries a `GraphContext` envelope (Pydantic) capturing how it was produced: provider id, product path, knob values, callback identity, and a hash of the inputs. The envelope is attached on `_post_plot` for speasy/VP graphs, on `plot_static_data` and `plot_function` for the static/functional paths, and re-attached on knob changes via the `update_knobs` slot. Public surface lives in `SciQLop.core.graph_context` (schema, `attach_context`, `context_of`, `rich_of`, `provider_for`).
- Right-click menu on any plot now offers "Copy Python code" entries for each graph, generated by the graph's provider via the new `DataProvider.python_snippets(ctx, graph=None) -> dict[label, snippet]` and `extended_metadata(ctx) -> dict` hooks. Speasy graphs ship two snippet variants: *Reproduce in SciQLop* (`panel.plot_product(<path>, ...)`) and *Notebook (matplotlib)* (`import speasy as spz; v.plot(ax=ax)`). Virtual products ship a three-tier *Reproduce in SciQLop* snippet: importable callbacks expand to `from x import y` calls, lambdas/closures fall back to a comment stub, and unknown sources omit the entry.
- Hover tooltip on each plot summarizes the graph context (product, knob values, last fetch shape/dtype). Inspector tree rows gain a "Graph context" extension with the same fields plus a copyable code snippet panel; both update live when the time axis pans/zooms via `graph.parent().time_axis().range()`.

### Plot API extensions (`SciQLop.user_api`)

- New `Histogram2D` plottable + `panel.histogram2d(x, y, ...)` shortcut on `PlotPanel`, plus `histogram2d()` methods on `XYPlot` and `TimeSeriesPlot`. Routed through `to_plottable` so the standard `panel.plot(...)` dispatch picks it up automatically.
- New `Overlay` wrapper class (`SciQLop.user_api.plot.Overlay`) exposing the C++ overlay surface as a Pythonic property on every plot: `plot.overlay = Overlay(text=..., level=Level.Plot, position=Position.TopLeft, size_mode=SizeMode.Auto)`. Overlay enums (`Level`, `SizeMode`, `Position`) and the `Overlay` class are re-exported from `SciQLop.user_api.plot`.
- New `dsp` facade (`SciQLop.user_api.dsp`) wrapping 13 SciQLopPlots DSP primitives with `SpeasyVariable` round-trip semantics: `filtfilt`, `sosfiltfilt`, `fir_filter`, `iir_sos`, `interpolate_nan`, `rolling_mean`, `rolling_std`, `resample`, `fft`, `spectrogram`, `reduce`, `reduce_axes`, `split_segments`. A typed `dsp._arrays` pass-through layer is exposed for callers that need ndarray semantics directly. Three new tutorial notebooks cover overlay, histogram2D, and DSP usage.

### Runtime tracing & Perfetto profiling

- New runtime tracer accessible from **Tools › Profiling**: start/stop a Chrome-trace JSON capture, open it in https://ui.perfetto.dev/ via the "Open trace in Perfetto" entry. The trace is served from localhost and never leaves the machine — Perfetto runs entirely client-side. Capture can also be started before the GUI by setting the `SCIQLOP_TRACE` environment variable.
- Wrapped tracer module `SciQLop.core.tracing` (re-exported as `SciQLop.user_api.tracing`) over the upstream `SciQLopPlots.tracing` C++ surface, with auto thread naming (Python thread name → Qt `objectName()` fallback → synthetic `worker-N`) and a `traced(...)` decorator that handles `async def` callables and selective parameter capture. Falls back to no-ops when SciQLopPlots ships without the tracing submodule.
- Zones instrumented in the data path: `plot.replot`, `plot.replot.dispatch`, `provider._get_data`, `provider.get_data`, `provider.post_process`, `speasy.get_data`, `speasy.fill_nan`, plus `set_data` conversion vs. C++ submission split.
- Speasy internals are now traced via runtime monkey-patches (no speasy fork required): `speasy.cache.{with_cache, fetch_fragment_group, wait_pending}`, `speasy.cache.unversioned.{with_cache, split_fragments}`, `speasy.proxy.{is_up, version, get_product, get_inventory}`, `speasy.http.urlopen`, `speasy.file.{open, fetch_remote, list}`, `speasy.cdf.{read, load_variable, load_variables}`, `speasy.archive.get_product`, and `speasy.cda.{dl_variable, direct_archive}`. Each zone carries the matched product / URL / dataset as Perfetto args, splitting the formerly opaque `speasy.get_data` bar into a per-layer flame graph (cache vs. proxy vs. HTTP vs. CDF parse).

### Startup performance

- Splash window now paints almost immediately after launch instead of waiting for workspace resolution. The launcher used to import `SciQLop.components.workspaces.backend.settings` *before* showing the splash, which transitively pulled in `SciQLop.core`, `speasy.core`, matplotlib, scipy and IPython through an eager re-export chain in `workspaces/__init__.py`. The launcher now defers `resolve_workspace_dir` until after `window.show()`, and the `workspaces` package re-exports its public names lazily via PEP 562 `__getattr__`. The leaf settings import drops from ~3 s to ~140 ms (Linux warm cache) and importing the launcher loads zero heavy modules — the splash paints before any settings/speasy work runs (closes #119).

### AppStore

- AppStore now filters plugin entries by SciQLop version: each version's PEP 440 `sciqlop` specifier is matched against the running `SciQLop.__version__`. Incompatible versions disappear from the per-plugin version list, and a plugin with no compatible version is dropped from the listing entirely. Missing or malformed specifiers stay permissive so a broken metadata entry does not silently hide a plugin.

### Catalogs

- Drag & drop catalogs within the catalog browser tree (cross-provider copy + same-provider move). Cocat catalogs can be moved within the same room via a CRDT attribute mutation (`MOVE_CATALOG`); cross-room moves still need a cocat library primitive and remain unsupported.
- Drag & drop a catalog from the browser onto a plot panel adds it as an overlay — same gesture as drag-from-tree, no menu round-trip.
- New `CatalogProvider.attribute_spec` API for typed metadata schemas: providers can publish per-attribute types and constraints (rating, author, tags) that the event table delegate honors. Tscat and cocat ship default attribute_specs for `rating`/`author`/`tags`. User-added attribute schemas are persisted via catalog attributes (cocat-syncable) with a precedence chain (catalog override → provider default).
- New chip-style tag list editor for `list[str]` metadata columns; integrates with the existing `EventTableDelegate`.
- Cell display uses scientific notation for very small / very large floats (`< 1e-3` or `>= 1e6`) so wide floating-point values no longer break column auto-fit. Column auto-fit also samples a bounded number of rows instead of measuring every cell.
- Centralized default `attribute_spec` (rating/author/tags) on `CatalogProvider` so providers no longer redeclare them; browser/edit polish includes natural editing behavior on selected cells and a `+ Attribute` dialog with explicit type selection.

### Plotting & providers

- `PlotHints` are now provider-driven and aggregate across multiple products: when a plot panel hosts graphs from several providers, hints are merged via `provider.plot_hints(node)` per-graph rather than read once from the panel. Speasy graphs gain `SpeasyVariable.attrs` as ISTP fallback when the inventory metadata is sparse — labels and units now fall back to the variable's own attributes if the dataset metadata doesn't supply them.
- `_plot_items` now returns a `dispose` handle, and product callbacks have been factored to share a common base (Scalar/Vector vs. Spectrogram dispatch lives in one place).

### Speasy provider integration

- Each Speasy `ConfigSection` is now exposed as a SciQLop `ConfigEntry` subclass: fields, types, defaults, and descriptions are read from Speasy at import time and rendered in the Settings UI through the existing delegate registry. Loading and saving go through Speasy's config rather than a parallel YAML file, so the Settings UI now controls Speasy's runtime configuration directly (proxy URL, cache retention, preferred CDA access method, ...).

### Cleanups

- Dropped the `experimental_collaboration` plugin (superseded by `cocat_catalogs`); the historical wiring inside the launcher and main window is removed.
- Various small cleanups across loader, settings, workspaces, core, and `user_api`. The `KnobBadge` overlay and one-shot discoverability hint were attempted then reverted in favor of the inspector "Parameters" section.

### Dependencies

- PySide6 / shiboken6 6.11.0
- PySide6-QtAds 4.5.0.3
- SciQLopPlots 0.24.0 (was 0.21.0 in v0.11.4)

## [v0.11.4](https://github.com/SciQlop/SciQLop/tree/v0.11.4) (2026-04-14)

[Full Changelog](https://github.com/SciQlop/SciQLop/compare/v0.11.3...v0.11.4)

### Bug fixes (collaborative catalogs)

- Fixed remote CRDT updates (catalog create/delete/rename, event add/remove, event range edits) not propagating to the UI until the user left and rejoined the room. The cocat provider now subscribes to `DB.on_create_catalogue` and to each catalogue's `on_delete`/`on_change_name`/`on_add_events`/`on_remove_events` callbacks on join, and wires every wrapped event to `Event.on_change_range`. Local writes reorder wrapper state updates before the cocat call so the synchronous echo callbacks are idempotent no-ops.
- Fixed `CocatCatalogProvider` credentials not loading on macOS. The system keyring backend on macOS does not override `get_credential`, so the base-class lookup for `username=None` always returned `None` and stored passwords were unreachable on reload. The username is now persisted to YAML alongside the server URL and the password is fetched via `get_password(service, username)`. Existing Linux users with ≤0.11.3 YAML files (which never stored the username) fall back to `get_credential(service, None)` — supported by SecretService and Windows backends — and the username is written back to YAML on the next save, so no credentials are lost across the upgrade.

### Bug fixes (Windows MSIX)

- Fixed Windows Store certification failing on `v0.11.4.dev0` because `make_msix.ps1` concatenated `.0` onto the raw `pyproject.toml` version, producing `0.11.4.dev0.0` which violates the MSIX `{ushort}.{ushort}.{ushort}.{ushort}` format. The script now extracts the `major.minor.patch` prefix via regex and appends `.0` only to that.
- Fixed Windows Store certification "Sign returned error: 0x800700C1" on files with `.cat` extension. `astroquery.jplspec` and `astroquery.linelists` ship plain-text molecular-line catalog data files (`catdir.cat`, `partfunc.cat`) that the Store Sign preprocessor treats as Microsoft Authenticode Catalogs (PKCS#7) and fails to parse as ASN.1. Both subpackages are now stripped from the bundle — speasy only uses `astroquery.utils.tap.core.TapPlus`, so the removal is surgical. `bundle.ps1` also runs a local signtool preflight over every `.cat` in the staged bundle to catch this class of failure before submission.

## [v0.11.3](https://github.com/SciQlop/SciQLop/tree/v0.11.3) (2026-04-13)

[Full Changelog](https://github.com/SciQlop/SciQLop/compare/v0.11.2...v0.11.3)

### Bug fixes (catalogs)

- Fixed panels keeping stale `CatalogOverlay` instances after a catalog is deleted. `PanelCatalogManager` now listens to `CatalogProvider.catalog_removed` for every existing provider and for any provider registered later (via `CatalogRegistry.provider_registered`), and drops the corresponding overlay automatically. Previously deleting a catalog via the tree, a collaborative backend, or the user API left every panel still drawing that catalog's events and broke UUID-keyed menu toggling.
- Fixed collaborative catalog sub-paths collapsing to the room root. Nested catalog paths beneath a cocat room are now encoded into the catalogue's `sciqlop_path` attribute and decoded on load, so nested catalogs survive round-trips. Room-membership lookups tolerate nested segments.
- Fixed catalog tree not showing `New Catalog.../New Folder...` placeholders on rooms joined after capabilities were granted. When a provider re-emits `folder_added` with new capabilities (cocat on room join), the tree model now walks into the inserted folder and installs the placeholders.
- Tightened `catalogs` user API path parsing: mixed separators and single-slash paths now raise `ValueError` with a clear message instead of being silently mangled. The public contract is now `//`-only, e.g. `"Shared//room//Cat"`.

### Bug fixes

- Fixed welcome page always showing "update available" because `SciQLop.__version__` was hardcoded to `0.11.0` in `SciQLop/__init__.py` and never bumped for 0.11.1/0.11.2. Version is now read from package metadata via `importlib.metadata.version("SciQLop")`, so it tracks `pyproject.toml` automatically.
- Welcome page update banner now uses `packaging.version` (PEP 440) for the comparison instead of a naïve numeric per-segment compare in JavaScript. Pre-release/dev versions (`0.12.0.dev0`) are now ordered correctly relative to final releases.

### Tooling

- Migrated version bumping from legacy `bumpversion` (in `setup.cfg`) to `bump-my-version` configured in `pyproject.toml`. Single source of truth (`pyproject.toml`), supports PEP 440 dev releases (`0.12.0.dev0` → `.dev1` → … → `0.12.0`). See `[tool.bumpversion]` in `pyproject.toml` for the workflow.

### Bug fixes (Windows MSIX)

- Fixed Windows Store certification "Sign returned error: 0x800700C1" by stripping non-amd64 PE binaries from the MSIX bundle. `pip._vendor.distlib` (`w32.exe`, `w64-arm.exe`, `t32.exe`, `t64-arm.exe`) and `debugpy._vendored.pydevd` (`inject_dll_x86.exe`, `attach_x86.dll`, `run_code_on_dllmain_x86.dll`) ship i386/arm64 launcher stubs that are valid PEs for the wrong architecture — the v0.11.1 MZ-magic check passed them through. The validator now parses the PE header (`e_lfanew` → `PE\0\0` → `IMAGE_FILE_MACHINE_AMD64`) and removes anything that is not a valid x64 PE.

## [v0.11.2](https://github.com/SciQlop/SciQLop/tree/v0.11.2) (2026-04-12)

[Full Changelog](https://github.com/SciQlop/SciQLop/compare/v0.11.1...v0.11.2)

### Bug fixes (macOS bundle)

- Fixed bundled `python3` missing `LC_RPATH @executable_path/../lib`, which made `_lzma.so` (and other stdlib extensions linking against bundled dylibs via `@rpath`) fail to load at startup. Root cause was a bug in `make_bundle_portable.py` that passed basenames instead of full paths to the Mach-O detection helper, silently skipping every binary in `Resources/usr/local/bin/`.
- Fixed hardened-runtime library validation rejecting PySide6, shiboken6, numpy and other PyPI wheels loaded from the per-user workspace venv with `different Team IDs`. The bundled `python3` is now signed with `com.apple.security.cs.disable-library-validation`, `com.apple.security.cs.allow-dyld-environment-variables`, `com.apple.security.cs.allow-unsigned-executable-memory` and `com.apple.security.cs.allow-jit` (the last one fixes a V8 crash in `Chrome_InProcRendererThread` when the welcome page loads in QtWebEngine on Apple Silicon).
- Rewrote the macOS codesign pass to follow Apple TN2206 canonical inside-out signing: nested `.app` bundles deepest-first, loose Mach-Os outside `.app` and `.framework`, then each `*.framework/Versions/A` directory deepest-first (the canonical multi-version sign target — previously we were signing `Foo.framework` which left framework inner main binaries without secure timestamps), then the outer `SciQLop.app`. This fixes notarization rejection of `QtWebEngineCore.framework` (whose nested `Helpers/QtWebEngineProcess.app` made the previous re-seal pass corrupt the framework's main binary signature).
- The macOS `.app` is now notarized and stapled **before** being wrapped in the DMG, so the notarization ticket travels with the app into `/Applications`. Previously only the DMG was stapled, which made Gatekeeper fall back to an online ticket lookup on first launch and prompt "cannot verify".
- The CI bundle script now fails the build loudly if `notarytool` returns anything other than `status: Accepted` and dumps the `notarytool log` for the failing submission, instead of silently shipping unstapled or unnotarized DMGs.
- Pre-flight check verifies a `Developer ID Application:` certificate is in the keychain and matches `CODESIGN_IDENTITY` before starting the signing pass, failing fast on misconfigured CI secrets.

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
