# Plugin extension points and collaboration — design

Date: 2026-10-14. Status: design, not implemented. Revised after an opencode review (same day).
Research: cross-ecosystem survey (VS Code, IntelliJ, Eclipse/OSGi, Qt Creator, JupyterLab, Backstage,
Grafana, Home Assistant, WordPress, webpack Tapable, pluggy, Obsidian, Blender, napari) and an inventory
of SciQLop's 37 registration mechanisms and 48 hard-coded dispatch sites (summarised in §9).

## 1. Goal

Plugins contribute features and use each other's features. Users build by hand what plugins build in code.

Driving case: a VDF plugin adds a VDF product kind and a VDF plot; an Earth plugin adds magnetosphere
scenes and models; other plugins add other planets. A third plugin builds a panel with time series,
a VDF plot and an Earth scene. A user builds the same panel with drag and drop. The panel is saved
in a workspace or template and comes back on restore.

Third-party plugins can do everything bundled plugins do.

## 2. Decisions

| Topic | Decision |
|---|---|
| Mechanism | Typed extension points (EPs), one class for all. Composition of panels = EPs with a parent slot (Backstage idea, applied to panels only). No service-token DI for now. |
| Kind ownership | The plugin that introduces a kind (e.g. `vdf.distribution`) owns its contract and its EPs. A kind can move to core later. |
| Panel persistence | Declarative from day one: a panel is a tree of `{kind, config, slots}` nodes. |
| Unload | Every registration has an owner, so unload is possible later. For now disabling a plugin asks for a restart. |
| Where contributions are declared | In code, during `activate(ctx)`. `plugin.json` carries dependencies and a `provides` summary for the app store. |
| Plugin dependencies | SciQLop resolves them by plugin name and version. pip never decides which plugins are installed; it only installs `python_dependencies`. |
| Packaged plugins | Every plugin ships a `plugin.json`, including pip/GitHub-installed ones (found next to the entry-point module). |
| Plugin identity | The key SciQLop already uses everywhere (settings, `loaded_plugins`, the existing `dependencies` of collaborative_catalogs): the folder name, or the entry-point name for a packaged plugin. `plugin.json` `name` stays the display name ("Planetary scenes"). |
| API versioning | A plugin's `version` is its API version; plugins follow semver (breaking API change = major bump). No separate `api_version`. |

## 3. Plugin contract

### 3.1 plugin.json

```json
{
  "name": "VDF event study",
  "version": "1.0.0",
  "description": "Event study panels combining VDFs and Earth scenes",
  "authors": [{"name": "A. Author", "email": "a@lab.fr", "organization": "LPP"}],
  "license": "MIT",
  "python_dependencies": ["numpy>=2"],
  "dependencies": ["vdf>=1.2,<2", "planetary_scenes"],
  "optional_dependencies": ["mars"],
  "provides": {
    "product_kinds": [],
    "plot_kinds": ["vdf_study.event_overview"],
    "extension_points": []
  }
}
```

`PluginDesc` changes (plugin_desc.py): add `optional_dependencies: list[str]` and `provides: Provides`
(all lists default empty); `description`, `authors`, `license` become optional with empty defaults,
so a minimal `plugin.json` is `{"name", "version"}`. Unknown keys are reported as a warning, not
silently dropped.

- `dependencies` / `optional_dependencies`: plugin names with PEP 440 specifiers checked against the
  other plugin's `version`.
- `provides`: summary for the app store; the code is the truth. After activation the loader compares
  what the plugin registered with `provides` and warns on mismatch; a test helper turns it into a failure.
- A packaged plugin (entry point in group `sciqlop.plugins`) ships `plugin.json` next to the module the
  entry point names. Without one it loads as today: no plugin dependencies, empty `provides`.
- App store: the index generator (sciqlop-appstore repo) copies `dependencies`, `optional_dependencies`
  and `provides` from each release's `plugin.json` into `versions[]`. That is what makes "which plugin
  provides `vdf.slice_plot`?" answerable offline from the cached index.

### 3.2 Loading

1. Read every enabled plugin's `plugin.json` (folder and entry-point plugins alike), keyed by plugin id
   (folder or entry-point name).
2. Compute the load set: enabled plugins whose required dependencies are present and in range,
   recursively. Present optional dependencies join the ordering; absent ones are just absent.
3. Topologically sort on required + present optional dependencies; ties broken by `name`, so the order
   is the same on every machine.
4. Refuse a plugin whose required dependency is missing, out of range, failed, or in a cycle.
   The message names the dependency, the installed version and the requested range. Dependents are
   refused in turn.
5. Phase 1: `activate(ctx)` for each plugin in order. It declares EPs, contributes, returns its API.
   The loader records each plugin's state: `active`, `failed(reason)`, `refused(reason)`. A raising
   `activate` is `failed`, whatever it returned; a `None` return is a valid "no API".
6. Phase 2: `ready(ctx)` (optional), once per plugin, after every phase-1 call.

Live install (app store, `%install`, settings live loader) goes through the same resolver: read the
new plugin's `plugin.json`, offer to install missing plugin dependencies, refuse with the step-4
message otherwise, then run steps 5 and 6 for the new plugins only. Install success is reported only
when activation succeeded (today a failed hot-load can still report `ok`).

`ready` runs once. A plugin that keeps a view of an EP (a menu of plot kinds, a cache) must also
listen to the EP's `added` signal, because a live-installed plugin contributes after `ready` ran.

### 3.3 `activate(ctx)` and `ctx`

The new contract is a distinct function, `activate(ctx)` (VS Code naming). A module with `activate` gets
the new contract; a module with only `load(main_window)` keeps today's behaviour. No signature sniffing.

| Member | Meaning |
|---|---|
| `ctx.name`, `ctx.version`, `ctx.main_window` | plugin id (folder or entry-point name), version; main window for UI work |
| `ctx.extension_point(id, type, doc)` | declare an EP owned by this plugin; `id` must start with `ctx.name.` |
| `ctx.contribute(ep_id, item)` | add `item` to an EP; owner = this plugin |
| `ctx.plugin(name)` | the API of an active plugin listed in `dependencies`/`optional_dependencies`; raises `UndeclaredDependency` otherwise, `PluginUnavailable` if it is not active |
| `ctx.has(name)` | whether an optional dependency is active (reliable in `activate`, thanks to §3.2 step 3) |

Optional-dependency code lives in its own module, imported only when `ctx.has(...)`:

```python
def activate(ctx):
    ctx.contribute("sciqlop.plot_kinds", vdf_slice_plot)
    if ctx.has("mars"):
        from .with_mars import register
        register(ctx)
    return VdfApi()
```

Owners: an `activate` plugin owns its registrations under its `name`. A legacy `load(main_window)`
plugin's registrations (through user_api `register_*`) are owned by `legacy:<name>`: the loader sets a
"current plugin" context variable around each `load`/`activate` call, and adapters read it. Calls made
outside any plugin (notebook cells, agent tools) are owned by `user`. The kernel `plugins` namespace
keeps exposing each plugin's API.

## 4. Extension points

### 4.1 One class

```python
class ExtensionPoint(Generic[T]):
    id: str                       # "sciqlop.plot_kinds", "vdf.reconstruction_methods"
    contribution_type: type[T]    # dataclass, pydantic model or Protocol; checked on contribute
    def contribute(self, item: T, owner: str) -> T
    def get(self, id: str) -> T                 # NotRegistered(LookupError) names the EP and the id
    def list(self, **filters) -> list[T]
    def remove_owner(self, owner: str) -> list[T]
    added: Signal(T); removed: Signal(T)
```

- Every contribution has an `id` of the form `<owner plugin>.<name>`; core components use
  `sciqlop.<component>.<name>` (e.g. `sciqlop.scenes.projection`). Ids are stable: saved panels and
  templates reference them, and the prefix plus the store index's `provides` name the plugin to install.
- Duplicate id from the same owner replaces (hot reload, `%%vp`); from another owner it raises.
  Replacement does not update objects already built from the old contribution (open plots keep the
  old behaviour until rebuilt); this is acceptable while unload stays restart-based.
- Thread affinity: EPs are main-thread objects. `contribute` and `remove_owner` raise
  `WrongThread` off the main thread; signals are emitted on the main thread. user_api adapters and
  `ctx` marshal with `@on_main_thread`, as user_api does today. Reads (`get`, `list`) are main-thread too.
- Discovery: `sciqlop.extensions.get(ep_id)` from anywhere on the main thread; plugins use `ctx`.
- Growth path: the existing scenes `Registry` (components/scenes/registry.py) plus owner, removal, signals.

### 4.2 Data contracts

The most valuable EPs: independent producers and consumers interoperate through them (Grafana data
frames, Home Assistant entity domains).

- `sciqlop.product_kinds`: a product kind is a **data shape** — what a product's data looks like.
  `ProductKind(id, label, contract, validate, default_plot_kind)`. Core kinds: `sciqlop.scalar`,
  `sciqlop.vector`, `sciqlop.multicomponent`, `sciqlop.spectrogram`, plus the scenes kinds
  (`sciqlop.scenes.scene`, `sciqlop.scenes.boundary`) and `sciqlop.layer`.
  It is not a merge of the existing enums, which keep their meaning: `GraphType` stays the rendering
  choice inside a plot kind; Speasy's `ParameterType` is mapped to a product kind at the speasy provider
  boundary; the published `VirtualProductType` enum and `product_type` strings keep working and map to
  the core kind ids (`VirtualProductType.Vector` → `sciqlop.vector`). The ~12 dispatch sites read the
  kind id instead of switching on whichever encoding they hold today.
- `sciqlop.source_kinds`: where a graph's data comes from. Core ids keep today's persisted values as
  aliases: `speasy`, `vp`, `function`, `static` are read as `sciqlop.speasy`, `sciqlop.vp`,
  `sciqlop.function`, `sciqlop.static`, so graph envelopes saved in workspaces and templates still
  load. Carries tooltip, inspector line, template reference, shareable flag, python snippet. A provider
  declares its source kind; a provider that declares none gets a generic `sciqlop.provider` envelope
  instead of none (today such graphs get no context at all, time_sync_panel.py:858).

### 4.3 Catalogue

Tier 1 is implemented as three plans: 1a plugin contract + extension-point base + scenes
(docs/superpowers/plans/2026-10-14-plugin-contract-and-extension-points.md), 1b data contracts
(product kinds, source kinds, data providers, MIME types, the `sciqlop.provider` fallback), 1c plot kinds,
drop rules and the panel tree format. Tier 2 follows with this contract. Tier 3 is a list of
candidates migrated only when a plugin needs one or when the cleanup is touched anyway.

| Tier | EP | Replaces |
|---|---|---|
| 1 | `sciqlop.product_kinds` | ~12 product-type dispatch sites (time_sync_panel, plot_remote, easy_provider, virtual_products, data_types, layers renderer) |
| 1 | `sciqlop.source_kinds` | `GraphContext.kind` Literal and its 6 if-chains; missing envelope for third-party providers |
| 1 | `sciqlop.data_providers` | `providers` dict (gains unregister) |
| 1 | `sciqlop.mime_types` | `register_mime` and its two bypasses (event list, product list) |
| 1 | `sciqlop.plot_kinds` | `_plot_product` branches, remote plot branch, user_api plot/graph type mapping, scene dispatch |
| 1 | `sciqlop.drop_rules` | scenes drop `_TABLE`, panel DnD callbacks, catalog tree drops |
| 1 | `sciqlop.scenes.bodies/boundaries/scenes` | scenes registries; `planetary_scenes` contributes like a third party |
| 2 | `sciqlop.panel_kinds` + slots | `new_plot_panel(backend="native")`; designed in the panels sub-project |
| 2 | `sciqlop.commands`, `sciqlop.menus`, `sciqlop.shortcuts` | CommandRegistry, one-shot QAction harvest, panel_menus, fixed product-tree / export / graph / catalog menus |
| 2 | `sciqlop.export_targets` | Export submenu, `PlotPanel.save` formats, proxy share |
| 2 | `sciqlop.inspector_sections` | core-only `add_inspector_extension` |
| 2 | `sciqlop.agent_tools`, `sciqlop.agent_backends`, `sciqlop.agent_skills` | fixed tool list, backend dict, package-only skills dir |
| 2 | `sciqlop.magics`, `sciqlop.kernel_namespace` | fixed magics list, ad-hoc `push_variables`; these EPs replay their contributions when a kernel starts (the shell does not exist at activation) |
| 2 | `sciqlop.workspace_sections`, `sciqlop.docks`, `sciqlop.settings` | fixed manifest tables, `add_side_pan`, ConfigEntry auto-registration (keeps working, gains owner) |
| 2 | `sciqlop.layers`, `sciqlop.virtual_products` | VPRegistry and LayerRegistry (near copies) on one hot-reload EP |
| 3 | `sciqlop.value_editors` | settings delegates + knob widgets (4 type→widget tables) |
| 3 | `sciqlop.themes`, `sciqlop.icons`, `sciqlop.colormaps`, `sciqlop.time_presets` | palette names ×3, icons, colormap lists, range presets |
| 3 | `sciqlop.template_formats`, `sciqlop.welcome_sections`, `sciqlop.quickstart`, `sciqlop.tours`, `sciqlop.search_domains`, `sciqlop.catalog_providers` | template extensions ×3, fixed welcome page, tours, search domains, CatalogRegistry |

Menus follow VS Code: an action is a command registered once; a menu entry places a command at a
location (`panel`, `panel.export`, `graph`, `product_tree`, `catalog_tree`, `main.tools`) with a
`when(context)` predicate.

## 5. Panels as trees

Tier 1 fixes the format; panel kinds and slots beyond the existing time panel come with the panels
sub-project. A panel is a tree of nodes `{kind, id, config, slots}`:

```yaml
kind: sciqlop.time_panel
config: {time_range: [2015-10-16T13:00, 2015-10-16T14:00]}
slots:
  plots:
    - {kind: sciqlop.timeseries,        config: {product: "speasy//amda/.../b_gse"}}
    - {kind: vdf.slice_plot,            config: {product: "vdf//mms1/dis", plane: XY}}
    - {kind: sciqlop.scenes.projection, config: {scene: planetary_scenes.earth_gsm, trajectories: [mms1]}}
```

- Every node kind is a plot-kind contribution; each knows `to_config`/`from_config`.
- `user_api` builds panels by node kind: `panel.add("vdf.slice_plot", product=...)`. Drops, menus and
  plugins call these same functions, so manual and programmatic composition share one path.
- Restore resolves each kind; a missing kind becomes a placeholder naming the plugin (looked up in the
  cached store index by `provides`, else derived from the id prefix) with an "install it?" offer.
- Templates and workspaces store the tree; templates v2 (per-graph entries) is the starting point,
  read by a migration like the existing v1→v2 rewrite.

## 6. Unload readiness

Registrations go through `ctx` or carry the current-plugin owner (§3.3), so each has an owner.
`unload(name)` = `remove_owner` on every EP, in reverse dependency order, after the plugin's
dependents. Consumers that cache contributions listen to `removed` (IntelliJ dynamic-plugin rule).
Not exposed in this design: disabling asks for a restart.

## 7. Migration rules

- `user_api` is published: every existing `register_*` function keeps its signature, its side effects
  (e.g. `register_scene`/`register_boundary` add product-tree nodes, `register_layer` stays a decorator)
  and its `replace` behaviour; it becomes an adapter onto its EP.
- Persisted values keep loading: source-kind aliases (§4.2), templates v2 read-migration (§5), plugin
  settings keep their folder/entry-point keys (they already are the plugin ids).
- One EP at a time; each migration removes its hard-coded dispatch in the same change.
- Scenes migrate first, as proof that a plugin contributes exactly like a third party would.
- Plugin-author documentation moves with the code: every change that adds or migrates an EP updates
  the bundled agent skill `sciqlop-plugin-design` (SKILL.md and `references/packaging-and-testing.md`,
  `products-and-data.md`, `ui-and-settings.md`) in the same commit, plus the global
  `sciqlop-user-api.md` memory when a user_api signature changes. Tier 1 adds a reference page on
  `activate(ctx)`/`ready(ctx)`, `plugin.json` dependencies/`provides`, declaring an EP, and collaborating
  with another plugin; the existing skill-name test keeps the published tool names honest.

## 8. Errors

- Missing/out-of-range/failed dependency: plugin refused; message names the dependency, the
  installed version and the requested range. Shown in the plugin list, the log and the install report.
- `ctx.plugin(name)` without a declared dependency: `UndeclaredDependency` naming both plugins;
  declared but not active: `PluginUnavailable` with the dependency's state.
- Contribution of the wrong type, duplicate id from another owner, or a mutation off the main thread:
  raises at `contribute`.
- Unknown kind on restore: placeholder node, never a silent drop.

## 9. Issues found while surveying (to fix early)

1. `WorkspaceManifest.load/save` keep only the four known tables: any other table in a `.sciqlop`
   file is lost on the next save (verified, workspace_manifest.py:97-184). Fix in Tier 1.
2. A provider that is neither an EasyProvider nor named "Speasy" gets no graph context at all
   (verified, time_sync_panel.py:845-860): no inspector line, tooltip or knob persistence. Fixed by the
   `sciqlop.provider` fallback (§4.2) in Tier 1.
3. QActions added by a live-loaded plugin never reach the command palette: the harvest runs once,
   after `load_all` (verified by review, sciqlop_app.py:211, live_loader.py:63-69). Tier 2 commands.
4. The loader stores `load()`'s return only when truthy and swallows exceptions, so "loaded with no
   API" and "failed" look the same (loader.py:76-84). Fixed by the state tracking in §3.2 step 5.

## 10. Testing

- Loader: deterministic order, cycles, ranges, optional deps present/absent, refusal cascade, failed
  `activate`, `None` API, legacy `load(main_window)`, `provides` drift helper, live install through the
  same resolver.
- `ExtensionPoint`: contract check, duplicate policy, `remove_owner`, signals, `WrongThread`.
- Interop proof: two test plugins, one declaring a product kind + plot kind, one building a panel from
  them through `ctx.plugin` and `user_api`; the panel round-trips through the tree format; a plugin
  live-installed after `ready` shows up through `added`.
- Persistence: a workspace saved with legacy `kind` values reloads with its graph contexts intact.
- Scenes migration: existing scenes tests pass unchanged; `planetary_scenes` contributes via `ctx`.

## 11. Out of scope (with the trigger that would bring each in)

- Service tokens (JupyterLab): when two plugins must provide the same interface and the user picks one.
- Manifest-declared contributions with lazy import (VS Code/napari): when startup time or app-store
  browsing needs capabilities without importing plugins.
- Hot unload in the UI: when a user workflow needs it; §6 keeps it possible.
- Panel kinds, slots and chrome injection: panels sub-project, driven by the first real VDF panel.
- Tier 3 EPs: when a plugin asks for one, or when the code they replace is reworked anyway.

## 12. Review log

opencode review (2026-10-14), verified against the code. Applied: F1 fallback envelope, F2 PluginDesc
change, F3 owner rule, F4 loader states, F5 store index fields, F6 product kind = data shape (enums
kept), F7/F9 confirmed issues, F8 `sciqlop.<component>` prefix, D1 `activate(ctx)` instead of
parameter sniffing, D2/D6 load set + deterministic order, D3 `added` for caches, D4 live install through
the resolver, D5 kernel replay, D7 identity = folder/entry-point name (the review suggested `plugin.json` name, but that field is a display name today: "Planetary scenes"), D9 legacy kind aliases, D10
panel_kinds to Tier 2, D11 main-thread affinity, D12 replacement caveat.
Not applied: cutting `provides` (D8) — the user wants app-store visibility, so the store index carries
it instead; a separate `api_version` (F9) — semver on `version` is simpler and matches VS Code/Grafana;
cutting signals from the base (cut 4) — live install needs `added` in Tier 1.
