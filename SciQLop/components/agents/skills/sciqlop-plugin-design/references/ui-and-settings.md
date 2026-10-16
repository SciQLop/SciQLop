# UI, threading and settings

## `activate(ctx)` (older plugins: `load(main_window)`)

The rules below apply to both. `activate(ctx)` reaches the main window as
`ctx.main_window`; `load(main_window)` stays supported.

- Called once, on the GUI thread, at startup. Keep it fast: register products,
  build widgets, return. No network calls here; start them in the background.
- Import SciQLop and Qt modules inside `activate()` (or `load()`) or in submodules it imports.
  Pure-Python helpers stay importable without SciQLop, which keeps them easy
  to test.
- Never raise for a missing configuration (no API key, server down, CLI not
  installed). Load anyway, and report the problem where the user meets it: in
  the dock, or on the graph through the callback's exception. A raising
  `activate()` (or `load()`) refuses every plugin that depends on yours.
- Return the objects you must keep alive (widgets, products). If the returned
  object has `async def close(self)`, SciQLop awaits it at shutdown: stop
  threads and close connections there.

## Docks

Contribute a `Dock` to `sciqlop.docks`. The main window builds and places it.

```python
from SciQLop.core.docks import Dock

def activate(ctx):
    ctx.contribute("sciqlop.docks", Dock(
        id="radio.spectrum", title="Radio spectrum",
        build=lambda: SpectrumWidget(),   # called by the window that places it
        placement="center",               # "center", "left", "right" or "bottom"
        icon=None,                        # registered icon name or image path; None: the widget's windowIcon
        visible=False,                    # center docks start hidden
        toolbar=True))                    # toggle also in the toolbar and the Tools menu
```

- `center` tabs the dock beside the Welcome page (`main_window.central_area()`).
  `left`/`right`/`bottom` make an auto-hide side pane, collapsed until clicked.
- The toggle action always goes to the View menu. Show and hide the dock only
  through it; `widget.show()` bypasses the docking system.
- Withdrawing the contribution (plugin disabled or failed) closes and deletes
  the dock and removes its toggle from every menu and toolbar.
- Contributing the same `id` again with `replace=True` rebuilds the dock.
- This replaces the old dance: a `_find_central_area` helper,
  `addWidgetIntoDock(..., area=...)`, `findDockWidget(title)`,
  `toggleView(False)`, then adding the toggle by hand.
- `main_window.add_side_pan(widget, location, icon)` still works. It
  contributes `Dock(id=f"{owner}.{title}", ...)` for an existing widget, so a
  second side pane with the same title from the same plugin raises `ValueError`.
  Withdrawing that pane deletes the widget you passed in: don't keep using it.

## Panels: kinds and extensions

A dock is one widget per window. A panel kind is a widget the user can open
many times, like the plot panel. Contribute a `PanelKind` to `sciqlop.panel_kinds`.

```python
from SciQLop.core.panel_kinds import PanelKind

def activate(ctx):
    ctx.contribute("sciqlop.panel_kinds", PanelKind(
        id="radio.waterfall", label="Waterfall",
        create=lambda name, config: Waterfall(config.get("band", "HF")),  # (name, config) -> QWidget
        to_config=lambda w: {"band": w.band},  # widget -> config dict; None: this kind cannot be saved
        icon=None,                 # registered icon name or image path
        in_new_menu=True))

    ctx.main_window.open_panel("radio.waterfall", band="LF")   # returns the widget
```

- `open_panel(kind_id, name=None, area=None, **config)` claims a unique name,
  calls `create(name, config)` with the keyword arguments as `config`, sets the
  widget's `objectName` and `windowTitle` to that name, docks it, and returns it.
- Names: with no `name`, the kind's `label` is the base (`Waterfall0`,
  `Waterfall1`...). A taken name gets a suffix (`X`, then `X_1`). Read the name
  back from `widget.objectName()`; renaming the widget renames its tab.
- The core kind is `sciqlop.time_panel` (`SciQLop.core.plot_kinds.TIME_PANEL`):
  `open_panel(TIME_PANEL)` is `new_plot_panel()`.
- `panel_kind_of(widget)` (`SciQLop.core.panel_kinds`) gives a panel's kind id.
  `main_window.panels()` lists every panel; `plot_panels()` still lists only
  plot-panel names.
- `main_window.remove_panel(widget_or_name)` and the tab's X close any kind,
  docked or floating. The widget is deleted: don't keep using it.
  `panel_added` is emitted with every new panel, of any kind.
- `create` raising: SciQLop logs an error naming the kind, docks nothing and
  `open_panel` re-raises. An unknown kind raises `NotRegistered` (a
  `LookupError`) listing the available kinds.
- Withdrawing a kind (plugin disabled or failed) keeps its open panels open;
  only new ones can no longer be opened.
- The "+" button in a dock area's title bar opens a time panel as before. With a
  second kind that has `in_new_menu=True`, it becomes a split button: the arrow
  lists every such kind by `label` (time panel first) and opens the choice in
  that area. Set `in_new_menu=False` to keep a kind out of the menu.
- From notebooks and scripts: `from SciQLop.user_api.panels import open_panel, list_panel_kinds`.
  `open_panel(kind, name=None, **config)` returns a `PlotPanel` for the time
  panel and the widget for any other kind.

Saving a panel of your kind:

- `panel_tree(widget)` (`SciQLop.components.plotting.panel_template`) gives
  `{"kind": id, "config": to_config(widget), "slots": {}}`. A time panel gives
  its usual template tree. A kind without `to_config` raises `ValueError`
  naming the kind.
- `PanelTemplate.from_panel(widget).to_file(path)` saves a template of your
  kind; its name is the widget's title. Files in the templates folder show up in
  the template list like time templates. `create_panel(main_window)` reopens it
  under the template's name and passes the saved config to `create` as a dict,
  so any key works, `name` and `area` included (only the public keyword form
  `open_panel(kind, **config)` reserves those two). `template.panel_kind` is the
  root kind.
- `apply(panel)` stays time-panel only: on another kind's template it raises
  `TypeError`.
- The "Save as template" button is on time panels only. Add your own through a
  panel extension that calls `PanelTemplate.from_panel(panel).to_file(...)`.
- Missing kind (plugin not installed or disabled): the template opens a
  placeholder panel ("This panel needs plugin 'radio' (panel kind
  'radio.waterfall')."), kind id `sciqlop.placeholder_panel`. It keeps the tree
  as read: `panel_tree(placeholder)` and saving it again write the same tree
  back. Panel extensions with `kinds=()` attach to it too.
- The placeholder looks your plugin up in the App Store index (off the GUI
  thread; offline, it shows the message alone). When it finds you it shows an
  "Install <plugin>" button, which installs and hot-loads through the App
  Store. An install error is shown in the placeholder.
- As soon as the kind is contributed (after that install, or because the plugin
  was enabled some other way), the placeholder opens the real panel with the
  saved config, in the same dock area and under the same name, and closes
  itself. If `create` raises, the placeholder stays and shows the error.
- So the offer finds you, list your panel kinds in `plugin.json`:
  `"provides": {"sciqlop.panel_kinds": ["radio.waterfall"]}`. Without it the
  store entry whose name matches the kind's id prefix (`radio`) is offered.

A panel extension is code run on every open and future panel of some kinds.
Contribute a `PanelExtension` to `sciqlop.panel_extensions`. `attach(panel)` gets
the panel widget and returns its clean-up (or None).

```python
from PySide6.QtWidgets import QToolButton
from SciQLop.core.panel_extensions import PanelExtension
from SciQLop.core.plot_kinds import TIME_PANEL

def add_button(panel):
    button = QToolButton(panel, text="Zoom to event")
    button.clicked.connect(lambda: zoom_to_event(panel))
    button.show()
    return button.deleteLater                    # the clean-up: no arguments

def activate(ctx):
    ctx.contribute("sciqlop.panel_extensions",
                   PanelExtension(id="events.zoom_button", attach=add_button, kinds=(TIME_PANEL,)))
```

- `kinds=()` (the default) means every panel kind. Attach order is contribution order.
- `attach` runs on every open panel of a matching kind when the extension is
  contributed, and on every new one when it opens.
- The clean-up runs once: when the panel closes (`remove_panel`, the tab's X,
  docked or floating), when the extension is withdrawn (plugin disabled or
  failed: the panels stay open), and before the new `attach` when the same id
  is contributed again.
- The clean-up never runs for a panel already destroyed, or one whose window
  was destroyed. So keep the extension's state as children of the panel (they
  die with it). Any connection to an app-lifetime object (a registry signal,
  the app, a timer) must check `shiboken6.isValid(panel)` in its slot.
- An `attach` or clean-up that raises is logged with the extension id and the
  panel name; the panel and the other extensions carry on.
- Every main window runs its own extensions on its own panels.

## Threading

SciQLop runs a Qt event loop on the main thread (with asyncio on top, through
qasync). Notebook code and SciQLop's chat tools run on another thread.

- Network, disk and heavy maths go to a worker (`QThreadPool` +
  `QRunnable`, or `concurrent.futures`). Send results back with a Qt signal.
  Send failures through the same signal, with the message — a worker that
  dies silently leaves a spinner forever.
- Connect that signal to a **method of a `QObject` living on the GUI thread**
  (your widget's slot). Connected to a lambda or a plain function, the slot
  runs in the worker thread, and touching widgets from there crashes at
  random.
- Keep a Python reference to the signal-carrying object until it has fired;
  a `QRunnable` is auto-deleted after `run()`.
- A late reply for a selection the user already left must be dropped: tag
  each request and ignore stale answers.
- `SciQLop.user_api` objects already marshal their calls to the GUI thread.
  Your own helpers that touch Qt objects from another thread need
  `@on_main_thread` (from `SciQLop.user_api.threading`), or call
  `invoke_on_main_thread(func, *args)`.
- Virtual product callbacks already run off the GUI thread. Do the fetch
  directly in the callback; don't spawn threads from it.
- Under qasync, `httpx.AsyncClient` streaming raises "cancel scope in a
  different task" errors. Stream with a sync client in an executor and bridge
  chunks to asyncio with `loop.call_soon_threadsafe(queue.put_nowait, item)`.

## Tables and lists

Users expect a header click to sort every table. Four traps, each silently
wrong:

1. Numbers shown as text sort as text (`"100 Hz" < "20 Hz"`). Keep the
   formatted text and store a typed key in a sort role (`Qt.UserRole + 1`).
2. `currentRow()` used as an index into a Python list is wrong once sorted.
   Store the payload, or its index, on the row's first item.
3. `QTableWidget` re-sorts on every `setItem` while sorting is on, scattering
   a row's cells. `setSortingEnabled(False)` while filling, then re-enable.
4. In a tree model, a parent row with only column 0 stops `sortChildren` from
   reaching its children. Give parent rows empty cells in every column.

## Plots inside your own widgets

A dock that previews data embeds SciQLopPlots widgets directly (`SciQLopPlot`).
Plot panels from `user_api` live in SciQLop's central area, not in your dock.
Plugins and users build mixed panels with `panel.add(kind, **config)`, the same path templates use.

- Create graphs once, then update them with `graph.set_data(...)`. Never redo
  a fetch or a fit on a slider move: compute once, cache, and reslice.
- Removing a line graph: `shiboken6.delete(graph)`. `del` drops only the Python
  wrapper and the C++ graph stays in the plot and the legend.
- One colormap per plot. Reuse it with `set_data` rather than recreating it.
- After `set_data` with a single time sample, widen the x range by hand: a
  zero-width `set_range(t, t)` is ignored.
- Pass C-contiguous `float64` arrays (`np.ascontiguousarray`). A reversed view
  (`a[::-1]`) fails deep in the bindings with an unrelated-looking
  `SystemError`.
- Themes: `SciQLopTheme.dark()` with **no parent**. `set_theme` takes
  ownership; a parented theme is double-owned and crashes on close.
- SciQLopPlots has no type stubs, and property-vs-method is not consistent.
  Check before use: `type(getattr(Class, "name")).__name__` gives
  `getset_descriptor` (property) or `method_descriptor` (call it).
- A `NameError: ... SciQLopPlotsBindings is not defined` usually means a wrong
  argument type or order in an overloaded call, not an import problem.
- Use matplotlib only for exported, offline figures.

## Commands and menu entries

A command is a contribution to `sciqlop.commands`: it shows in the command palette. A menu entry
(`sciqlop.menus`) places a registered command in a menu, in the same plugin or another one.

`PaletteCommand(id, name, description, callback, args=[...])` and
`MenuEntry(id, location, command, label=None, when=<always>, order=0)`
(`from SciQLop.core.menus import MenuEntry`). `label=None` shows the command's name. Entries sort by `(order, id)`.

When an entry is triggered, the callback gets the context values whose key matches one of the command's
`CommandArg.name`s. The context values use the palette's argument conventions. The locations and their context keys:

| Location | Menu | Context keys |
|---|---|---|
| `panel` | panel right-click menu | `panel` (panel name) |
| `panel.export` | Export submenu of the panel menu | `panel` |
| `graph` | per-graph submenu under Export > Copy Python code | `panel`, `graph` (graph name) |
| `product_tree` | right-click on a plottable product | `product` (path string, `//` separated) |
| `catalog_tree` | right-click in the catalog tree | `provider`, and `catalog` when on a catalog |
| `main.tools` | Tools menu | none |

`when(context)` decides whether the entry shows for that context. A `when` that raises hides the entry and logs an error.
An entry whose command is not registered is left out.

```python
from SciQLop.components.command_palette.arg_types import PanelArg
from SciQLop.components.command_palette.backend.registry import PaletteCommand
from SciQLop.core.menus import PANEL, MenuEntry


def activate(ctx):
    ctx.contribute("sciqlop.commands", PaletteCommand(
        id="my_plugin.zoom", name="Zoom to last event", description="", args=[PanelArg("panel")],
        callback=lambda panel: zoom_to_last_event(panel)))
    ctx.contribute("sciqlop.menus", MenuEntry("my_plugin.zoom_entry", PANEL, "my_plugin.zoom",
                                              when=lambda c: c["panel"].startswith("MMS")))
```

`register_panel_menu` (dynamic submenus on the panel menu) is unchanged and keeps working.

Plugins register commands in `activate(ctx)`. `CommandRegistry().register(...)` also works from a notebook cell:
it is marshalled to the main thread.

## Export targets

A file format for `PlotPanel.save(path)` and the panel's Export menu is a contribution to `sciqlop.export_targets`.
Each target adds an "Export as <label>..." action.

`ExportTarget(id, label, suffixes, write, scalable=True)` (`from SciQLop.core.export_targets import ExportTarget`):

- `suffixes`: lowercase, each starting with `.`. The first one is the dialog's default and the one appended when the user leaves it out.
- `write(panel, path, width, height, scale)`: `panel` is the user_api `PlotPanel`. `width` and `height` are 0 when unset, `scale` is `None` when unset. Raise on failure: the menu shows the message, `save` lets it propagate.
- `scalable=False`: `save(..., scale=...)` is refused for this target.

Two targets claiming the same suffix: the core ones (PNG, PDF, JPEG, BMP) win, then the lowest id.
The menu lists core targets first, then plugin targets in contribution order.

```python
from SciQLop.core.export_targets import ExportTarget


def write_csv(panel, path, width, height, scale):
    with open(path, "w") as f:
        f.write(f"panel,plots\n{panel.name},{len(panel.plots)}\n")


def activate(ctx):
    ctx.contribute("sciqlop.export_targets", ExportTarget("my_plugin.csv", "CSV", (".csv",), write_csv, scalable=False))
```

## Inspector sections

A section in the inspector of a panel, a plot or a graph is a contribution to `sciqlop.inspector_sections`.

`InspectorSection(id, title, target, build, applies=<always>, priority=0)`
(`from SciQLop.core.inspector_sections import InspectorSection, GRAPH_TARGET`):

- `target`: `PANEL_TARGET`, `PLOT_TARGET` or `GRAPH_TARGET` (`"panel"`, `"plot"`, `"graph"`).
- `build(obj, parent)` returns the section's `QWidget`, created with `parent`. `obj` is the user_api object:
  a `PlotPanel`, a plot (`TimeSeriesPlot`, `XYPlot`, `ProjectionPlot`) or a graph. A `build` that raises shows
  "<title>: failed to build, see the log".
- `applies(obj)` decides whether the section goes on that object. It runs when the object or the section appears,
  and again for a rejected section whenever the graphs of the object's plot change. Keep it cheap and free of side
  effects. A raising `applies` skips the section and logs an error.
- `priority`: an int, ordering the sections in the inspector.

The section reaches objects that already exist and every new one. Withdrawing it removes it everywhere.
Keep no state in the section: read it from `obj` each time `build` runs.

```python
from PySide6.QtWidgets import QLabel
from SciQLop.core.inspector_sections import GRAPH_TARGET, InspectorSection


def activate(ctx):
    ctx.contribute("sciqlop.inspector_sections", InspectorSection(
        "my_plugin.about", "About", GRAPH_TARGET,
        build=lambda graph, parent: QLabel(f"Graph {graph.name}", parent)))
```

## Keyboard shortcuts

A shortcut is a contribution to `sciqlop.shortcuts`. It is listed in the help panel and in Settings, and the
user can rebind it. Use `register_shortcut` in `activate(ctx)`, or `ctx.contribute("sciqlop.shortcuts", Shortcut(...))`.
The id is `<plugin id>.<name>`.

```python
from SciQLop.components.shortcuts.registry import Shortcut, register_shortcut

def activate(ctx):
    register_shortcut(Shortcut("my_plugin.fit", "VDF", "Fit the distribution", "Ctrl+Alt+F"))
```

A shortcut registered while the help panel or Settings is open shows up there at once.
Plugins register shortcuts in `activate(ctx)`. `register_shortcut` also works from a notebook cell: it is
marshalled to the main thread.

## Kernel: magics and namespace

An IPython magic is a contribution to `sciqlop.magics`. It is applied to the SciQLop kernel at once, and
removed again when your plugin is withdrawn.

```python
from SciQLop.core.magics import Magic

def hello(line):
    return f"hi {line}"

def activate(ctx):
    ctx.contribute("sciqlop.magics", Magic("my_plugin.hello", "hello", "line", hello))
```

- `kind` is `"line"`, `"cell"` or `"line_cell"`. `name` is an identifier, without the `%`.
- `completer` is optional: an IPython matcher (API v2) for tab completion. It is removed with the magic.
- The core magics (`%vp`, `%layer`, `%plot`, `%timerange`, `%install`, `%workspace`, `%job`) always keep their name.
  A plugin magic with the same name is logged and ignored.
- Between plugins, the first contribution of a name wins. When it is withdrawn, the next one takes over.
- A magic that raises prints its traceback in the cell. The kernel keeps running.

A kernel name is a contribution to `sciqlop.kernel_namespace`. It is pushed into the kernel's namespace at once.

```python
from SciQLop.core.kernel_namespace import NamespaceEntry

def activate(ctx):
    ctx.contribute("sciqlop.kernel_namespace", NamespaceEntry("my_plugin.stats", "stats", my_stats))
```

- `name` is an identifier. The value is pushed as it is when you contribute; keep it cheap to create.
- The core names (`main_window`, `workspace`, `app`, `background_run`, `plugins`) always keep their name.
  A plugin entry with the same name is logged and ignored.
- Between plugins, the first contribution of a name wins. When it is withdrawn, the next one takes over.
- Withdrawing removes the name only if the user did not rebind it. A name the user reassigned stays.

## Drop rules

What a drop on a plot does is a contribution to `sciqlop.drop_rules`
(`from SciQLop.core.drop_rules import DROP_RULES, DropRule`). Every plot panel
accepts each MIME type that has rules, including MIME types contributed later.

`DropRule(id, mime_type, drop, product_kind=None, target=None, creates_plot=False)`:
- `drop(plot, payload, panel)` does the work. For a drop between plots, `plot` is the empty plot the panel
  just made: a rule that builds its own plot calls `take_drop_placeholder(plot, panel)` (from
  `SciQLop.components.plotting.drops`) first, then moves its new plot to the index it returns, as the scene rule
  does. `plot` is None only for programmatic drops.
  For `PRODUCT_LIST_MIME_TYPE` the payload is one product path. A rule that raises shows the error on the plot.
- `product_kind` is the dragged product's kind id and `target` is the plot kind id of the plot dropped on.
  None matches anything.
- `creates_plot=True` lets a drop between plots make a new plot for it.
- The most specific matching rule wins: a matching `product_kind` weighs 2, a matching `target` weighs 1,
  and ties go to the smallest id.

```python
from SciQLop.core.drop_rules import DropRule
from SciQLop.core.mime.types import PRODUCT_LIST_MIME_TYPE

ctx.contribute("sciqlop.drop_rules", DropRule("my_plugin.show_vdf", PRODUCT_LIST_MIME_TYPE,
                                         lambda plot, product, panel: show_vdf(plot, product),
                                         product_kind="my_plugin.distribution", creates_plot=True))
```

Contribute through `ctx` in `activate(ctx)` so the rule goes away with the plugin.

Scene plots are saved in panel templates and restored by name, but only registered scenes and boundaries:
an ad-hoc `Scene` object comes back as a placeholder.

## Settings

```python
from typing import ClassVar
from pydantic import Field, field_validator
from SciQLop.components.settings import ConfigEntry, SettingsCategory

class MyPluginSettings(ConfigEntry):                 # class name must be unique app-wide
    category: ClassVar[str] = SettingsCategory.PLUGINS
    subcategory: ClassVar[str] = "My Plugin"

    server_url: str = Field("https://example.org/api", description="Data server")
    timeout_s: int = Field(60, ge=5, le=600, description="Request timeout, seconds")

    @field_validator("timeout_s", mode="before")
    @classmethod
    def _clamp_timeout(cls, v):
        try:
            return max(5, min(600, int(v)))
        except (TypeError, ValueError):
            return v
```

- The class appears as a page in SciQLop's settings. Field `description`s are
  the help text.
- Each class persists to `<config dir>/<classname lowercased>.yaml`, and the
  class name is a global registry key: two plugins defining `Settings` clash.
  Prefix it with the plugin name.
- A `ConfigEntry` subclass is a contribution to `sciqlop.settings`, keyed by class name and owned by the plugin
  that imported it. Withdrawing the plugin removes its page from the panel; the YAML file stays on disk. A plugin
  installed while Settings is open shows up there at once. A second class with a name already in use still raises
  `ValueError`, but a withdrawn plugin's name is free again.
- `MyPluginSettings()` reads the YAML on every construction. Construct it when
  you need the value instead of caching an instance at load time.
  `with MyPluginSettings() as s: s.timeout_s = 30` saves on exit.
- Once a YAML file exists, its content **replaces** constructor kwargs.
- One invalid value resets **every** field to its default, and the defaults
  are saved over the user's file at once. Clamp every bounded numeric field
  with a `mode="before"` validator, so a stale or hand-edited value can't wipe
  the user's other settings.
- State the plugin must persist but the user shouldn't edit (products created
  on demand, last selection): a field with
  `json_schema_extra={"widget": "hidden"}`.
- Secrets go to the system keyring: set
  `_keyring_ = KeyringMapping("server_url", "username", "password")` (from
  `SciQLop.components.settings.backend.entry`). Never store a token in YAML.

## Workspace sections

A plugin can own one table of the workspace's `.sciqlop` file, described by a pydantic model.

```python
from pydantic import BaseModel
from SciQLop.components.workspaces.backend.workspace_sections import WorkspaceSection

class MyPluginWorkspace(BaseModel):
    last_catalog: str = ""

ctx.contribute("sciqlop.workspace_sections", WorkspaceSection("my_plugin", MyPluginWorkspace))
```

- Read with `manifest.section("my_plugin")`. You get a model instance, or `None` when the table is absent, the
  section is not contributed, or the table does not validate (logged once per loaded manifest, so a plugin reading
  through `edit_manifest` warns on each call; the table is kept as is).
- Write with `manifest.set_section("my_plugin", MyPluginWorkspace(...))`, then `manifest.save(path)`. Use
  `edit_manifest(path)` so you do not overwrite what others saved.
- TOML has no null: fields that are `None` are left out of the file, and `set_section` raises `ValueError` for a
  `None` inside a list. Give optional fields a `None` default so they read back.
- The table name cannot be `workspace`, `plugins`, `dependencies` or `examples` (SciQLop's), and must be a bare
  TOML key (`[A-Za-z0-9_-]+`).
- Withdrawing the plugin leaves the table in the file, untouched.
- No change notification: call `section()` when you need the value.

## Quickstart, tours, search, catalogs, templates, presets, themes

Each of these is owned by your plugin when you add it from `activate(ctx)`, and leaves when your plugin is
withdrawn:

- `SciQLop.core.sciqlop_application.sciqlop_app().add_quickstart_shortcut(name, description, icon, callback)` adds a welcome-page shortcut. A name
  already used by another plugin or by SciQLop is refused (`DuplicateContribution`).
- `register_tour(Tour(...))` (`SciQLop.components.onboarding`) adds a guided tour. A tour needs at least one step,
  and step ids must be unique; the `Tour` constructor checks both. A tour id already used by another plugin is
  refused (`DuplicateContribution`).
- `register_domain(domain)` (`SciQLop.components.smart_search`) adds a smart-search domain: an object with a `name`
  and a `snapshot()` returning `NodeSnapshot(path_key, raw_text)` items. Call `notify_changed(name)` when its content
  changes. A domain name already used by another plugin is refused (`DuplicateContribution`).
- Subclass `CatalogProvider` and build it: it registers itself. `register` works from any thread, but build the
  provider on the main thread: a QObject keeps the thread it was built on. Do not `ctx.contribute` a provider:
  building it registers it.
- `ctx.contribute("sciqlop.template_formats", TemplateFormat(id, label, suffixes, loads, dumps))` lets panel templates
  be saved and read in your format: `loads(text) -> dict`, `dumps(dict) -> text`. "Save as template" still writes
  `.json`; files in your format are listed while your plugin is active.
- `ctx.contribute("sciqlop.time_presets", TimePreset(id, label, seconds, description))` adds a duration to every
  panel's time-range bar and to the palette's "Set time range". `description` is the palette wording ("Last 3 days").
- `ctx.contribute("sciqlop.themes", Theme(id, label, palette))` adds a theme to Settings → Appearance and to
  `user_api.themes`. `palette` maps Qt palette roles (`Window`, `Base`, `Text`, …) to colours, as the files in
  `SciQLop/resources/palettes` do. If your theme is the user's choice, it applies as soon as your plugin activates;
  when your plugin is withdrawn SciQLop shows `space` and keeps the user's choice.

## Agents: backends, tools, skills

### Backends (`sciqlop.agent_backends`)

The chat dock belongs to SciQLop. A backend plugin contributes a class only:

```python
from SciQLop.components.agents import ensure_agent_dock, register_agent_backend

def activate(ctx):
    register_agent_backend(MyBackend)        # needs MyBackend.display_name
    return ensure_agent_dock(ctx.main_window)
```

- For a CLI agent that speaks ACP, subclass
  `SciQLop.components.agents.acp.AcpAgentBackend` and implement
  `acp_command()`. The rest (tools, streaming, permissions, sessions) is
  inherited.
- Keep `__init__` and `check_prerequisites()` lenient. Raise from
  `acp_command()` or from the first request instead, so the error shows in the
  chat. A backend raising during construction fails the dock and every agent
  plugin loaded after it.
- Read API keys at request time, not in `__init__`.
- Implement `async aclose()` if your backend holds a process, a server or a connection: SciQLop calls it when it
  drops the backend (New session after a tool or skill change, a replaced or withdrawn backend). `AcpAgentBackend`
  already does. Errors are logged, never raised.
- `register_agent_backend` contributes an `AgentBackendEntry(name, factory)` to `sciqlop.agent_backends`, owned
  by your plugin; withdrawing the plugin removes it. Any thread may call it. The legacy
  `register_agent_backend("Name", factory)` form still works.
- Registering a name again replaces the backend. A name another plugin registered is taken over with a warning.
  A replacement takes effect for new sessions: the conversation open on that backend keeps its instance until
  New session.
- The dock follows the extension point: a backend installed later appears in its list without disturbing the
  open conversation. Withdrawing the backend in use cancels its running turn, drops its session and falls back to the first
  available.

### Tools (`sciqlop.agent_tools`)

A plugin offers tools to agent sessions next to SciQLop's own, from `activate` (main thread):

```python
from SciQLop.components.agents import AGENT_TOOLS, AgentTool

def activate(ctx):
    schema = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}
    AGENT_TOOLS.contribute(AgentTool("myplugin_echo", "Echo the text back.", schema, lambda p: p["text"]))
    AGENT_TOOLS.contribute(AgentTool("myplugin_wipe", "Delete the cache.", {"type": "object", "properties": {}},
                                     lambda p: wipe_cache(), gated=True, thread=True))
```

- `name` matches `^[a-zA-Z0-9_-]{1,64}$`, `description` is not empty, else `ValueError`. Prefix names with your plugin.
- `call(payload)` returns text, a dict with `"content"` (as the core tools do), or a coroutine.
- `gated=True` for anything that changes state: it is denied when writes are off, and the user confirms each call.
- `thread=True` runs `call` in a worker thread: only for Qt-free code. Otherwise it runs on the GUI thread.
- A name already used by a core tool or an earlier contribution is ignored and logged: core tools always win.
- Sessions get a snapshot. The dock picks up new or withdrawn tools once all plugins have loaded: a chat with no
  messages yet is rebuilt with them at once, a chat with messages gets them when the user clicks New session. A
  running session calling a withdrawn tool is told it was withdrawn.

### Skills (`sciqlop.agent_skills`)

A plugin ships a skill folder and contributes it from `activate` (main thread):

```python
from pathlib import Path
from SciQLop.components.agents import AGENT_SKILLS, AgentSkill

def activate(ctx):
    AGENT_SKILLS.contribute(AgentSkill("myplugin-howto", Path(__file__).parent / "skills" / "myplugin-howto"))
```

- The folder holds `SKILL.md` plus any reference `*.md` files, in sub-folders if you like.
- `name` matches `^[a-z0-9][a-z0-9-]{0,63}$` and the folder must hold `SKILL.md`, else `ValueError`. Prefix names
  with your plugin; they share `.claude/skills/` with SciQLop's and the user's own.
- Skills are copied into `<workspace>/.claude/skills/<name>/` once all plugins have loaded (and whenever a session
  starts). A chat with no messages yet is restarted so its agent sees them; a chat with messages gets them on New
  session.
- SciQLop records what it published in `.claude/skills/.sciqlop-published`. A skill withdrawn later (plugin
  disabled or unloaded) is removed from the workspace the same way; folders not in that record, such as the
  user's own skills, are never touched.
