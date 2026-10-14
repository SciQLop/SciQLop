# Plugin extension points and collaboration — design

Date: 2026-10-14. Status: design, not implemented.
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
| Where contributions are declared | In code, during `load(ctx)`. `plugin.json` carries dependencies and a `provides` summary for the app store. |
| Plugin dependencies | SciQLop resolves them by plugin id and version. pip never decides which plugins are installed; it only installs `python_dependencies`. |
| Packaged plugins | Every plugin ships a `plugin.json`, including pip/GitHub-installed ones (found next to the entry-point module). |

## 3. Plugin contract

### 3.1 plugin.json

```json
{
  "name": "vdf_study",
  "version": "1.0.0",
  "python_dependencies": ["numpy>=2"],
  "dependencies": ["vdf>=1.2,<2", "earth"],
  "optional_dependencies": ["mars"],
  "provides": {
    "product_kinds": [],
    "plot_kinds": [],
    "extension_points": [],
    "panel_kinds": ["vdf_study.event_panel"]
  }
}
```

- `dependencies` / `optional_dependencies`: plugin names with PEP 440 specifiers checked against the
  other plugin's `version`.
- `provides`: summary only; the code is the truth. After `load`, the loader compares what the plugin
  registered with `provides` and logs a warning on mismatch; a test helper turns it into a failure.
- A packaged plugin (entry point in group `sciqlop.plugins`) ships `plugin.json` next to the module the
  entry point names. Without one it loads as today: no plugin dependencies, empty `provides`.

### 3.2 Loading

1. Read every enabled plugin's `plugin.json` (folder and entry-point plugins alike).
2. Topologically sort by `dependencies` and present `optional_dependencies`.
3. Refuse a plugin whose required dependency is missing, out of range, failed, or in a cycle.
   The message names the dependency and the reason. Its dependents are refused in turn.
4. Phase 1: `load(ctx)` for each plugin in order. It declares its EPs, contributes, returns its API.
5. Phase 2: `ready(ctx)` (optional) for each plugin, after all phase-1 calls. It reads what others contributed.

Live install (app store, `%install`) runs the same steps for the new plugin and its missing dependencies.
Before installing, the app store and `%install` read the new plugin's `dependencies`, offer to install
the missing ones, or refuse with the same reason the loader would give.

### 3.3 `ctx` (one per plugin)

| Member | Meaning |
|---|---|
| `ctx.name`, `ctx.version`, `ctx.main_window` | identity; `main_window` keeps old plugins working |
| `ctx.extension_point(id, type, doc)` | declare an EP owned by this plugin; `id` must start with `ctx.name.` |
| `ctx.contribute(ep_id, item)` | add `item` to an EP; owner = this plugin |
| `ctx.plugin(name)` | the API (return value of `load`) of a plugin listed in `dependencies`/`optional_dependencies`; raises otherwise |
| `ctx.has(name)` | whether an optional dependency is loaded |

Optional-dependency code lives in its own module, imported only when `ctx.has(...)`:

```python
def load(ctx):
    ctx.contribute("sciqlop.plot_kinds", vdf_slice_plot)
    if ctx.has("mars"):
        from .with_mars import register
        register(ctx)
    return VdfApi()
```

Backward compatibility: only a first parameter named exactly `ctx` opts into this contract; any other
`load(...)` is called with the main window as today. Such a plugin cannot declare EPs, its
registrations are owned by "legacy:<name>", and it has no `ready` phase.
The kernel `plugins` namespace keeps exposing each plugin's API.

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

- Every contribution has an `id` of the form `<plugin>.<name>` (core uses `sciqlop.`). Ids are stable:
  saved panels and templates reference them, and the prefix names the plugin to install when missing.
- Duplicate id from the same owner replaces (hot reload, `%%vp`); from another owner it raises.
- Mutations happen on the main thread (`@on_main_thread` at the user_api boundary, like today).
- Discovery: `sciqlop.extensions.get(ep_id)` from anywhere (kernel, user_api); plugins use `ctx`.
- Growth path: the existing scenes `Registry` (components/scenes/registry.py) plus owner, removal, signals.

### 4.2 Data contracts

The most valuable EPs: independent producers and consumers interoperate through them (Grafana data
frames, Home Assistant entity domains).

- `sciqlop.product_kinds`: `ProductKind(id, label, contract, validate, default_plot_kind)`.
  Core kinds: `sciqlop.scalar`, `sciqlop.vector`, `sciqlop.multicomponent`, `sciqlop.spectrogram`,
  `scenes.scene`, `scenes.boundary`, `sciqlop.layer`. One id replaces the four parallel encodings
  (strings, `VirtualProductType`, `ParameterType`, `GraphType`).
- `sciqlop.source_kinds`: where a graph's data comes from (`sciqlop.speasy`, `sciqlop.vp`,
  `sciqlop.function`, `sciqlop.static`, plugin-defined). Carries tooltip, inspector line, template
  reference, shareable flag, python snippet. Providers declare their source kind; no `isinstance`.

### 4.3 Catalogue

Tier 1 is the first implementation plan. Tiers 2 and 3 follow, each its own plan, with this contract.

| Tier | EP | Replaces |
|---|---|---|
| 1 | `sciqlop.product_kinds` | ~12 product-type dispatch sites (time_sync_panel, plot_remote, easy_provider, virtual_products, data_types, layers renderer) |
| 1 | `sciqlop.source_kinds` | `GraphContext.kind` Literal and its 6 if-chains |
| 1 | `sciqlop.data_providers` | `providers` dict (gains unregister) |
| 1 | `sciqlop.mime_types` | `register_mime` and its two bypasses (event list, product list) |
| 1 | `sciqlop.plot_kinds` | `_plot_product` branches, remote plot branch, user_api plot/graph type mapping, scene dispatch |
| 1 | `sciqlop.drop_rules` | scenes drop `_TABLE`, panel DnD callbacks, catalog tree drops |
| 1 | `sciqlop.panel_kinds` (tree format only) | `new_plot_panel(backend="native")` |
| 1 | `scenes.bodies/boundaries/scenes` | scenes registries; `planetary_scenes` contributes like a third party |
| 2 | `sciqlop.commands`, `sciqlop.menus`, `sciqlop.shortcuts` | CommandRegistry, QAction harvest, panel_menus, fixed product-tree / export / graph / catalog menus |
| 2 | `sciqlop.export_targets` | Export submenu, `PlotPanel.save` formats, proxy share |
| 2 | `sciqlop.inspector_sections` | core-only `add_inspector_extension` |
| 2 | `sciqlop.agent_tools`, `sciqlop.agent_backends`, `sciqlop.agent_skills` | fixed tool list, backend dict, package-only skills dir |
| 2 | `sciqlop.magics`, `sciqlop.kernel_namespace` | fixed magics list, ad-hoc `push_variables` |
| 2 | `sciqlop.workspace_sections`, `sciqlop.docks`, `sciqlop.settings` | fixed manifest tables, `add_side_pan`, ConfigEntry auto-registration (keeps working, gains owner) |
| 2 | `sciqlop.layers`, `sciqlop.virtual_products` | VPRegistry and LayerRegistry (near copies) on one hot-reload EP |
| 3 | `sciqlop.value_editors` | settings delegates + knob widgets (4 type→widget tables) |
| 3 | `sciqlop.themes`, `sciqlop.icons`, `sciqlop.colormaps`, `sciqlop.time_presets` | palette names ×3, icons, colormap lists, range presets |
| 3 | `sciqlop.template_formats`, `sciqlop.welcome_sections`, `sciqlop.quickstart`, `sciqlop.tours`, `sciqlop.search_domains`, `sciqlop.catalog_providers` | template extensions ×3, fixed welcome page, tours, search domains, CatalogRegistry |

Menus follow VS Code: an action is a command registered once; a menu entry places a command at a
location (`panel`, `panel.export`, `graph`, `product_tree`, `catalog_tree`, `main.tools`) with a
`when(context)` predicate.

## 5. Panels as trees

A panel is a tree of nodes `{kind, id, config, slots}`:

```yaml
kind: sciqlop.time_panel
config: {time_range: [2015-10-16T13:00, 2015-10-16T14:00]}
slots:
  plots:
    - {kind: sciqlop.timeseries, config: {product: "speasy//amda/.../b_gse"}}
    - {kind: vdf.slice_plot,     config: {product: "vdf//mms1/dis", plane: XY}}
    - {kind: scenes.projection,  config: {scene: earth.gsm, trajectories: [mms1]}}
```

- Every node kind is a contribution (`panel_kinds`, `plot_kinds`); each knows `to_config`/`from_config`.
- `user_api` builds panels by node kind: `panel.add("vdf.slice_plot", product=...)`. Drops, menus and
  plugins call these same functions, so manual and programmatic composition share one path.
- Restore resolves each kind; a missing kind becomes a placeholder naming the plugin (from the id
  prefix) with an app-store "install it?" offer (lookup through `provides` in the store index).
- Templates and workspaces store the tree; templates v2 (per-graph entries) is the starting point,
  read by a migration like the existing v1→v2 rewrite.
- Panel kinds, slots (`plots`, `chrome.actions`, `chrome.options`, `chrome.toolbar`) and chrome
  injection are designed in detail in the panels sub-project; the tree format above is fixed now.

## 6. Unload readiness

Registrations go through `ctx`, so each has an owner. `unload(name)` = `remove_owner` on every EP,
in reverse dependency order, after the plugin's dependents. Consumers that cache contributions listen
to `removed` (IntelliJ dynamic-plugin rule). Not exposed in this design: disabling asks for a restart.

## 7. Migration rules

- `user_api` is published: every existing `register_*` function keeps its signature and becomes a thin
  adapter onto its EP (owner taken from the calling plugin's `ctx` when known, else "user").
- One EP at a time; each migration removes its hard-coded dispatch in the same change.
- Scenes migrate first, as proof that a plugin contributes exactly like a third party would.

## 8. Errors

- Missing/out-of-range/failed dependency: plugin refused; message names the dependency, the
  installed version and the requested range. Shown in the plugin list and the log.
- `ctx.plugin(name)` without a declared dependency: `UndeclaredDependency` naming both plugins.
- Contribution of the wrong type, or duplicate id from another owner: raises at `contribute`.
- Unknown kind on restore: placeholder node, never a silent drop.

## 9. Issues found while surveying (to fix early)

1. `WorkspaceManifest.load/save` keep only the four known tables: any other table in a `.sciqlop`
   file is lost on the next save (verified 2026-10-14, workspace_manifest.py:97-184). Blocks
   `workspace_sections`; fix in Tier 1.
2. Graphs from a third-party DataProvider get source kind "speasy" (time_sync_panel.py:831). Unverified.
3. QActions added by a live-loaded plugin never reach the command palette (harvest runs once). Unverified.

## 10. Testing

- Loader: dependency ordering, cycles, ranges, optional deps, refusal cascade, `provides` drift helper.
- `ExtensionPoint`: contract check, duplicate policy, `remove_owner`, signals.
- Interop proof: two test plugins, one declaring a product kind + plot kind, one building a panel from
  them through `ctx.plugin` and `user_api`; the panel round-trips through the tree format.
- Scenes migration: existing scenes tests pass unchanged; `planetary_scenes` contributes via `ctx`.

## 11. Out of scope (with the trigger that would bring each in)

- Service tokens (JupyterLab): when two plugins must provide the same interface and the user picks one.
- Manifest-declared contributions with lazy import (VS Code/napari): when startup time or app-store
  browsing needs capabilities without importing plugins.
- Hot unload in the UI: when a user workflow needs it; §6 keeps it possible.
- Panel kinds and chrome injection details: panels sub-project, driven by the first real VDF panel.
