---
name: sciqlop-virtual-products
description: Use when the user asks for a derived or computed quantity, a "virtual product", a `%%vp` cell, or to plot something computed from what is already plotted (|V_alpha - V_p|, plasma beta, a filtered or rotated field, a ratio of two densities). Covers designing, writing, testing and plotting a SciQLop virtual product.
---

# Virtual products in SciQLop

The `sciqlop_*` tools named here exist only inside SciQLop's chat panel. Read
`AGENTS.md` first: it has the plotting workflow and the Speasy rules this
skill builds on.

A virtual product (VP) is a Python function `f(start, stop, ...)`. SciQLop
calls it for whatever time range is on screen, and again on every pan or
zoom. It shows up in the product tree and plots like any other product.

## Workflow

Follow these steps in order. Each one catches a mistake the next one cannot.
When the definition, the inputs or the deliverable are open, settle them with
the user first (see the `sciqlop-clarify` skill).

1. **Find the inputs.** If the user points at what is on screen, call
   `sciqlop_describe_panel(name=...)` and take the product paths from it,
   dropping a leading `root//`. Otherwise drill `sciqlop_products_tree`.
   Keep the `//`-joined paths: `Depends` and `sciqlop_fetch` both take them.
2. **Look at the data.** Call `sciqlop_fetch(products=[...], start, stop,
   name="raw")` over a short range, such as the panel's own range. It binds a
   dict of `SpeasyVariable`s in the kernel and prints its keys, shapes, units
   and coverage. Do not hunt speasy uids to call `spz.get_data` yourself.
3. **Try the maths** with `sciqlop_exec_python` on those variables. Check
   `v.columns`, `v.unit` and the cadence (`np.diff(v.time[:5])`) first. Then
   compute and print a few numbers. Are the values physically plausible, in
   the units you expect? Fix it here, where each try is cheap.
4. **Write the VP** in the declarative form below and register it with one
   `sciqlop_exec_python` call. If the user wants it in a notebook, create
   the notebook with `sciqlop_create_notebook`, add the cell with
   `sciqlop_insert_notebook_cell`, and run it with
   `sciqlop_run_notebook_cell`. That runs it in the same kernel.
   A VP with a return annotation is registered without running. Add
   `--debug --start "<iso>" --stop "<iso>"` to the `%%vp` line to run it once
   right away: the cell output lists each input, the result (shape, unit, NaN
   share, min/median/max) and the checks, or the error with its traceback.
   It also opens a scratch debug panel showing the result.
5. **Plot it** with `sciqlop_plot_product(product="<the --path>",
   name="<panel>")`. The default `plot_index=-1` adds a new subplot below the
   others; an existing index overlays it on that subplot.
6. **Check it on the panel.** Call `sciqlop_wait_for_plot_data(name=...)`,
   then `sciqlop_describe_panel(name=...)`: the new graph's `last_error` must
   be empty and `n_points` above zero. Then `sciqlop_screenshot_panel` to
   look at it.
7. **Fix and rerun.** Edit the cell and run it again with the same function
   name. The product is updated in place, and plots that show it fetch again.

## The form to write

```python
%%vp --path "wind/dv_alpha_proton"
from typing import Annotated
import numpy as np
from speasy.products import SpeasyVariable
from speasy.signal.resampling import interpolate
from SciQLop.user_api.virtual_products import Depends

WIND = "speasy//amda//Parameters//Wind//3DP//ion - moments"

def dv_alpha_proton(
    start: float, stop: float,
    va: Annotated[SpeasyVariable, Depends(WIND + "//alpha//velocity GSE")],
    vp: Annotated[SpeasyVariable, Depends(WIND + "//proton//velocity GSE")],
) -> Scalar["|V_alpha - V_p|"]:
    if va is None or vp is None:
        return None
    return np.linalg.norm(va - interpolate(va, vp), axis=1)
```

- `start` and `stop` come first, as epoch seconds.
- Each input is a parameter annotated with `Depends("<//path>")`. SciQLop
  fetches it for the requested range and passes it in. Never call
  `spz.get_data` in the body. A `Depends` target can also be another VP, to
  chain computations, or any `callable(start, stop)`.
- The return annotation sets the plot type and the legend: `Scalar["label"]`,
  `Vector["x", "y", "z"]`, `MultiComponent["a", "b", ...]` or
  `Spectrogram`. One label per column you return. `%%vp` provides these
  names; elsewhere, import them from
  `SciQLop.user_api.virtual_products.types`.
- Exactly one public function per cell. Name helpers with a leading `_`.
- Any other parameter with a default value (`window: int = 5`) becomes a
  knob the user can change from the plot's inspector, without editing code.

## Traps

- **An input can be `None`.** Speasy returns nothing for a range without
  data. Return `None` then, never raise.
- **Inputs live on different time grids.** Products have their own cadence.
  `interpolate(reference, other)` puts `other` on `reference`'s timestamps,
  and the result keeps `reference`'s time axis. Use the input with the
  cadence you want for the output as the reference, usually the coarser one.
- **Edges.** Interpolation, filters and derivatives need data beyond the
  requested range. Widen the fetch with `Depends(path, pad=<seconds>)`.
- **Gaps and fill values** arrive as NaN from Speasy products. NumPy
  propagates NaN, which is what you want: never replace it with zeros.
- **Do the maths on the `SpeasyVariable`,** not on `.values`. Arithmetic,
  ufuncs, `np.linalg.norm(v, axis=1)` and column selection all keep the time
  axis and units. A bare array has no time axis to plot against.
- **Column labels are product-specific.** Read `v.columns` before selecting
  `v["..."]`. Never guess a label.
- **Units.** Check `v.unit` on every input before combining them. Convert
  explicitly (`b * 1e-9` for nT to T), and put the output unit in the label
  when it is not obvious.
- **Large ranges.** The function runs on every pan and zoom, over the whole
  visible range. Keep it vectorised; no Python loops over samples.
- **`--cachable`.** Add it to `%%vp` when the output for a time range only
  depends on the inputs in that range. SciQLop then fetches a margin around
  the view, so panning stays smooth. Leave it out when the function returns a
  fixed number of points for any range, such as a resampled or binned
  product.
- **Read the `--debug` report before plotting.** A value range far from what
  the physics allows, a NaN share near 100% or a time span shorter than the
  requested range are bugs to fix first, even when the checks say ok.

For anything not covered here (spectrogram axes, coloured lines, knob
widgets), call `sciqlop_api_reference('virtual_products')` and
`sciqlop_api_reference('knobs')` rather than guessing signatures.
