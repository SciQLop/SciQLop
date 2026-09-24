# Virtual products with a colour axis — design

Date: 2026-09-24. Status: approved in brainstorming, awaiting spec review.
Second opinion: an opencode review of the draft found two flaws in the first
SciQLopPlots API (see "Rejected alternatives"); this spec already includes the fix.

## Goal

A virtual product (VP) can return a colour axis: one scalar per time sample.

- **Time-series panels.** A Scalar, Vector or MultiComponent VP draws as a line
  graph coloured point by point by that scalar.
- **Projection plots.** For example, a spacecraft trajectory (X–Y, Y–Z, Z–X panes)
  coloured by |B|.

The colour comes from the **same VP callback** as the data. Colouring one product
by another product is out of scope.

Success looks like this:

```python
from SciQLop.user_api.data_types import Colored, Vector

def traj(start, stop) -> Colored[Vector["X", "Y", "Z"]]:
    pos = get_pos(start, stop)            # SpeasyVariable or (t, (N, 3))
    return Colored(pos, color=b_mag(pos))  # (N,)

create_virtual_product("demo/traj", traj, VirtualProductType.Vector,
                       labels=["X", "Y", "Z"],
                       color_label="|B| (nT)", color_gradient="viridis")
```

Plotting `demo/traj` in a time panel draws three coloured lines. Plotting it in a
projection plot draws a coloured trajectory with a working time marker. Both use the
plot's shared colour scale (range, log, pinning, gradient), as coloured curves do today.

## Principle: each batch says whether it carries colour

The colour travels **with** its data, in the same signal emission, and that emission
**names** the colour. Nothing is guessed from the number of buffers. Nothing sticky is
stored on the graph.

Why not push the colour after the data? Data reaches the graph through a queued
cross-thread hop (`SciQLopPlots/src/DataProducer.cpp:245-264`). A same-length refresh
keeps the old colours (`src/SciQLopLineGraph.cpp:46-62`). So a colour pushed separately
could land on the next refresh's data.

## Part 1 — SciQLopPlots (needs a release)

1. **A coloured callback result.** A Python callback may return
   `{"data": [t, ...], "color": c}` instead of a plain list. `_collect_buffers`
   (`src/PythonInterface.cpp:546-585`) recognises the dict. `DataProviderInterface`
   then emits a new signal, `new_data_colored(QList<SciQLopPyBuffer> data, SciQLopPyBuffer color)`.
   A plain list behaves exactly as it does today.
2. **The remote pipeline** (out-of-process VPs) gets `set_data_colored(data, color)`.
   It emits the same signal.
3. **Line graphs.** `SciQLopLineGraphFunction` and `SciQLopLineGraphRemote` connect
   `new_data_colored` next to their 2-buffer signal. The slot runs `set_data(x, y)` and
   then applies the colour with the graph's stored gradient, back to back on the GUI
   thread. A remote graph also clears its busy flag on this signal. The busy handling
   is tied to the arity switch at `src/SciQLopGraphInterface.cpp:168-181`. If a batch
   is rejected (wrong colour length), it is dropped with the existing
   `drop_bad_batch` warning.
4. **`SciQLopLineGraph::set_color_gradient(gradient)`**, new. It lets SciQLop set the
   gradient once, before any data arrives.
5. **Projection curves.** `SciQLopNDProjectionCurvesFunction` connects `new_data_colored`
   too. `data` uses today's `n+1` layout `[t, d0..dn-1]`, so the time values are set
   and the time marker works. The colour goes to every pane through the existing
   `set_color_values` path and the shared scale (`src/SciQLopNDProjectionCurves.cpp:83-159`).
6. **Unchanged:** `ColorScaleController`, gradients, range, log, pinning, and all
   existing buffer-count layouts.

Tests (SciQLopPlots `tests/integration/`):
- a callback line graph that returns the dict is coloured;
- a same-length refresh through the dict applies the new colours, not the old ones;
- a plain 3-buffer list sent to a line graph is still not treated as colour;
- a projection fed the dict keeps its time values and feeds the colour scale;
- a remote line graph fed `set_data_colored` is coloured and not left busy.

## Part 2 — SciQLop: the `Colored` type

In `SciQLop/user_api/data_types.py`:

- **`Colored(data, color)`** is a small frozen container. `data` is anything the inner
  type accepts today: a SpeasyVariable or a `(t, values)` tuple. `color` is array-like.
- **`Colored[Vector["X","Y","Z"]]`** (and `Colored[Scalar]`, `Colored[MultiComponent]`)
  returns an annotation marker that wraps the inner annotation.
- **`extract_vp_type_info`** unwraps the marker. `VPTypeInfo` gets one new field,
  `colored: bool = False`. `Colored[Spectrogram]` is rejected with a clear error.
- **`wrap_graph_data`** understands a coloured layer result. It keeps `time` and
  `values`, and adds `color`.

## Part 3 — SciQLop: the data path

1. **Registration.** `create_virtual_product` gets three new keyword arguments:
   `colored: bool = False`, `color_label: str = ""` and `color_gradient: str = "jet"`.
   They are stored in the VP metadata. The `%%vp` magic, the only caller of
   `extract_vp_type_info` today, sets `colored` from `VPTypeInfo.colored`. A direct
   `create_virtual_product` call passes `colored=True` explicitly.
2. **Providers.** `EasyScalar` and `EasyVector` (and so `EasyMultiComponent`) get an
   `_as_colored` step when `colored` is set:
   - the callback must return a `Colored`; anything else is an error in the log and
     yields no data;
   - the inner data goes through today's conversion, giving `[t, values]`;
   - the result is `{"data": [t, values], "color": color}`.
   This means `DataProvider._get_data` (`data_provider.py:153-158`) passes a dict
   through like it passes a list. Its zero-width check applies to `data`.
3. **Validation** (`validation.py`, used with `debug=True`) checks the inner data as
   today, and checks that `color` is 1-D with one value per time sample. NaN is
   allowed; it draws as a gap.
4. **Projection reshape.** `_projection_shaped_callback`
   (`components/plotting/ui/time_sync_panel.py:280-310`) splits the columns inside
   `data` and leaves `color` untouched:
   `{"data": [t, d0..dk-1], "color": c}`.
5. **Plot time.** When SciQLop plots a coloured VP, it sets the gradient on the graph
   (`set_color_gradient`) and the colour-axis label from the VP metadata. This is done
   on every plot, not stored across hot reloads.
6. **`%%vp` magic** (`user_api/virtual_products/magic.py`):
   - `_inject_type_names` also injects `Colored`;
   - `_infer_type_from_data` unwraps a `Colored` result, so an unannotated cell that
     returns one is inferred as the coloured inner type.
7. **Out-of-process VPs.**
   - The remote registry stores a `colored` flag next to the arity
     (`easy_provider.py:196-202`, `remote/registry.py`).
   - The worker's `reduce_result` turns a `Colored` into the inner arrays plus the
     colour as the last array (`remote/reduction.py`).
   - The channel (`remote/channel.py:66-80`) calls
     `pipeline.set_data_colored(views[:-1], views[-1])` for a coloured channel.
     Otherwise it calls `set_data(*views)` as today.
   - The docstring invariant in `reduction.py` ("arity is fixed by the graph type") is
     updated to mention the flag.

Out of scope: spectrograms (they already have a z axis), and colouring one product
by another product.

## Testing (SciQLop)

TDD, reproducer first, as usual. New tests next to the existing ones in
`tests/test_virtual_products/`, `tests/test_vp_*.py` and
`tests/test_projection_*.py`:

- `Colored[...]` annotations resolve to the right `VPTypeInfo`, `colored=True`;
  `Colored[Spectrogram]` raises.
- a coloured Vector VP plotted in a time panel gives a line graph with colour data;
  panning (a refresh) keeps colour and data paired.
- a coloured Vector VP in a projection plot colours the curves, and the time marker
  still gets time values.
- a VP registered as coloured that returns plain data logs an error and draws nothing.
- debug validation rejects a colour of the wrong length or with 2 dimensions.
- `%%vp` with `-> Colored[Vector[...]]` under `from __future__ import annotations`,
  and an unannotated cell returning `Colored(...)`.
- an out-of-process coloured VP draws coloured and is not left busy.
- a plain Vector VP returning `(t, bx, by)` is **not** coloured (regression guard for
  the rejected no-flag rule).

## Rejected alternatives

- **Push the colour after the data (SciQLop only).** No release needed, but it races
  on refresh (see "Principle").
- **Treat 3 buffers to a line graph as colour, with no flag.** A Vector VP returning
  `(t, bx, by)` is passed through today (`easy_provider.py:404-405`) and dropped. Under
  that rule, `by` would silently become a colour axis, which is worse than no plot.
  Found by the opencode review.
- **A sticky `set_color_column(bool)` on projection curves.** A `%%vp` hot reload from
  uncoloured to coloured would not flip it, and the next batch would be misread.
  Found by the opencode review.
- **A `ColoredVector` VP type per combination.** Multiplies types for no gain over a
  wrapper.

## Follow-ups (not in this work)

- A 2-pane projection returning `n+1 = 3` buffers goes out on `new_data_3d` and is
  dropped, because projections only connect `new_data_nd`. SciQLop always builds
  3 panes, so it is not affected. File as a SciQLopPlots issue.
- One-column line graphs built by `plot(x, y)` are not colourable yet (SciQLopPlots #113).
  Callback line graphs are always `SciQLopLineGraphFunction`, so VPs are not affected.
- A "colour by another product" convenience could be built on top of this later.
