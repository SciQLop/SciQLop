# Code Review Backlog — 2026-05-03

Findings from a multi-agent review of `user_api/`, `components/{catalogs,plotting,settings,workspaces,plugins}/`, `core/`, and built-in `plugins/`. Each item has a confidence score from the reviewer and a file:line anchor. Order within each section is roughly impact-first.

## Tier 1 — Critical bugs

- [ ] **C1. `PlotPanel.plots` unguarded `_impl` access** *(user_api, conf 85)*
  `SciQLop/user_api/plot/_panel.py:344` — uses `self._impl` instead of `self._get_impl_or_raise()`. After Qt destroy, raises `AttributeError` instead of `ValueError`.

- [ ] ~~**C2. `PlotPanel.time_range` setter double-updates child plots**~~ — **withdrawn**: commit 880e5c59 added that loop deliberately ("Fix PlotPanel.time_range setter to propagate to all subplots"). `set_time_axis_range` does NOT propagate to subplots; the loop is load-bearing. Reviewer's premise was wrong.

- [ ] **C3. `EventTableModel` meta-signal binding is fragile across `set_context`** *(catalogs, conf 95)*
  `SciQLop/components/catalogs/ui/event_table.py:95-104, 131-142` — `set_context` does not (re)bind `event_meta_changed`; only `set_events` does. Move `_connect_provider_meta_signal` into `set_context`.

- [ ] **C4. Per-pixel sort during span drag** *(catalogs, conf 88)*
  `SciQLop/components/catalogs/backend/provider.py:330-334` — `_on_event_range_changed` sorts the full event list on every `range_changed` tick. Defer with the same 10 ms timer pattern used by `TscatEvent._apply_changes`, or only sort on commit.

- [ ] **C5. `_DataSpan` leaks `time_range_changed` connection** *(plotting, conf 95)*
  `SciQLop/components/plotting/ui/knob_inspector/plot_items.py:86-87, 139-140` — `cleanup()` doesn't disconnect; orphan callback hits `set_range` on a deleted widget → `RuntimeError`.

- [ ] **C6. `create_plot_items` leaks `knobs_changed` connection** *(plotting, conf 92)*
  Same file, lines 191-196 — closure over items survives `cleanup()`. Disconnect during `_dispose_graph_knobs` / `_dispose_layer`.

- [ ] **C7. `_PLOT_REGISTRIES` keyed by C++ pointer addresses** *(plotting, conf 82)*
  `SciQLop/components/plotting/ui/time_sync_panel.py:42-115` — silent `destroyed`-connect skip at lines 113-114 leaks registries; new plot at the same address inherits stale hints.

- [ ] **C8. `ConfigEntry.__init__` propagates `ValidationError` on stale YAML** *(settings, conf 90)*
  `SciQLop/components/settings/backend/entry.py:134-143` — only YAML parse errors caught; Pydantic validation errors from old/extra keys break the whole settings load. Wrap and recover with defaults + save.

- [ ] **C9. `load_all` constructs `SciQLopPluginsSettings` twice (lost writes risk)** *(plugins, conf 85)*
  `SciQLop/components/plugins/backend/loader/loader.py:147-148` — call `plugins_folders()` before entering the `with`, or pass `settings` in.

- [ ] **C10. `Worker`/`background_load` is broken** *(plugins, conf 92)*
  Same file, lines 53, 101 — `result.emit(*self.fn(...))` over a non-tuple return. Either fix to emit `(name, module)` or remove the dead path.

- [ ] **C11. `ThreadStorage` implementation hazards (NOT a functional bug — it's a deliberate `threading.local()` workaround)** *(speasy_provider)*
  `SciQLop/plugins/speasy_provider/speasy_provider.py:83-97` — exists to work around [diskcache#295](https://github.com/grantjenks/python-diskcache/issues/295) (recycled pool threads thrash SQLite connections). Functional in production but:
  (a) class-level `_storage = {}` makes all instances share the same dict (latent, only one instance today);
  (b) `self._storage = {}` in `__init__` routes through the override → stores a `'_storage': {}` key inside the per-thread dict instead of creating an instance attribute;
  (c) no `__delattr__` → diskcache's `delattr(self._local, 'con')` (`diskcache/core.py:2347`) silently no-ops, leaving a dead connection on cross-PID forks;
  (d) no comment linking the issue.
  Fix: `object.__setattr__(self, "_storage", {})` in `__init__`, drop the class annotation, add `__delattr__`, add a docstring with the issue link.

- [ ] ~~**C12. `_on_action_done` counter underflow**~~ — **withdrawn**: agent assumed one decrement but `add_event` submits two `_TRACKED_ACTIONS` (`CreateEntityAction` + `AddEventsToCatalogueAction`), so two decrements pair the two increments (`_tracked_action` + `_link_to_catalog`). Verified by reproducer: counter starts 0 → after `add_event` is 2 → after both `_on_action_done` is 0.

## Tier 2 — Important bugs

- [ ] **I1. `ensure_arrays_of_double` returns a generator** *(user_api, conf 90)*
  `SciQLop/user_api/plot/_graphs.py:33` — `tuple(...)` instead of generator expression; one-shot consumption is a footgun.

- [ ] **I2. `PlotPanel.remove_plot` is an empty stub** *(user_api, conf 80)*
  `SciQLop/user_api/plot/_panel.py:286-287` — implement or `raise NotImplementedError`. Missing `@on_main_thread` either way.

- [ ] **I3. `ProjectionPlot` doesn't inherit `_BasePlot`** *(user_api, conf 80)*
  `SciQLop/user_api/plot/_plots.py:429-482` — no `destroyed` wiring → dangling Shiboken pointer. Stub setters lack `@on_main_thread`.

- [ ] ~~**I4. `_apply_changes` race drops second edit**~~ — **withdrawn**: no data-loss path. The setters update `self._start/self._stop` immediately; `_pending_*` are only flags. `_apply_changes` reads `self._start/self._stop` (always current) for dispatch. Qt single-threaded event loop means no re-entry. Even with nested events during `tscat_model.do()`, the setter has already updated `self._start`; the next timer fire sees `_pending_start=None` and returns without re-dispatching.

- [ ] **I5. `EventTableDelegate._column_type` O(N) scan on first edit** *(catalogs, conf 80)*
  `SciQLop/components/catalogs/ui/event_table_delegate.py:144-155` — sample first 100 rows for untyped columns.

- [ ] **I6. `_on_catalog_selected` doesn't short-circuit re-selection** *(catalogs, conf 80)*
  `SciQLop/components/catalogs/ui/catalog_browser.py:283-309` — `if node.catalog is self._current_catalog: return`.

- [ ] **I7. `ColumnVisibilityPopover` fires `visibility_changed` on drag-reorder** *(catalogs, conf 80)*
  `SciQLop/components/catalogs/ui/column_visibility_popover.py:115-118` — block `itemChanged` during row moves.

- [ ] **I8. `_build_color_by_menu` bypasses the loaded model** *(catalogs, conf 82)*
  `SciQLop/components/catalogs/ui/catalog_browser.py:762-764` — read from `self._event_model._events` instead of `catalog.provider.events(catalog)` (which can be empty for async-loaded catalogs).

- [ ] **I9. `_dispose_layer` / `_disconnect_watchers` not RuntimeError-safe** *(plotting, conf 83)*
  `SciQLop/components/plotting/ui/time_sync_panel.py:546-563` and `SciQLop/user_api/layers/_renderer.py:271` — wrap `graph_list_changed.disconnect` to handle dead C++ wrappers.

- [ ] **I10. `_specgram_callback` returns wrong shape on exception** *(plotting, conf 88)*
  `SciQLop/components/plotting/ui/time_sync_panel.py:210-225` — return `(empty, empty, empty)` instead of `[]` to avoid downstream unpack errors.

- [ ] ~~**I11. `panel_template.apply` reads `graph.name` instead of `graph.name()`**~~ — **withdrawn after API truth-check**: on a graph instance, `g.name` returns a `str` directly (Shiboken auto-property). Verified at runtime: `type(g.name) → str`, `callable(g.name) → False`. Code is correct.

- [ ] **I12. `ConfigEntry.__init__` emits `changed` per field during construction** *(settings, conf 83)*
  `SciQLop/components/settings/backend/entry.py:108-111` — observer ordering hazard. Suppress until `__init__` completes.

- [ ] **I13. `duplicate_workspace` collides on repeat + ignores `background`** *(workspaces, conf 82)*
  `SciQLop/components/workspaces/backend/workspaces_manager.py:187-195` — fixed `_copy` suffix raises `FileExistsError`; result never registered or switched to.

- [ ] **I14. `_ensure_migrated` re-runs `restore_legacy_json` on every list call** *(workspaces, conf 80)*
  Same file, lines 26-36 — gate on existence of `workspace.json` first.

- [ ] **I15. `PluginsDictDelegate._load_plugin_descriptions` re-scans on each settings open** *(settings, conf 80)*
  `SciQLop/components/settings/ui/settings_delegates/__init__.py:501-514` — cache module-level or attach to `loaded_plugins`.

- [ ] **I16. `sciqlop_app()` returns foreign `QApplication` silently** *(core, conf 85)*
  `SciQLop/core/sciqlop_application.py:94-99` — assert `isinstance(..., SciQLopApp)`.

- [ ] **I17. `_deferred_load` captures `catalog_model` reference for up to 5 s** *(tscat, conf 80)*
  `SciQLop/plugins/tscat_catalogs/tscat_provider.py:387-400` — weakref or validate before `rowCount()`.

- [ ] **I18. `unique_names` grows monotonically** *(core, conf 80)*
  `SciQLop/core/unique_names.py:1-28` — add `release_name(name)` and call from panel/plot teardown.

## Tier 3 — Refactors

- [ ] **R1. Merge `_plot_product_callback` and `_specgram_callback`** — common base; subclasses only override `__call__` body.
- [ ] **R2. Deduplicate `_find_panel`** — defined identically in `user_api/layers/_renderer.py:34` and `components/plotting/ui/knob_inspector/plot_items.py:40`.
- [ ] **R3. Extract `_post_plot(...)` from `plot_product`** — collapses Scalar/Vector vs Spectrogram if/elif.
- [ ] **R4. Move shared `attribute_spec` defaults (rating/author/tags) into `CatalogProvider`** — currently duplicated in `tscat_provider.py:210-225` and `cocat_provider.py:519-533`.
- [ ] ~~**R5. Replace `ThreadStorage` with `threading.local()`**~~ — **withdrawn**: `ThreadStorage` is a deliberate workaround for [diskcache#295](https://github.com/grantjenks/python-diskcache/issues/295). Use `threading.local()` would re-introduce the bug. See C11 for the right cleanup.

## Tier 4 — User API improvements (backwards-compatible)

- [ ] **A1. Export knob submodules in `__all__`** *(user_api, conf 80)*
  `SciQLop/user_api/knobs/__init__.py:34-41` — add `marker`, `specs`, `values`, `introspection` so IPython tab-completion finds them.

- [ ] **A2. Implement (or explicitly raise) `remove_plot`** — see I2.

- [ ] **A3. `ProjectionPlot` parity with `_BasePlot`** — inherit and add `@on_main_thread` to stubs (see I3). Add real implementations where SciQLopPlots supports them; document gaps where it doesn't (e.g. `set_time_range` no-op per memory note).

- [ ] ~~**A4. Drop the redundant `findChildren` re-lookup in `add_layer`**~~ — **withdrawn after API truth-check**: verified at runtime that `panel.plots()` returns `SciQLopPlotInterfacePtr` (interface), while `findChildren(SciQLopPlot)` returns the patched `SciQLopPlot` instance. The loop is load-bearing.

## Tier 5 — Hygiene

- [ ] **H1. Type-hint bug** — `speasy_provider.py:100` uses `List[str] or None` (always evaluates to `List[str]`). Should be `Optional[List[str]]`.
- [ ] **H2. Verify per-event signal connections in `EventTableModel`** are still load-bearing (per memory `catalog-event-table-perf-pitfalls.md`) before any model-signal refactor.

## Notes

- Items C5/C6/C7 form a coherent cleanup-leak cluster in the plot-knob/inspector path; fixing C7 should include explicit `weakref` or pyobject-id keying instead of address keying.
- Items C8/I12/I15 cluster around `ConfigEntry`; consider tackling together.
- Items C11/R5/H1 are all in `speasy_provider.py` — single PR.
- Items I13/I14 are workspace lifecycle — single PR.
