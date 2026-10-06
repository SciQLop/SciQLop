---
name: sciqlop-troubleshooting
description: Use when a plot is empty, wrong, stuck loading or slow, a fetch fails, a cell hangs, SciQLop crashed, or the user asks why something does not show. Maps each symptom to the tool calls that tell its causes apart, and to the fix.
---

# Troubleshooting in SciQLop

The `sciqlop_*` tools named here exist only inside SciQLop's chat panel.
Diagnose before changing anything: each symptom below has several causes, and
one or two tool calls tell them apart.

## Always start here

1. **Name the panel.** `sciqlop_list_panels` lists them.
   `sciqlop_active_panel` returns nothing when several panels are open and
   none has focus; then ask which one, or pass `name=` everywhere.
2. `sciqlop_wait_for_plot_data(name=...)`. Data loads asynchronously.
3. `sciqlop_describe_panel(name=...)`. For every graph: `busy`, `n_points`,
   `last_error`, and for every plot the y axis `log` flag and `range`.
4. `sciqlop_screenshot_panel(name=...)` to see what the user sees.

## Symptom → check → cause

**Empty plot, `last_error` is set.** Read the message; it is the exception
the fetch raised.
- A network or HTTP error: the provider is unreachable. On a network that
  needs a proxy, the user sets it in Settings › Application › network
  (`proxy_url`, `no_proxy`).
- An error from a virtual product: fix its code. Run it once with
  `%%vp --debug --start ... --stop ...`, which prints the inputs, the result
  and the traceback (see the `sciqlop-virtual-products` skill).

**Empty plot, no error, `n_points` 0 or null.** No data in that time range,
which is not an error. Compare the panel's `time_range` with the product's
coverage from `sciqlop_describe_product`. If it falls outside, the user also
sees a "No data here" notice with a **Go to first data** / **Go to last
data** button. If it falls inside, the instrument may have a gap: call
`sciqlop_describe_product` with `probe=true` and the panel's range to see the
gap share.

**Stuck loading: `busy` stays true, or the wait times out.** A slow provider,
or a range far too long for a dense product. Check the range against the
product's cadence (probe it) and narrow it. A slow virtual product runs its
whole computation on every refresh.

**Data is there but the plot looks flat, empty or clipped.** Compare the y
`range` from `sciqlop_describe_panel` with the data's min/max from
`sciqlop_fetch`. The user can autoscale with **M** (axis under the mouse) or
**Ctrl+Shift+A** (all plots). On a log axis (`log: true`), values ≤ 0 cannot
be drawn; **L** toggles log on the axis under the mouse.

**The line breaks into pieces, or joins across a gap.** Fill values arrive as
NaN, so breaks at NaN are real gaps. A line graph also breaks where the time
step jumps; its `gap_threshold` controls that, and `0` never breaks. Check
the graph API with `sciqlop_api_reference('plot')`.

**A spectrogram looks wrong.** Its log scales come from the product's
metadata; set them from the plot API when the metadata is missing. A
descending frequency axis is flipped automatically, and a product without a
frequency axis is drawn against the channel index.

**Panning or zooming is slow, or refetches every time.** Speasy products
fetch a margin around the view, so small pans are free. A virtual product
fetches exactly its view unless declared with `%%vp --cachable`, so every pan
reruns it. Very dense products over long ranges are slow by nature: narrow
the range or use a lower-cadence product.

**A cell or tool call hangs.** `sciqlop_interrupt_kernel` stops the running
cell. `sciqlop_kernel_vars` and `sciqlop_inspect(name)` show what the kernel
holds.

**SciQLop crashed in the previous session.** `sciqlop_read_crash_report`
returns the log tail, the versions and the last agent tool calls; the call
still in flight is the usual trigger. Diagnose from it, then offer a report
with `sciqlop_open_bug_report(title, body)`: the user reviews and submits
it. Write a diagnosis there, not raw stack dumps or personal paths.

## Rules while debugging

- Code from `sciqlop_exec_python` runs on the kernel thread. Use
  `SciQLop.user_api`, never `._impl` or raw Qt objects, and never call
  methods on a Qt object generically to see what they do. That has crashed
  SciQLop.
- Change one thing at a time and re-run the checks above after each change.
- Do not report a fix until `sciqlop_describe_panel` shows `n_points` above
  zero and no `last_error`, and the screenshot shows the data.
