# Plot comparison ("diff") — design

Status: draft, 2026-10-19. Brainstormed with the project lead.

## 1. Why

Space physicists compare data all the time: this event against that one, this product against
another, this algorithm setting against the default. Today they do it by hand — two windows,
screenshots, ad hoc notebook code. They don't ask for comparison tools because they never had
good ones, so there is no use-case list to wait for.

This design gives SciQLop a **foundation for any comparison**, not one feature. One data model
of "a comparison"; several interchangeable ways to look at it (like GitHub's image diff:
2-up / swipe / onion skin / difference); small plug-ins for new kinds of comparison.

Background reading the design leans on:
- Gleicher et al., *Visual comparison for information visualization*, Information Visualization
  10(4), 2011 — juxtaposition / superposition / explicit encoding.
- Gleicher, *Considerations for visualizing comparison*, IEEE TVCG 24(1), 2018.
- Javed, McDonnel, Elmqvist, *Graphical perception of multiple time series*, IEEE TVCG 2010 —
  overlay wins for local comparison, separate panels for dispersed comparison.
- Superposed epoch analysis (Chree, 1913) — the space-physics pattern for N events.

## 2. Goals, non-goals, anti-goals

Goals
- One model covering: two or more catalog events / time intervals, two products, one product
  with different knob values, and cases not yet thought of.
- The view is switchable without rebuilding the comparison.
- First release ships two views: **Overlay** and **Difference**. Adding a view later is a
  self-contained contribution.
- A comparison can be saved as a panel template and reopened from it (the same way time
  panels are saved today). Workspace session persistence of open panels does not exist for any
  panel kind and is out of scope; once it exists, comparisons ride on the same `to_config`.
- Same feature from the GUI, from `user_api`, and for agents.
- Users stumble on it during normal work (context-menu doors), not only via a menu.

Non-goals (first release)
- Side-by-side, Swipe / onion skin, Superposed epoch, A-vs-B scatter views (designed for, §6.4,
  built later).
- Relative-time axis labels (x axis stays the base's absolute time, §5).
- Comparing panels that are not time panels (XY, projection, scene).
- Resampling spectrograms with different y bins (§6.3).

Anti-goals
- A big modal "Compare" dialog with many modes nobody opens.
- A comparison that silently compares mismatched things (different units, different bins,
  different scales) and draws a plausible-looking but meaningless picture. Mismatches must
  show as a visible message on the plot.
- Per-view special cases in the model. If a view needs new data in the model, the model is wrong.

## 3. The model

Pydantic models, plain data, serialisable as-is.

```
Comparison
  base:       panel tree (exactly what panel_template.panel_tree() saves today)
  dimension:  id of a ComparisonDimension ("time", "product", "settings", plugins…)
  variants:   list[Variant]          # base is the implicit first side
  view:       id of a ComparisonView ("overlay", "difference", …)
  view_options: dict[str, dict]      # per view id, so switching back keeps options

Variant
  label:  str                        # legend / title text, e.g. "2015-10-22 06:01"
  params: dict                       # dimension-specific, validated by the dimension
```

### 3.1 Graph specs — the uniform unit

Every graph of the base panel is described as a **GraphSpec**:

```
GraphSpec
  plot_index:  int          # which plot of the base panel
  node:        product path # what data_provider fetches
  knobs:       dict         # VP knob values (empty for plain products)
  time_offset: float        # seconds; data is fetched at [start+off, stop+off] and shifted back
```

Specs are read from the base **snapshot** (`PanelTemplate.from_panel`), and the inner panel is
built from that same snapshot, so `plot_index` always matches the plots the comparison shows
(the snapshot skipping empty plots of the source panel is then harmless). Only product-backed graphs (non-empty product path)
get specs; function and static graphs are carried along unchanged and are never compared.

A dimension's only job is to turn (base GraphSpecs, Variant) into the variant's GraphSpecs:

| dimension | changes                                                     | params                          |
|-----------|-------------------------------------------------------------|---------------------------------|
| time      | `time_offset` of **every** graph                            | `t0` (variant anchor time)      |
| product   | `node` of **one** target graph                              | `target` (plot, graph), `node`  |
| settings  | `knobs` of **one** target graph                             | `target`, `knobs`               |

Views only ever see "a list of sides, each a list of GraphSpecs, each with a label". A graph
whose spec is identical across all sides is *unchanged*; views draw it once (base styling) and
build nothing comparative for it.

"Other spacecraft" and "model vs data" are product variants with a good label — no new
dimension needed.

### 3.2 Time-shifted, knob-overridden products — the one new data primitive

Decided with the project lead: ghosts are **real product graphs**, not callable graphs.
Callable graphs (`plot_function`) only get an error overlay; plot hints, post-fetch hints, knob
state, prefetch margin, colour axis, labels and spectrogram y handling live only in
`_plot_product` / `_post_plot` (`components/plotting/ui/time_sync_panel.py`). So the product path
gains two optional parameters:

- `time_offset` (seconds): fetch `[start + off, stop + off]`, subtract `off` from returned times.
- `knobs` override: initial knob values for this graph instead of the defaults.

Everything else (hints, caching, error overlays, threading) is then inherited. This is also a
useful feature on its own ("plot this product shifted by 27 days"), and should be reachable from
`user_api` plot calls as a keyword. No SciQLopPlots change is expected; if one turns out
necessary, stop and raise it.

Remote (out-of-process) VPs: if the offset can be applied where the remote path builds its
request, support them; otherwise refuse them in the comparison with an overlay message and a
`simplify:` comment (my call).

The Difference view's computed graph is the one place a callable is needed (it combines two
sides). It fetches both sides through the same offset/knob-aware provider call and must carry the
base graph's plot hints explicitly.

### 3.3 Time alignment

For the time dimension the base has an anchor `t0_base` and each variant a `t0`;
`time_offset = t0 - t0_base`. Anchor choice is a comparison option: event **start** (default),
**centre**, or **end**. Events of different durations are just shifted; duration normalisation
belongs to the future Epoch view. Free time intervals (not catalog events) use their start.

Base and anchor rules (my call):
- From a panel ("Compare with…", Tools menu): base = the panel's current visible range,
  `t0_base` = its start (or centre/end per option); every picked event/interval is a variant.
- From a catalog selection: base = the **first** selected event, the others are variants
  ("Compare: 3 events" = base + 2 variants). Difference therefore needs exactly two selected.
- The user's source panel is never moved; the comparison builds its own inner panel.

## 4. Extension points

Two new EPs, following `SciQLop/core/extensions.py` (`declare(ExtensionPoint(...))`, owner-tagged,
main-thread registration):

- `sciqlop.comparison_dimensions` — `ComparisonDimension(id, label, apply(base_specs, variant) ->
  specs, picker(...) -> QWidget for the wizard's step 3, validate(params))`.
- `sciqlop.comparison_views` — `ComparisonView(id, label, applies(comparison) -> bool | reason,
  build(comparison, options) -> QWidget, default_options)`. `applies` returning a reason lets
  the switcher show a disabled tab with a tooltip ("Difference needs exactly two sides").

Core contributes the three dimensions and the two views through these EPs, like core plot and
panel kinds already do.

## 5. The comparison panel

A new panel kind `comparison` (`SciQLop/core/panel_kinds.py` `PanelKind`), opened in a dock tab
like any panel:

```
┌ Compare: 3 events ─────────────────────────────────────────┐
│ [ Overlay ] [ Difference ]        Align: [start ▾]  ⋯      │
├────────────────────────────────────────────────────────────┤
│   inner time panel built by the current view               │
└────────────────────────────────────────────────────────────┘
```

- Header: one tab per registered view, enabled per `applies`; current view's options; a "⋯"
  menu to edit variants (reopens the wizard pre-filled).
- Decided with the project lead: the base is a **snapshot** of the source panel taken at
  creation; later edits to the source panel don't follow. The inner panel's structure is
  read-only (no product drops, no added plots, no knob edits); zoom and pan are free. Changes go
  through "⋯ ▸ Edit comparison", which reopens the wizard pre-filled and rebuilds.
- Switching view rebuilds only the inner panel from the model; the visible time range carries
  over.
- `to_config` = `Comparison.model_dump()`; `create` rebuilds from it. Data is re-fetched on
  reopen, never stored. Saving uses the existing template save path.
- x axis = the base's absolute time; the header states the alignment ("aligned on event
  start"). Relative-time axis labels are a later improvement.

## 6. Views

### 6.1 Overlay (first release)

One time panel with the base's plots. For each changed graph, each variant adds a ghost graph
on the same plot: same colour family as the base graph, lighter and dashed, legend
`"<graph> — <variant label>"`. Any number of variants; above 6 a notice suggests Epoch (later).

Colormap graphs cannot be overlaid meaningfully: Overlay draws the base colormap and puts a
plot overlay message "spectrogram variants not shown — use Difference (or Swipe, later)".

### 6.2 Difference (first release)

`applies` only with exactly two sides (base + one variant). For each base plot that holds at
least one changed graph (my call: one row pair per **plot**, not per graph):

- row 1: the plot with base and variant overlaid (as Overlay),
- row 2: the computed relation for each of that plot's changed graphs.

Plots with no changed graph appear once, unchanged. A 4-plot panel under the time dimension
becomes 8 rows; that is expected.

Operation option: `A − B` (default for lines), `A / B`, `log10(A / B)` (default for colormaps,
with a diverging colormap centred on 0).

### 6.3 Resampling and mismatch rules (Difference)

- B is linearly interpolated onto A's time grid; samples outside B's span are NaN. Option:
  nearest instead of linear.
- Component counts must match, units must match (from plot hints/metadata when known);
  otherwise the row shows an Error overlay naming the mismatch.
- Colormaps: y bins must be identical per sample, otherwise Error overlay "different energy
  bins — not supported yet". `simplify:` comment: upgrade path is 2D interpolation on A's bins
  in log-y.

### 6.4 Later views (designed for, not built)

| view          | applies when                          | notes                                          |
|---------------|---------------------------------------|------------------------------------------------|
| Side by side  | ≥2 sides                              | sibling panels, synced on *relative* time      |
| Swipe / onion | 2 sides                               | the spectrogram answer; needs a spike: clipping a live QRhi plot via widget mask may not work → fallback swipes grabbed images, re-grabbed after zoom |
| Epoch         | time dimension, ≥3 sides              | x = t − t0 (or fraction of duration), median + quartile band, faint traces |
| Scatter       | 2 sides, line graphs                  | XY plot of A(t) vs B(t) with y = x line         |

Each is one `ComparisonView` contribution; none requires a model change. If one does, revisit §3.

## 7. Entry points

All open the same wizard, more or less pre-filled. Registered through the commands/menus EP
(plan 2a):

- **Tools ▸ Compare…** — empty wizard.
- **Panel context menu ▸ Compare with…** — base = this panel.
- **Catalog: 2+ events selected ▸ Compare** — dimension = time, variants = the events; base =
  the panel currently showing the catalog (if several, ask; if none, the wizard asks for a base
  panel). The event table's context menu (`catalog_browser.py`) has no extension-point hook
  today, and `CATALOG_TREE`'s context is catalog-level only: this needs a new menu location
  with a selected-events context.

Wizard (one dialog, three steps visible at once, not a multi-page wizard):

1. Base panel (dropdown of open time panels).
2. What changes — radio list of registered dimensions.
3. Compare against — the selected dimension's `picker` widget.

"Compare" creates the comparison panel with view = Overlay.

## 8. Python and agents

`user_api` (published API — additive only, `@on_main_thread` wrappers per house rules):

```python
cmp = compare(panel, over="time", variants=catalog.events[:3], view="overlay")
cmp.view = "difference"
cmp.variants            # read-only labels/params
cmp.options["difference"]["operation"] = "ratio"
```

`over=` takes a dimension id; `variants=` accepts dimension-friendly values (events / time
ranges for time, product paths for product, knob dicts for settings) which the dimension turns
into `Variant`s. Agent tools: `create_comparison` and `set_comparison_view`, built on this API,
listed in the agent tool surface and skill docs.

## 9. Constraints

- Follow `docs/qt-lifetime-patterns.md`; the comparison panel owns its inner panel and rebuilds
  it on view switch — no slots wired to children's `destroyed` that call back into the parent.
- No SciQLopPlots changes in the first release. If one turns out necessary, stop and raise it.
- VP knobs, ISTP plot hints, and provider error overlays must keep working on ghost graphs
  (they go through `_plot_product`, §3.2) and on difference graphs (hints carried explicitly).
- Tests: pytest-qt; model and dimension logic tested without Qt; one GUI test per view and per
  entry point; persistence round-trip.

## 10. Left to the builder

- Module placement (suggested `SciQLop/components/comparison/` with `backend/` model + dimensions,
  `ui/` panel + wizard + views).
- Exact ghost styling within "lighter, dashed, same colour family".
- Wizard widget details, as long as it stays one dialog with the three steps.
- How the time picker offers free time intervals besides catalog events.
- Phasing the first release into plans (suggested: model + side source → dimensions → panel
  kind + persistence → Overlay → Difference → wizard + entry points → user_api + agents).
