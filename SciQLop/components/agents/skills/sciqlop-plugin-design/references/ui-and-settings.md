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

```python
import PySide6QtAds as QtAds

def _central_area(main_window):
    welcome = main_window.dock_manager.findDockWidget("Welcome")
    return welcome.dockAreaWidget() if welcome is not None else None

def add_dock(main_window, widget, title):
    widget.setWindowTitle(title)                         # becomes the dock title
    main_window.addWidgetIntoDock(QtAds.DockWidgetArea.TopDockWidgetArea, widget,
                                  area=_central_area(main_window))
    dock = main_window.dock_manager.findDockWidget(title)
    dock.toggleView(False)                               # start hidden
    action = dock.toggleViewAction()
    main_window.toolsMenu.addAction(action)              # same action everywhere
    main_window.toolBar.addAction(action)
    return dock
```

- Pass `area=` explicitly. With `area=None`, SciQLop picks the biggest
  *visible* area — and at load time the window is not laid out yet, so nothing
  is visible. The dock then lands in a new area stacked above the welcome page
  instead of tabbed beside it.
- Show and hide the dock only through `dock.toggleViewAction()`. Calling
  `widget.show()` or your own toggle bypasses the docking system and pops the
  dock into a fresh area.
- `addWidgetIntoDock` already adds the toggle to the View menu.

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

## Agent backend plugins

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
