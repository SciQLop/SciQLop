# Panel kinds and panel extensions — design

Status: approved in conversation 2026-10-16 (approach A, three sections, plus the install offer). Parent spec:
`docs/superpowers/specs/2026-10-14-plugin-extension-points-design.md` (§4.3 row `sciqlop.panel_kinds` + slots, §5, §11).

## 1. Goal

Plugins can propose new kinds of panels, declared so that other plugins depending on them can open and save
them, and plugins can extend any panel, the base SciQLop time panel included, in whatever way they want.
A real 3D view, for example, is a panel kind of its own.

What SciQLop provides is only what a plugin cannot do alone:

1. a registry of panel kinds (list, open by id, depend on),
2. a hand-off of every panel, open and future, to the plugins that extend it, with their clean-up called on
   panel close and on withdrawal,
3. saving and restoring a panel as a tree, with a placeholder and an install offer when its plugin is missing.

SciQLop does not predefine slots, toolbars or chrome: an extension gets the panel widget itself. This replaces
the parent spec's "slots" (§5): the `slots` field of the tree stays (the time panel uses `slots.plots`), but no
slot API is designed.

Out of scope: arbitrary widgets as rows inside a time panel (`SciQLopMultiPlotPanel.add_plot` takes only
SciQLopPlots plots; trigger: a SciQLopPlots API for foreign rows); closing open panels when their kind is
withdrawn; workspaces saving open panels (only templates store trees today).

## 2. Decisions

| Question | Decision |
|---|---|
| What a panel kind returns | Any `QWidget`. SciQLop docks it like today's panels. |
| How a panel is opened | One function, `main_window.open_panel(kind_id, name=None, **config)`, used by the UI, `user_api`, templates and plugins. |
| The time panel | Core kind `sciqlop.time_panel` (already the root kind of template trees). `new_plot_panel()`, `create_plot_panel()` and the "+" button keep their behaviour and return types. |
| What an extension receives | The real Qt widget (for a time panel, the `TimeSyncPanel`). |
| Extension clean-up | `attach` may return a callable; SciQLop calls it on panel close (from its close path, never from `destroyed`), on withdrawal, and before re-attaching a replaced extension. |
| Missing kind on restore | A placeholder panel that keeps the raw tree (saving it writes the tree back unchanged), names the plugin, and offers to install it. |
| Finding the plugin to install | The store index entry whose latest compatible version lists the kind under `provides["sciqlop.panel_kinds"]`; else the entry whose canonical name equals the kind's id prefix; else the message alone. The published index has no `provides` today (checked 2026-10-16: 11 plugins, 0 versions with it); copying it into the index is an `sciqlop-appstore` follow-up. |

## 3. Panel kinds: `sciqlop.panel_kinds`

```python
@dataclass(frozen=True)
class PanelKind:
    id: str                                   # "sciqlop.time_panel", "<plugin>.<name>"
    label: str                                # shown in the new-panel menu
    create: Callable[[str, dict], QWidget]    # (name, config) -> widget; config is {} for a new panel
    to_config: Optional[Callable[[QWidget], dict]] = None   # None: this kind cannot be saved
    icon: Optional[str] = None                # registered icon name or file path
    in_new_menu: bool = True
```

- `open_panel(kind_id, name=None, **config)`: claims a unique name (`claim_name`/`auto_name`, as today), calls
  `create(name, config)`, sets the widget's `objectName` and `windowTitle` to the name, docks it through the path
  `new_native_plot_panel` uses today (delete-on-close, rename following, `panel_added`, panels-list
  notification, the add-panel button), records the kind on the widget (`panel_kind_of(widget) -> str`), runs
  the matching panel extensions (§4), and returns the widget.
- The time panel kind's `create` is today's `TimeSyncPanel` construction (+ `PanelContainer`); its `to_config`
  is today's `PanelTemplate.from_panel(...).to_tree()` minus the root `kind`.
- `new_native_plot_panel(name, area)` keeps its signature (it has an `area` argument and callers); it becomes a
  thin wrapper over the shared docking code so the two paths cannot drift.
- `user_api`: `open_panel(kind, name=None, **config)` (marshalled to the main thread; a time panel comes back as
  today's `PlotPanel`, any other kind as its widget) and `list_panel_kinds() -> list[str]`.
- The new-panel menu (the "+" button and its menu) lists every kind with `in_new_menu=True`, in contribution
  order, the time panel first; with only the core kind nothing visible changes.
- Errors: `create` raising → `log.error` naming the kind, nothing docked, `open_panel` re-raises. Unknown kind →
  `NotRegistered` listing the available kinds. A duplicate id from another owner → `DuplicateContribution`.
- Withdrawal: open panels of a withdrawn kind stay open; new ones cannot be opened.
  `simplify:` comment: close them on withdrawal when hot unload needs it.

## 4. Panel extensions: `sciqlop.panel_extensions`

```python
@dataclass(frozen=True)
class PanelExtension:
    id: str
    attach: Callable[[QWidget], Optional[Callable[[], None]]]   # returns the clean-up, or None
    kinds: tuple[str, ...] = ()                                 # () = every panel kind
```

- A follower owned by the main window keeps `{(extension id, panel): cleanup}`.
  - Extension added: attach to every open panel whose kind matches.
  - Panel opened (from `open_panel`): attach every matching extension, in contribution order.
  - Panel closing (from `remove_panel`, before the widget is taken out of its dock): call that panel's clean-ups.
  - Extension removed (withdrawal, `remove_owner`): call its clean-up for every panel it is attached to.
  - Extension replaced (same id, `added` without `removed`): call the old clean-ups, then attach the new one.
- Errors: an `attach` or clean-up that raises is logged with the extension id and the panel name; the panel and
  the other extensions carry on.
- Qt lifetime: EP signals live for the process, main windows do not (and several are alive at once in tests):
  bound-method slots guarded with `shiboken6.isValid(self)`; never call into a parent from a child's `destroyed`
  (`docs/qt-lifetime-patterns.md`).
- No existing core feature moves onto extensions in this work.

## 5. Saving and restoring

- `panel_tree(widget) -> dict`: `{kind, config, slots}`. The time panel gives today's v3 tree unchanged; any
  other kind gives `{"kind": id, "config": to_config(widget)}`; a kind without `to_config` → `ValueError` naming
  the kind; a placeholder gives back the tree it holds.
- `PanelTemplate`: template files accept any root kind. A time-panel root keeps today's `PanelTemplate`
  behaviour (load, `list_templates` migration, apply to an existing panel). Any other root is restored with
  `open_panel(kind, **config)`; the template list shows it like any other template.
- Placeholder panel (a core `QWidget`, not a contribution): text "This panel needs plugin `<plugin>`", the raw
  tree, and an "Install `<plugin>`" button when the store lookup (§2) finds an entry. The lookup runs off the GUI
  thread (`fetch_index` has a 10 s timeout); the button installs through the App Store backend's existing
  install + hot-load path. When the kind is contributed (`PANEL_KINDS` `added` with that id, after a hot-load
  or any other way), the placeholder opens the real panel from its tree in the same dock position and closes
  itself. Install failure → the error is shown in the placeholder; nothing else changes.
- The "save as template" action stays on time panels. A plugin kind adds its own save action through a panel
  extension, calling `panel_tree`.

## 6. Testing

- EP contracts: wrong type, duplicate id, `NotRegistered` message.
- `open_panel`: a test kind docks a widget, gets a unique name, emits `panel_added`, appears in the panels list,
  closes through the close button. Time-panel parity: every existing panel/template test passes unchanged.
- Extensions: attach on extension-added and on panel-opened; clean-up on close, withdrawal and replace; `kinds`
  filtering; `attach`/clean-up raising is logged and contained; a destroyed main window ignores EP signals
  (`destroy_main_window`).
- Templates: a plugin kind round-trips through a template file; a missing kind restores as a placeholder that
  saves its tree back unchanged; the placeholder swaps itself for the real panel when the kind is contributed.
- Install offer: lookup by `provides`, by canonical prefix, and none (fake index); the install path is
  exercised with the App Store backend's install monkeypatched (no network, no pip).
- Interop: plugin A declares a panel kind and an extension of its own kind; plugin B, depending on A, opens A's
  kind through `ctx.plugin`/`open_panel` and extends the time panel; withdrawing A runs every clean-up.

## 7. Documentation

Same commit as the code (parent spec §7): `sciqlop-plugin-design` skill `references/plugin-contract.md` (EP
list) and `references/ui-and-settings.md` ("Panels: kinds and extensions"); global `sciqlop-user-api.md`
(`open_panel`, `list_panel_kinds`); the parent spec's §4.3 row and §5 reworded (no slot API; extensions get the
widget).

## 8. Follow-ups outside this work

- `sciqlop-appstore`: copy each release's `plugin.json` `provides` into `index.json` `versions[]` (makes the
  install lookup exact).
- Foreign rows inside a time panel (needs SciQLopPlots).
- Workspaces saving open panels as trees.
