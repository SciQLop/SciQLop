# Products and data

How a plugin puts data in front of the user. Check every call below against
the installed `SciQLop.user_api` before relying on it.

## Product paths

- A path is a list of tree segments. As a string, join with `//`:
  `"myplugin//mission//instrument//param"`. Never split a path on a single
  `/` yourself — segment names may contain `/` (AMDA has `"final / prelim"`).
- A string without `//` is split on `/`, so `"myplugin/foo"` also works when
  you register your own products. Pick segment names without `/`.
- No `"root"` prefix. Speasy products live under `speasy//<provider>//...`.
- Pick a top-level segment named after the plugin, so its products are easy to
  find and never collide with another plugin's.

## Virtual products: the default way to add products

```python
from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType

def b_total(start: float, stop: float):          # epoch seconds, UTC
    t, b = fetch_my_data(start, stop)            # your code
    if t is None:
        return None                              # "no data in this window"
    return t, b                                  # or a SpeasyVariable

vp = create_virtual_product("myplugin/b_total", b_total,
                            VirtualProductType.Scalar, labels=["|B|"])
```

### Callback contract

- **Signature:** `start` and `stop` first, annotated. `float` gives epoch
  seconds; `datetime` and `np.datetime64` are converted for you. Extra
  parameters with defaults become knobs. No `*args` or `**kwargs`: they
  disable every knob.
- **Return:**
  - Scalar / Vector / MultiComponent: `(t, y)` or a `SpeasyVariable`.
  - Spectrogram: `(t, y, z)` with `z.shape == (len(t), len(y))`, or a 2-D
    `SpeasyVariable` whose second axis is the frequency or energy axis.
  - `None`: nothing covers this window. A normal outcome, not an error. (An
    empty result means the same to the panel. Inside a `@Cacheable` fetch
    function the rule differs — see Caching.)
  - Spectrogram energy/frequency axis: a fully reversed axis is flipped for
    you. Bins in any other order are not: sort them with `np.argsort` and
    reorder `z`.
  - Fill values: replace them with `NaN` in the callback. Nothing on the
    product path does it for you.
- **Errors:** raise. SciQLop logs the traceback and records the message on
  the graph (`sciqlop_describe_panel` reports it as `last_error`). A callback
  that catches everything and returns `None` turns a bug into a blank plot
  that nobody can diagnose.
- **Labels:** Scalar takes exactly 1, Vector exactly 3, MultiComponent any
  number, Spectrogram none. A return annotation (`-> Vector["x", "y", "z"]`,
  types from `SciQLop.user_api.virtual_products.types`) can carry them.
- **Return a `SpeasyVariable` when you can.** Its metadata becomes axis labels,
  units and log scales on the plot. Building one by hand, set
  `meta["UNITS"]`, `meta["SCALETYP"]` (`"linear"`/`"log"`), `meta["LABLAXIS"]`,
  and `columns=[...]`. These hints are read **once per plot**, from the first
  non-empty fetch: decide scales from the product, not from one window's data.
- **Annotations are evaluated in the module's globals.** With
  `from __future__ import annotations`, every name used in the callback's
  annotations (`SpeasyVariable`, `Knob`, `Scalar`, …) must be imported at
  module top. Otherwise SciQLop silently falls back: time arguments of unknown
  type, knobs and annotated labels lost.
- **Keep the returned `VirtualProduct`** (return it from `load()`, or store it
  on your plugin object). Plot it with `panel.plot(vp)` or by path with
  `panel.plot_product("myplugin//b_total")`.
- Registering again at the same path replaces the tree node, but the old
  provider object stays alive. Register each path once: keep a
  `{path: VirtualProduct}` dict and reuse the entry. There is no public removal
  call yet; `list_virtual_products()` lists what exists.
- `display_name=` sets the tree label without changing the path.

### `cachable=True`

A promise that the callback returns the same full-resolution data for an
interval, whatever window is requested. SciQLop then fetches twice the
visible window and serves pans inside it without calling you again. Leave it
off when the output depends on the whole window (an average over it) or has a
fixed number of points per request (it would keep coarse data after a zoom).

### Derived products: `Depends`

Declare inputs in the signature instead of fetching them in the body:

```python
from typing import Annotated
from speasy.products import SpeasyVariable
from SciQLop.user_api.virtual_products import Depends
from SciQLop.user_api.virtual_products.types import Scalar

FGM = "speasy//cda//MMS//MMS1//FGM//MMS1_FGM_SRVY_L2//mms1_fgm_b_gse_srvy_l2"

def b_squared(start: float, stop: float,
              b: Annotated[SpeasyVariable, Depends(FGM, pad=30.0)]) -> Scalar["|B|^2"]:
    return None if b is None else b["Bt"] ** 2
```

The target can be a product path, another `VirtualProduct`, or a
`callable(start, stop)`. `pad` widens the fetch (seconds) so resampling has
data at both edges. Do the maths on the `SpeasyVariable`, not on `.values`:
the variable keeps time axis, units and labels.

### Knobs

```python
from typing import Annotated
from SciQLop.user_api.knobs import Knob          # MODULE TOP — see below

def smoothed(start: float, stop: float,
             window: Annotated[int, Knob(min=1, max=500, label="Window")] = 10):
    ...
```

- A plain default (`window: int = 10`) is enough for a spin box. `Annotated`
  with `Knob(...)` adds bounds, labels, units, and visual widgets
  (`widget="vspan"`, `"hline"`, `"vline"`).
- With `from __future__ import annotations`, SciQLop evaluates the annotation
  strings in the callback's **module globals**. `Knob` imported inside a
  factory function is invisible there → `NameError` at registration. Import
  it at module top. A unit test with `inspect.signature(cb, eval_str=True)`
  pins this.
- Shared knob aliases (`Window = Annotated[int, Knob(...)]`) must also be
  module-level names in every module that uses them.

## Streaming archived data (files, web services)

Model: **one virtual product per source channel**, whose callback fetches
whatever covers `[start, stop]`. The user pans and zooms with SciQLop's normal
time controls; your plugin never manages windows itself.

```python
@dataclass(frozen=True)
class Source:                       # data, not code: one row per channel
    path: str                       # "myplugin//station_a//flux"
    query: dict                     # what your fetcher needs

def make_callback(source, fetcher):
    def callback(start: float, stop: float):
        files = fetcher.search(source.query, start, stop)
        if len(files) > MAX_FILES:
            raise ValueError(f"{len(files)} files in view; zoom in")   # never truncate silently
        if not files:
            return None
        return concat_along_time([fetcher.load(f) for f in files])
    return callback

def register(sources, fetcher):
    return [create_virtual_product(s.path, make_callback(s, fetcher),
                                   VirtualProductType.Spectrogram)
            for s in sources]
```

Rules:
- Never one product per downloaded file. It floods the tree, and the user
  cannot pan past the file's end.
- Cap the work per call and say so. Returning only the first N files shows
  data at the window start and nothing after: it looks like a fetch bug.
- If the search UI creates products on demand (the user picks a station),
  persist what was created, and re-register it in `load()` without network
  calls. Otherwise saved panels referencing it fail after a restart. A
  settings field marked `json_schema_extra={"widget": "hidden"}` is a good
  store: persisted, not shown in the settings page.
- First window for a freshly plotted product: a few days, not the dataset's
  full coverage. Prefer a sample range the source advertises, else the last N
  days of coverage. A decade-long first request stalls everything.

## Caching remote data

Use Speasy's cache rather than writing your own.

- `@Cacheable(prefix="myplugin", fragment_hours=1)` (from
  `speasy.core.cache`): range-aware. It splits the window into fixed
  fragments, caches each, and merges. Pans reuse fragments. The decorated
  function takes `start_time`/`stop_time` arguments (configurable) and must
  return a `SpeasyVariable`.
  - For "there is certainly no data here", return an **empty**
    `SpeasyVariable`, not `None`. `None` means "unknown": nothing is cached,
    and a concurrent request for the same fragment can wait on a pending lock
    for minutes.
  - Cache **raw** data. Filter, detrend, resample or FFT downstream, on the
    assembled window. Processing per fragment leaves seams at fragment edges.
  - A cached fragment is final. Bypass the cache for windows near "now" that
    the archive may still fill in.
- `@CacheCall(cache_retention=..., is_pure=True)`: exact-argument cache, for a
  pure step like parsing a file keyed by `(path, mtime_ns, size)`.
- Cached values must pickle. Search results holding live objects (sessions,
  web rows) don't: convert them to plain dicts or keep an in-memory TTL dict.
- Import `speasy.core.cache` lazily (inside the factory) if plugin import time
  matters.

## Out-of-process products

`create_virtual_product` has no such option. Instantiate the classes from
`SciQLop.user_api.virtual_products` directly:
`VirtualScalar(path, callback, label, out_of_process=True)` (and
`VirtualVector`, `VirtualMultiComponent`, `VirtualSpectrogram`). The callback
then runs in a worker process, one per plugin.
It keeps a slow or GIL-heavy callback off SciQLop's process. Costs:

- The callback is pickled with `cloudpickle` at registration. Closures over
  sockets, Qt objects or open files fail there.
- No `Depends(...)`, no `debug=True`.
- Only arrays come back. Metadata from a returned `SpeasyVariable` is lost, so
  no automatic labels, units or log scales.
- The worker has its own environment and state. A product visible in the
  tree proves nothing about the fetch path: test the callback in a subprocess.

Keep products in-process unless the callback measurably hurts the UI.

## Static data the plugin already holds

```python
import numpy as np
from SciQLop.user_api import TimeRange
from SciQLop.user_api.plot import create_plot_panel

panel = create_plot_panel()
span = float((t[-1] - t[0]) / np.timedelta64(1, "s"))     # t is datetime64
if 0 < panel.zoom_limit_seconds < span:                    # 0 means unlimited: keep it
    panel.zoom_limit_seconds = span
plot, graph = panel.plot_data(t, energy, flux)             # 3 args → colormap
panel.time_range = TimeRange(t[0], t[-1])
plot.apply_hints(hints)                                    # labels, units, log scales
```

- 2 arguments → lines (one per column of `y`); 3 with a 2-D `z` → colormap.
- `datetime64` times and any numeric dtype are converted for you.
- **Colormap `y` must be ascending.** The renderer binary-searches both axes;
  a descending energy table gives a blank or scrambled image, not a flipped
  one. `energy, flux = energy[::-1], flux[:, ::-1]` when needed.
- Replace fill values (CDF `FILLVAL`, often `-1e31`) with `NaN` before
  plotting; they wreck auto-scaling. Compare in the variable's own dtype.
- Set the time range **after** plotting, and **before** `plot.rescale_axes()`:
  rescale fits y to the data inside the visible window only.
- Skip all of this when plotting a product: the panel drives the range.

## Plot hints

`SciQLop.core.plot_hints.PlotHints` / `AxisHints` describe labels, units and
scales declaratively. `plot.apply_hints(hints)` applies them.
`SciQLop.core.istp_hints.istp_metadata_to_hints(attrs)` builds them from ISTP
(CDF) attributes, with the DEPEND_1 variable's attributes under `"_depend_1"`.

On a colormap the vertical axis (energy, frequency) is `y2` and the colour
scale is `z`. The left `y` axis is for lines.

## Speasy providers in a plugin

Only if the data must be reachable through `speasy.get_data` too.

- Parameter and dataset uids in your inventory must **not** start with the
  provider name. SciQLop adds `speasy//<provider>//` itself.
- SciQLop builds the `speasy` tree once, when its Speasy plugin loads. An
  inventory your plugin adds later shows up only on the next launch. Either
  republish the provider's tree node after updating the inventory, or expose
  the products as virtual products instead.
