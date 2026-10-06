---
name: sciqlop-plugin-design
description: Use when designing, writing, reviewing or debugging a SciQLop plugin — a Python package SciQLop loads at startup through `load(main_window)` — including plugins that add products to the product tree, virtual products, dock widgets, settings pages, data fetchers or agent backends, and when a plugin loads but its products, plots or dock show nothing.
---

# Designing SciQLop plugins

## Overview

A SciQLop plugin is a Python package with a `load(main_window)` function.
SciQLop calls it once at startup. Everything the plugin adds goes through
SciQLop's public API: `SciQLop.user_api` for products and plots, the main
window for docks and menus, `ConfigEntry` for settings.

Most plugin bugs are silent. The plugin loads, the product shows in the tree,
and the plot stays empty. Each trap below was hit in a real plugin. Read the
table before writing code, and come back to it when something shows nothing.

**Source of truth:** the installed `SciQLop.user_api` package. Signatures
change between releases. Before relying on a call, check it: read its
docstring, or call `sciqlop_api_reference('<module>')` when you run inside
SciQLop's chat. Never copy a pattern from another plugin without checking it
against the current API — plugins carry workarounds for bugs fixed since.

## Pick the mechanism from what the plugin does

| The plugin needs to… | Use | Not |
|---|---|---|
| Add a plottable product computed or fetched on demand | `create_virtual_product(path, callback, VirtualProductType.X)` | A custom Speasy provider (the tree is built once at startup) |
| Derive a product from other products | Callback params annotated `Annotated[SpeasyVariable, Depends("a//b")]` | `speasy.get_data` inside the callback body |
| Stream archived data (files, web service) | One virtual product **per source/channel**; the callback fetches whatever covers `[start, stop]` | One product per downloaded file |
| Let the user tune a product (threshold, smoothing) | Extra callback kwargs with defaults → knobs | A custom form in a dock |
| Plot static data the plugin already holds | `panel.plot_data(x, y[, z])` on a `create_plot_panel()` | Direct SciQLopPlots calls |
| Show a browser / search UI | A `QWidget` in a dock (`main_window.addWidgetIntoDock`) | A modal dialog |
| Draw a small plot inside that dock | SciQLopPlots, graphs created once and updated with `set_data` | matplotlib |
| Persist user options | A `ConfigEntry` subclass | Hand-written YAML/JSON |
| Mark events or intervals | `SciQLop.user_api.catalogs.catalogs` | A private event list |
| Add an assistant to the chat dock | `register_agent_backend(MyBackend)` + `ensure_agent_dock(main_window)` | Your own chat widget |

Details and code for each row: [references/products-and-data.md](references/products-and-data.md)
and [references/ui-and-settings.md](references/ui-and-settings.md).

## Minimal plugin

```
my_plugin/                  # folder added to SciQLop's plugin folders
├── pyproject.toml          # name = "sciqlop-my-plugin"
└── my_plugin/              # the package SciQLop imports
    ├── __init__.py         # defines or re-exports load()
    ├── plugin.json         # REQUIRED for folder discovery
    └── tests/
```

```python
# my_plugin/__init__.py
def load(main_window):
    from .products import register_products   # import SciQLop-heavy code lazily
    return register_products()                 # keep references alive; may be None
```

If `load()` returns an object with `async def close(self)`, SciQLop awaits it
at shutdown. Packaging, `plugin.json` fields, version pins and tests:
[references/packaging-and-testing.md](references/packaging-and-testing.md).

## Traps that make a plugin show nothing

| Symptom | Cause | Fix |
|---|---|---|
| Plugin never loads from its folder | No `plugin.json` next to `__init__.py`, or the folder in the settings is the wrong level | Add it; list the folder that *contains* the package |
| Log says "Skipping plugin" for a valid-looking plugin | `plugin.json` misses a required field (each author needs `name`, `email`, `organization`) | Fill every field |
| Log says "Skipping plugin … requires SciQLop" | The `SciQLop>=X,<Y` range in `plugin.json` excludes the running version | Widen the range once tested on that version |
| Plot has data but no units, linear spectrogram | Callback returns bare arrays, so no metadata reaches the plot | Return a `SpeasyVariable` with `UNITS`/`SCALETYP` meta |
| Product in tree, plot empty, no error | The callback swallowed an exception and returned `None` | Let errors raise; SciQLop logs them and records them on the graph. Return `None` only for "no data here" |
| Knobs missing, log says "knobs disabled" | Callback takes `*args`/`**kwargs` | Exact signature: `(start: float, stop: float, knob: int = 5)` |
| `NameError: Knob` at registration, or knobs/labels silently missing | `from __future__ import annotations` + a name used in the callback's annotations (`Knob`, `SpeasyVariable`, …) imported inside a function | Import every annotation name at module top |
| Panel shows "now", data is from 2015 | Fresh panel keeps the default range | Set `panel.time_range` after plotting (a few days, not a dataset's whole decade) |
| Multi-day range collapses to one day | Panel zoom limit (default 1 day) clips the span | Raise `panel.zoom_limit_seconds` first, only if `0 < limit < span` |
| y axis stuck at 0..5 | `rescale_axes()` called before the time range was set | Set the time range first, then rescale |
| Spectrogram blank or scrambled | `y` (energy/frequency) not ascending. Products get a fully reversed axis flipped for them; `plot_data` and unordered bins don't | Sort `y` ascending (`argsort`), reorder `z` |
| Log scale or units right on one window, wrong after panning | Hints from a returned `SpeasyVariable` are applied once per plot, from the first non-empty fetch | Put the same `UNITS`/`SCALETYP` on every return, don't derive them from the data |
| Products only appear on the 2nd launch | Plugin added a Speasy inventory after the tree was built | Use virtual products, or republish the tree node |
| Dock appears above the welcome page, not tabbed | `addWidgetIntoDock(area=None)` at load time | Pass `area=` explicitly |
| Settings test passes on CI, fails locally | `ConfigEntry` reads the real user YAML instead of kwargs | Monkeypatch `entry.SCIQLOP_CONFIG_DIR` to a temp dir in every test |
| Works in-process, empty with `out_of_process=True` | Worker process has a different environment; no ISTP hints come back | Test the callback in a subprocess; keep metadata-rich products in-process |

## Design rules

1. **Public API first.** Use `SciQLop.user_api`. Reach into `plot._impl` or
   `SciQLop.components.*` only for a gap with no public alternative, behind one
   helper with a comment naming the gap.
2. **Products are paths and callbacks, not files.** A product is a stable tree
   path plus a function of `(start, stop)`. SciQLop drives pan and zoom.
3. **Fail loudly.** Never `except Exception: pass`, never return a truncated
   result silently. Raise, or show the reason in the dock.
4. **Never block the GUI thread.** Network and disk work run off the GUI
   thread; results come back through a Qt signal or `invoke_on_main_thread`.
   Errors travel the same way.
5. **Compute once, cache, update cheaply.** Heavy work (fetch, fit, FFT) runs
   once per window and is cached. UI interaction only reslices cached arrays.
6. **Verify by looking.** Reading `axis.range()` back proves the call took,
   not that the plot is right. Render the real panel and look at it, with a
   realistic selection (several channels, several days).
