# UI, threading and settings

## `load(main_window)`

- Called once, on the GUI thread, at startup. Keep it fast: register products,
  build widgets, return. No network calls here; start them in the background.
- Import SciQLop and Qt modules inside `load()` or in submodules it imports.
  Pure-Python helpers stay importable without SciQLop, which keeps them easy
  to test.
- Never raise for a missing configuration (no API key, server down, CLI not
  installed). Load anyway, and report the problem where the user meets it: in
  the dock, or on the graph through the callback's exception. A raising
  `load()` can take other plugins down with it.
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

def load(main_window):
    register_agent_backend(MyBackend)        # needs MyBackend.display_name
    return ensure_agent_dock(main_window)
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
