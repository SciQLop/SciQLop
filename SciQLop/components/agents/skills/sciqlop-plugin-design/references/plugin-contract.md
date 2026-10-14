# Plugin contract: activate(ctx), dependencies, extension points

## Two entry points

- `activate(ctx)` — the current contract. SciQLop calls it once, in dependency order. Return your public API (or None).
- `load(main_window)` — the old contract, still supported. A module with `activate` never gets `load` called.
- `ready(ctx)` (optional, `activate` plugins only) — runs after every plugin activated. Read what others contributed here. If it raises, the error is logged and the plugin stays active.

## plugin.json

| Key | Meaning |
|---|---|
| `name`, `version` | display name, and the version other plugins' specifiers check (semver: a breaking API change is a major bump) |
| `dependencies` | plugins you need, by plugin id (folder or entry-point name) with PEP 440 ranges: `["vdf>=1.2,<2"]` |
| `optional_dependencies` | plugins you use when present; they load before you |
| `provides` | `{extension point id: [contribution ids]}` plus `"extension_points": [ids you declare]`; shown by the app store |
| `python_dependencies` | pip packages (numpy…); never other plugins |

A packaged plugin ships `plugin.json` next to the module its `sciqlop.plugins` entry point names, and lists it in package data.

## ctx

| Call | Does |
|---|---|
| `ctx.contribute("sciqlop.scenes.scenes", Scene(...))` | add to an extension point; you are recorded as the owner. `replace=True` overwrites an item another owner registered |
| `ctx.extension_point("myplugin.methods", Method)` | declare your own extension point; the id must start with `myplugin.` |
| `ctx.plugin("vdf")` | the API `vdf`'s `activate` returned; raises `UndeclaredDependency` if `vdf` is not in your plugin.json, `PluginUnavailable` if it is not active |
| `ctx.has("mars")` | whether a declared dependency is active |
| `ctx.main_window` | the main window, for docks and menus |

Extension points are main-thread objects: contributing from another thread raises `WrongThread`.
Core ids today: `sciqlop.scenes.bodies`, `sciqlop.scenes.boundaries`, `sciqlop.scenes.scenes`.

## Collaborating with another plugin

```python
def activate(ctx):
    vdf = ctx.plugin("vdf")                       # declared in plugin.json dependencies
    ctx.contribute("vdf.reconstruction_methods", vdf.Method("myplugin.fast", fast))
    if ctx.has("mars"):                           # optional_dependencies
        from .with_mars import register           # code needing mars lives in its own module
        register(ctx)
    return MyApi()
```

If you keep a list built from an extension point (a menu, a cache), also connect to
`extensions.get(ep_id).signals.added`: a plugin installed later contributes after your `ready`.

## When a plugin does not load

The log says why: `Plugin study not loaded: needs plugin vdf>=1.2,<2, but vdf 2.0.0 is installed`.
Dependents of a refused or failed plugin are refused too, with the chain in the message.

## Test that plugin.json matches the code

```python
from SciQLop.components.plugins.testing import assert_provides_matches
assert_provides_matches("myplugin", "myplugin/plugin.json")   # after activating the plugin
```

At startup the loader runs the same check and only logs a warning on drift.
