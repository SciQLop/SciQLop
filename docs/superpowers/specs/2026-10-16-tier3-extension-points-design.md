# Tier 3 extension points — design

Status: approved in conversation 2026-10-16 (approach A, two sections); revised after an opencode review the same day. Parent spec:
`docs/superpowers/specs/2026-10-14-plugin-extension-points-design.md` (§4.3 Tier 3 rows, §6 unload readiness).

## 1. Goal

Plugins can contribute quickstart shortcuts, guided tours, smart-search domains, catalog providers, template file
formats, time-range presets and themes. Everything a plugin contributed goes away when it is withdrawn, and the UI
follows. Every duplicated list (template suffixes ×6, palette names ×3, duration presets ×3) comes from one
extension point.

No Tier 3 item is driven by a concrete plugin request yet: the designs stay minimal.

Out of scope (parent spec §4.3 Tier 3, left for later): `value_editors` (four tables with different key types),
`welcome_sections` (the welcome page has no generic section format), `colormaps` (plot gradients are a C++ enum in
SciQLopPlots), `icons` (`register_icon` already works; owner tagging can follow when a plugin needs unload).

## 2. Decisions

| Question | Decision |
|---|---|
| Source of truth | The extension point. The existing public functions become thin wrappers that contribute under the current owner (approach A; same as Tier 2 settings and docks). |
| Existing callers | Unchanged: `add_quickstart_shortcut`, `register_tour`/`get_tour`/`all_tours`, `register_domain`/`unregister_domain`, subclassing `CatalogProvider`, `CatalogRegistry` methods and signals, `user_api.themes`. `sciqlop_msa`'s provider keeps working. |
| Consumers | Follow the point's `added`/`removed` signals; process-lifetime signals connect to guarded bound slots (`shiboken6.isValid(self)`), per `docs/qt-lifetime-patterns.md`. |
| Threads | The plan 3a wrappers can be called from any thread: notebook cells and agent tools run on the kernel thread or a worker (an AI labelling pipeline building a `CatalogProvider`, for example). Each wrapper captures `current_owner()` on the calling thread and contributes through an `@on_main_thread` helper with that owner, the `register_agent_backend` pattern. Limit: before the kernel installs the cross-thread invoker, `on_main_thread` runs the call in place, so a worker thread at startup still gets `WrongThread`. |
| Plans | 3a: quickstart, tours, search domains, catalog providers (§3). 3b: template formats, time presets, themes (§4). |

## 3. Existing registries (plan 3a)

### 3.1 `sciqlop.quickstart`

- `QuickstartShortcut(name, description, icon, callback)`, key `name`.
- `sciqlop_app().add_quickstart_shortcut(...)` contributes one; `quickstart_shortcuts()` and
  `quickstart_shortcut(name)` read the point. `quickstart_shortcut(name)` keeps returning a dict
  (`{"name", "description", "icon", "callback"}`): the welcome backend subscripts it (welcome/backend.py:274-279,
  502-505). `quickstart_shortcuts_added` keeps its `Signal(str)` payload, the name.
- The welcome page refreshes on `removed` too (today only on additions; a withdrawn plugin's shortcut stays).
- The test harness snapshots and restores the point instead of `app._quickstart_shortcuts`.

### 3.2 `sciqlop.tours`

- The existing `Tour`, key `id`.
- The checks now in `register_tour` (no steps, duplicate step ids) move to `Tour.__post_init__`, so a direct
  contribution is checked too.
  The error messages stay as they are ("has no steps", "duplicate step_id values").
- `register_tour`, `get_tour`, `all_tours` wrap the point. Behaviour change: the same owner registering the same id
  again replaces it instead of raising; another owner's id still raises (`DuplicateContribution`).
  `tests/test_onboarding_registry.py::test_register_tour_rejects_duplicate_id` changes accordingly.
- The test-only helpers (`_forget_tour_for_tests`, `_reset_registry_for_tests`) act on the point.

### 3.3 `sciqlop.search_domains`

- The existing `SearchDomain` protocol, marked `@runtime_checkable` for the contribution type check; key `name`.
- `register_domain`/`unregister_domain` wrap the point, from any thread (§2 Threads).
- `SmartSearchRegistry` (created lazily) takes the domains already contributed when it is created, and follows
  `added`/`removed`: `removed` drops the domain's index and reindex timer (today's `unregister_domain` body).

### 3.4 `sciqlop.catalog_providers`

- `CatalogProvider` instances, keyed by instance as `f"{provider.name}#{id(provider):x}"` (readable in error messages):
  today two providers may share a name, and a name key would make the second replace or fail.
- `CatalogProvider.__init__` keeps registering itself through `CatalogRegistry.register`, the single path into the
  point, now under the current owner; registering twice stays a no-op.
- `CatalogRegistry` keeps `register`, `unregister`, `providers`, `provider_by_name`, `all_catalogs` and its signals
  `provider_registered`/`provider_unregistered`, driven by the point. Its call sites (79 references in 25 files) do not
  change. The `destroyed` connection moves with it.
- Withdrawal unregisters the plugin's providers; their catalogs leave the tree. Deleting the provider object stays the
  plugin's job.
- A provider destroyed without `unregister` is removed from the point too, and, as today (`_on_destroyed`),
  `provider_unregistered` is not emitted for it: its slots would be handed a dead object.
- Providers may be built off the main thread (a notebook cell, an agent tool, a labelling pipeline): `register`,
  `unregister` and the destroyed handler reach the point through the main thread (§2 Threads). The provider object
  keeps the thread affinity it was built with, as today.

## 4. Hard-coded lists (plan 3b)

### 4.1 `sciqlop.template_formats`

- `TemplateFormat(id, label, suffixes: tuple[str, ...], loads: Callable[[str], dict], dumps: Callable[[dict], str])`.
- Core formats: `json` (`.json`), `yaml` (`.yaml`, `.yml`, with today's tuple-aware SafeLoader subclass).
- All six sites derive from it: `_read_template_data`, `PanelTemplate.to_file`, `_TEMPLATE_EXTENSIONS`
  (`list_templates`, `find_template_file`), `user_api/templates.py`, `PlotPanel.save_template`
  (user_api/plot/_panel.py:921-923), and the welcome page's import file filter.
- The core reader and writer raise `ValueError` listing the supported suffixes for an unknown one;
  `user_api/templates.py` keeps falling back to a template name lookup. "Save as template" still writes `.json`.
- Withdrawal: templates in that format stop being listed; their files are untouched.

### 4.2 `sciqlop.time_presets`

- `TimePreset(id, label, seconds)`.
- The three duration tables derive from it: the time-range bar's duration combo (`DURATION_PRESETS`), the command
  palette's `TimeRangeArg` completions, and `_do_set_time_range`'s `durations` table in `commands.py` (default: the
  `1d` preset).
- Core presets keep the bar's ids, so `panel.duration = "7d"` keeps working (the setter is `setCurrentText`, a silent
  no-op for an unknown label): 1m, 1h, 12h, 1d, 7d, plus 1M (30 days) from the palette. Visible changes: the bar gains
  1M; the palette offers all six, displayed as "Last <label>", with `7d` instead of `1w`.
  `tests/test_time_range_bar.py` expects the new list.
- Open bars rebuild their combo on `added`/`removed`, keeping the current selection.
- Zoom limits (`ZOOM_LIMIT_PRESETS`) stay core-only: they bound the zoom, they are not time ranges.

### 4.3 `sciqlop.themes`

- `Theme(id, label, palette: dict[str, str] | Path)`; a path must be an existing `.yaml` that parses to a mapping,
  checked on contribute.
- Core themes: the 8 files in `resources/palettes`.
- The palette loader resolves names through the point: `_load_palette`/`setup_palette` (theming/palette.py:25-60)
  read the theme's dict or `.yaml` path instead of `palettes_path/<name>.yaml`; an unknown name or unreadable file
  falls back to `space` (today the `open` is outside the `try`, so a missing file raises). The core themes are
  contributed when `theming` is imported, so the import-time `SCIQLOP_PALETTE` binding still finds them.
- The three name lists derive from it:
  - the settings combo: `json_schema_extra` gains `"choices_from": "<extension point id>"`; the combo delegate reads
    that point's keys and repopulates on `added`/`removed` (guarded slot), since the settings page is built at
    startup, before plugins contribute. `SciQLopStyle.color_palette` uses `"choices_from": "sciqlop.themes"`;
  - `user_api.themes.list_themes()` and `apply_theme` validate against the point;
  - `PaletteName` becomes `str` (a `Literal` cannot list plugin themes).
- Startup: if the saved theme is not contributed yet (its plugin loads later), SciQLop starts with the default
  `space`, and applies the saved theme as soon as it is contributed. The saved setting is never overwritten by a
  fallback.
- Withdrawal of the active theme: switch to `space`, keep the setting (the theme comes back on the next start with
  that plugin).
- The per-palette icon cache dir is chosen from the active theme, not from the saved setting (icons.py:229 reads the
  setting today, which would be wrong while a plugin theme is pending).

## 5. Testing

- Each point: contribute, withdraw (`remove_owner`), and the old function still works through it.
- Quickstart: the welcome backend reports the change on removal.
- Search domains: a withdrawn domain's index and timer are dropped.
- Catalog providers: a withdrawn provider's catalogs leave the catalog tree; a provider subclass used the way
  `sciqlop_msa` does still registers and lists its catalogs; a destroyed provider leaves the point.
- Template formats: a plugin format round-trips a template through `to_file`/`from_file` and is listed.
- Time presets: a plugin preset shows in an open bar and in the palette completions, and leaves on withdrawal.
- Themes: a plugin theme (dict and path forms) loads; it shows in an already-built settings combo; one contributed
  after startup while saved is applied; its withdrawal falls back to `space` and keeps the setting; an unknown saved
  name starts on `space`.
- Interop: one test plugin contributes one of each of the seven points through `ctx` and is withdrawn.

## 6. Documentation

Same commit as the code (parent spec §7): `sciqlop-plugin-design` skill `references/plugin-contract.md` (EP list) and
`references/ui-and-settings.md`; global `sciqlop-user-api.md` (`list_themes`, `PaletteName`); the parent spec's §4.3
Tier 3 rows marked implemented.
