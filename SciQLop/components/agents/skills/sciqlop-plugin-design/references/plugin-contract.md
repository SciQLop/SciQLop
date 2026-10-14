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
| `optional_dependencies` | plugins you use when present; they load before you when they can. Inside a mutual pair (each optional to the other, or optional one way and required the other) one of you loads first, so `ctx.has(other)` is reliable only in `ready()` |
| `provides` | `{extension point id: [contribution ids]}` plus `"extension_points": [ids you declare]`; shown by the app store |
| `python_dependencies` | pip packages (numpy…); never other plugins |

A packaged plugin ships `plugin.json` next to the module its `sciqlop.plugins` entry point names, and lists it in package data.
Editable installs often list no files, so their `plugin.json` is not found and the plugin loads without dependencies.

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

Hypothetical example: `vdf`, `vdf.reconstruction_methods`, `vdf.Method` and `mars` are made-up names.

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

## Drag-and-drop payloads (`sciqlop.mime_types`)

A `MimeType(id, decoder, encoder=None, obj_type=None, nested_type=None)` is keyed by `id`, the MIME type string.
`decoder(QMimeData)` returns the object. `encoder(obj)` returns a `QMimeData`. `encode_mime(obj)` finds the encoder
by the exact `type(obj)`; for a list it uses `obj_type=list` and `nested_type` for the item type.
`SciQLop.core.mime.register_mime(...)` still works and contributes a `MimeType` too.
When two MIME types encode the same object type, the first registered wins. Register a new object type rather than
re-registering `TimeRange` under another MIME id.

```python
from SciQLop.core.mime import MimeType

def activate(ctx):
    ctx.contribute("sciqlop.mime_types",
                   MimeType("application/x.vdf.slice", decode_slice, encode_slice, obj_type=Slice))
```

## Data contracts (extension points in SciQLop 1b)

| Extension point | Contribution | Key | How a plugin contributes |
|---|---|---|---|
| `sciqlop.data_providers` | `DataProvider` | provider name | `MyProvider("myplugin")` registers itself, owned by the active plugin |
| `sciqlop.mime_types` | `MimeType` | MIME string | `ctx.contribute(...)`, or `register_mime(...)` |
| `sciqlop.source_kinds` | `SourceKind` | `id` | `ctx.contribute(...)`; a provider points at it with its `source_kind` attribute |
| `sciqlop.product_kinds` | `ProductKind` | `id` | `ctx.contribute(...)`; tag product-tree nodes with `PRODUCT_KIND_KEY` |

Field details: data providers, source kinds and product kinds in
[products-and-data.md](products-and-data.md), MIME types above.

```python
from SciQLop.components.plotting.backend.data_provider import DataProvider
from SciQLop.core.enums import ParameterType
from SciQLop.core.models import ProductsModelNodeType, add_product_node
from SciQLop.core.product_kinds import PRODUCT_KIND_KEY, ProductKind
from SciQLop.core.source_kinds import SourceKind

class VdfProvider(DataProvider):
    source_kind = "vdf.instrument"

def activate(ctx):
    ctx.contribute("sciqlop.product_kinds", ProductKind("vdf.distribution", "VDF", 3, "vdf.slice_plot"))
    ctx.contribute("sciqlop.source_kinds", SourceKind("vdf.instrument", tooltip, inspector_line))
    provider = VdfProvider("vdf")
    add_product_node(["vdf"], "f", provider.name, {PRODUCT_KIND_KEY: "vdf.distribution"},
                     ProductsModelNodeType.PARAMETER, ParameterType.Scalar)
```

- A failed `activate()` withdraws everything the plugin contributed.
- Dependency names match across case, dash and underscore: `io-vdf`, `io_vdf` and `Io_Vdf` are one plugin.
- Plot kinds, which make a plugin's product kind plottable, are in the next section.

## Plot kinds, drop rules and saved panels

| Extension point | Contribution | Key |
|---|---|---|
| `sciqlop.plot_kinds` | `PlotKind(id, label, plot_product, owns, to_config, from_config)` | `id` |
| `sciqlop.drop_rules` | `DropRule(id, mime_type, drop, product_kind, target, creates_plot)` | `id` |

`PlotKind` contracts:
- `plot_product(target, product, kwargs)` puts a product on a panel or plot and returns `(plot, graph)`, or None.
- `owns(plot)` says whether an existing plot is yours. A plot no plugin claims is a time-series plot.
- `to_config(plot)` returns JSON-friendly values only (str, number, bool, list, dict). None means "not saved".
- `from_config(panel, config)` builds the plot on the panel and returns the user-facing object.

`DropRule.drop(plot, payload, panel)` gets one product path for product drops. For a drop between plots, `plot`
is the empty plot the panel has just made. A rule that builds its own plot calls `take_drop_placeholder(plot, panel)`
first, which removes that empty plot and returns its index (or None), then moves its new plot there with
`panel.move_plot(panel.plot_count() - 1, index)`. `plot` is None only for programmatic drops. Rules are matched on MIME type, then weighted: a matching `product_kind` counts 2, a matching `target`
(plot kind id) counts 1. The heaviest wins, ties go to the smallest id. `None` matches anything.
`creates_plot=True` makes a drop between plots create that empty plot first.
A plot that stands in for a missing plugin's plot kind refuses product drops, so rules never see it.

A saved panel is a tree (template v3). Each plot is its kind id plus the config `to_config` returned:

```yaml
version: 3
panel:
  kind: sciqlop.time_panel
  config: {time_range: ...}
  slots:
    plots:
      - {kind: vdf.slice_plot, id: ..., config: {product: vdf//mms1/dis, plane: XY}, slots: {}}
```

When a kind is unknown (plugin gone or disabled) or its `from_config` fails, the panel gets a placeholder that
names the plugin from the id prefix. The placeholder keeps the node, so saving the panel again writes it back
unchanged and the plugin can restore it later.

`PlotPanel.add(kind, **config)` builds a plot through the same `from_config`, so
`panel.add("vdf.slice_plot", product="vdf//mms1/dis", plane="XY")` and a restored template take one path.
Drop-rule behaviour and scene plots: see ui-and-settings.md. Plot dispatch by product kind: products-and-data.md.

```python
from SciQLopPlots import PlotType
from SciQLop.core.drop_rules import DropRule
from SciQLop.core.mime.types import PRODUCT_LIST_MIME_TYPE
from SciQLop.core.plot_kinds import PlotKind
from SciQLop.core.product_kinds import ProductKind

SEEN = {}                                         # plot name -> config

def from_config(panel, config):
    plot = panel.create_plot(len(panel.plots()), PlotType.TimeSeries)
    SEEN[plot.objectName()] = dict(config)
    return plot

def drop(plot, product, panel):
    from SciQLop.components.plotting.drops import take_drop_placeholder
    index = take_drop_placeholder(plot, panel)
    new_plot = from_config(panel, {"product": "//".join(product)})
    if index is not None:
        panel.move_plot(panel.plot_count() - 1, index)
    return new_plot

def activate(ctx):
    kind = PlotKind("vdf.slice_plot", "VDF slice", lambda panel, product, kw: (from_config(panel, {"product": "//".join(product)}), None),
                    lambda plot: plot.objectName() in SEEN, lambda plot: SEEN[plot.objectName()], from_config)
    ctx.contribute("sciqlop.product_kinds", ProductKind("vdf.distribution", "VDF", 0, "vdf.slice_plot"))
    ctx.contribute("sciqlop.plot_kinds", kind)
    ctx.contribute("sciqlop.drop_rules", DropRule("vdf.drop", PRODUCT_LIST_MIME_TYPE, drop,
        product_kind="vdf.distribution", creates_plot=True))
```

## When a plugin does not load

The log says why: `Plugin study not loaded: needs plugin vdf>=1.2,<2, but vdf 2.0.0 is installed`.
Dependents of a refused or failed plugin are refused too, with the chain in the message.

## Test that plugin.json matches the code

```python
from SciQLop.components.plugins.testing import assert_provides_matches
assert_provides_matches("myplugin", "myplugin/plugin.json")   # after activating the plugin
```

At startup the loader runs the same check and only logs a warning on drift. It applies only to `activate` plugins that ship a `plugin.json`.
