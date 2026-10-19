# Plot Comparison Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A "Comparison" panel kind: one model (base snapshot + dimension + variants) shown through switchable views, with Overlay and Difference first.

**Architecture:** Pure-Python model and math in `SciQLop/components/comparison/backend/`, Qt views/panel/wizard in `SciQLop/components/comparison/ui/`. Dimensions and views are two new extension points. Ghost graphs are ordinary product graphs plotted with a new `time_offset` keyword on the product path; only the Difference graph is a callable.

**Tech Stack:** Python 3.13, PySide6, SciQLopPlots, Pydantic v2, numpy, pytest-qt.

**Spec:** `docs/superpowers/specs/2026-10-19-plot-comparison-design.md`

## Global Constraints

- Run everything with `uv run`; canonical test run is `uv run pytest --no-xvfb <target>`.
- **One build/test invocation at a time, in the foreground, waited out.** Never background or overlap pytest runs (each GUI pytest process is multi-GB).
- Work and commit on `main`, no branches. Commit with explicit pathspecs; the tree has unrelated untracked files that must not be committed. Never push.
- `user_api/` is published: additive changes only, every Qt-touching wrapper method is `@on_main_thread`.
- Follow `docs/qt-lifetime-patterns.md`: never call into a parent from a slot wired to a child's `destroyed`.
- No SciQLopPlots changes. If one turns out necessary, stop and report.
- Code style per CLAUDE.md: small functions, data over code, no comment-decorated blocks, `simplify:` comments on deliberate corner cuts.
- Wait in GUI tests with `qtbot.waitUntil`, never a fixed `qtbot.wait(N)` as an assertion.
- GUI tests never leave parentless top-level widgets: `qtbot.addWidget(w)` for bare widgets, docked panels closed with `main_window.remove_panel` + `qtbot.waitUntil` (pattern: `tests/test_panel_kinds.py` `demo_kinds`). Full-suite teardown segfaults have come from leftovers before.
- Fetch callbacks run on worker threads: resolve `ProductsModel.node` / `providers.get` / knobs on the main thread at build time and capture them; callbacks only fetch and reshape, never touch Qt.
- `panel` arguments may be `user_api` wrappers: unwrap with `panel._get_impl_or_raise()` when present before `PanelTemplate.from_panel`.
- Extension point ids: `sciqlop.comparison_dimensions`, `sciqlop.comparison_views`. Panel kind id: `sciqlop.comparison`. Core view ids: `overlay`, `difference`. Core dimension ids: `time`, `product`, `settings`.

## Review Focus

1. A variant whose time window has no data (event outside product coverage) → the ghost is empty, nothing raises, the base still draws. Test in Task 5.
2. A base panel holding a static/function graph (empty product path) → that graph is carried unchanged and never compared; the comparison still builds. Test in Task 2.
3. Reopening a saved comparison whose product is no longer in the products tree → the panel opens, the missing graph is skipped with a log warning, and every **other** ghost still lands on the plot holding its base graph (no index shift). Test in Task 7, with a 2-plot base whose plot 0 only holds the missing product.
4. Difference where B covers only part of A's time span → NaN outside B's span, no extrapolation. Test in Task 4.
5. The source panel is closed after the comparison was created → the comparison is unaffected (snapshot). Test in Task 7.

Also covered (found in review): ghosts must not raise the "No data here" coverage banner (Task 1); ISTP fill values must not turn a difference into a ±1e31 wall (Task 4/6); same-count but different components (`Bx/By/Bz` vs `Bn/Be/Bz`) and different units are refused in **both** views (Task 5/6); a base with no time range yet is refused with a clear message (Task 3).

---

## File Structure

```
SciQLop/components/comparison/
  __init__.py
  backend/
    __init__.py
    model.py          # Variant, GraphSpec, Side, Comparison, base_specs(), sides(), changed_keys()
    dimensions.py     # ComparisonDimension + EP + core time/product/settings dimensions
    views.py          # ComparisonView + EP + available_views()
    difference.py     # resampling + relations (pure numpy)
    checks.py         # mismatch checks shared by both views (units, components, remote)
  ui/
    __init__.py
    inner_panel.py    # build_inner_panel(), read-only TimeSyncPanel from the snapshot
    styling.py        # ghost styling
    overlay_view.py   # build_overlay()
    difference_view.py# build_difference()
    panel.py          # ComparisonPanel widget
    panel_kind.py     # PanelKind contribution + view/dimension core contributions
    pickers.py        # step-3 picker widgets + PICKERS {dimension_id: factory} (keeps backend Qt-free)
    wizard.py         # CompareDialog
    commands.py       # palette commands + menu entries
SciQLop/user_api/comparison.py
SciQLop/components/agents/tools/comparison_tool.py
```

Modified: `components/plotting/ui/time_sync_panel.py` (time_offset, `read_only` panel flag), `components/plotting/core_kinds.py` (no coverage offer for shifted graphs), `components/plotting/panel_template.py` (`apply` returns plots), `user_api/plot/_panel.py` + `_plots.py` (time_offset keyword), `core/menus.py` (new location), `components/catalogs/ui/catalog_browser.py` (event-menu hook), `components/catalogs/backend/panel_manager.py` (`panels_showing`), `components/command_palette/arg_types.py` (`EventsArg`), `components/extension_points.py` (registration), `CHANGELOG.md`.

---

### Task 1: Time-shifted product graphs

**Files:**
- Modify: `SciQLop/components/plotting/ui/time_sync_panel.py` (`_ProductCallbackBase`, `_plot_product`)
- Modify: `SciQLop/user_api/plot/_panel.py:281` (`PlotPanel.plot_product`), and the `plot_product`/`plot(product=...)` path of `SciQLop/user_api/plot/_plots.py` that forwards kwargs
- Test: `tests/test_time_offset_products.py`

**Interfaces:**
- Produces: `shift_buffers(result, offset: float)` in `time_sync_panel.py` — returns the provider buffers (list/tuple `[t, ...]`, or `{"data": [t, ...], "color": c}`, or empty) with `t - offset`, never mutating the input arrays.
- Produces: `_plot_product(p, product, *, time_offset: float = 0.0, product_inputs=None, ...)`; `plot_product(...)` forwards it. `_ProductCallbackBase.__init__(..., time_offset: float = 0.0)`; `_fetch(start, stop)` fetches `[start + time_offset, stop + time_offset]` and returns `shift_buffers(result, time_offset)`.
- Produces: `PlotPanel.plot_product(..., time_offset=_UNSET)` (seconds, float).
- `components/plotting/core_kinds.py` `_plot_timeseries`: skip `offer_jump_to_data` when `kwargs.get("time_offset")` is non-zero (the notice compares coverage against the unshifted panel range and would show a false "No data here" banner, then hijack the panel with "Go to first data").
- A remote (out-of-process) product with a non-zero `time_offset`: `_plot_product` logs an error and returns `None` (`simplify:` comment: apply the offset where `plot_remote` builds its request when remote comparisons are needed). `plot_product_or_raise` then raises its usual ValueError.

- [ ] **Step 1: Write the failing tests**

```python
def test_shift_buffers_subtracts_offset_without_mutating():
    t = np.array([10.0, 20.0]); y = np.array([1.0, 2.0])
    out = shift_buffers([t, y], 5.0)
    assert list(out[0]) == [5.0, 15.0] and list(t) == [10.0, 20.0]
    assert out[1] is y

def test_shift_buffers_handles_colored_and_empty():
    t = np.array([10.0]); out = shift_buffers({"data": [t, t], "color": "c"}, 1.0)
    assert list(out["data"][0]) == [9.0] and out["color"] == "c"
    assert shift_buffers([], 1.0) == []

def test_time_offset_fetches_shifted_window(plot_panel, qtbot):
    seen = []
    def cb(start, stop):
        seen.append((start, stop)); x = np.linspace(start, stop, 10); return x, x * 0
    vp = create_virtual_product("test_time_offset/vp", cb, VirtualProductType.Scalar, labels=["y"])
    plot_panel.time_range = TimeRange(1000.0, 2000.0)
    plot_panel.plot_product(vp, time_offset=86400.0)
    qtbot.waitUntil(lambda: seen)
    start, stop = seen[-1]
    assert start <= 1000.0 + 86400.0 and stop >= 2000.0 + 86400.0   # prefetch margin may widen it
    assert start > 86400.0

def test_shifted_graph_does_not_offer_jump_to_data(plot_panel, qtbot):
    # VP with coverage = [1000 + 86400, 2000 + 86400] (only the shifted window); panel shows [1000, 2000]
    # plot with time_offset=86400 -> no CoverageNotice child on the panel's impl
```

- [ ] **Step 2: Run** `uv run pytest --no-xvfb tests/test_time_offset_products.py -v` — expected FAIL (`shift_buffers` not defined / unexpected keyword `time_offset`).
- [ ] **Step 3: Implement** `shift_buffers` (copies the time array only; value arrays are passed through by identity — spectrogram memory), the coverage skip in `core_kinds.py`, the callback offset, the `time_offset` pop in `_plot_product` (passed to both `_plot_product_callback` and `_specgram_callback`), the remote refusal, and the `user_api` keyword with a docstring line ("Seconds; data is fetched `time_offset` later and drawn at the panel's time, e.g. 27 days to overlay the next solar rotation.").
- [ ] **Step 4: Run** the same command — expected PASS. Then run `uv run pytest --no-xvfb tests/test_plot_panel_plot_args.py tests/test_panel_tree.py -q` — expected all pass.
- [ ] **Step 5: Commit** `feat(plotting): plot a product shifted in time` (pathspecs: the four source files + the test).

---

### Task 2: Comparison model

**Files:**
- Create: `SciQLop/components/comparison/__init__.py`, `backend/__init__.py`, `backend/model.py`
- Test: `tests/comparison/test_model.py` (no Qt, no main window)

**Interfaces:**
- Consumes: `PanelTemplate`, `PlotModel`, `ProductModel` from `SciQLop/components/plotting/panel_template.py`.
- Produces (Pydantic `BaseModel`s):
  - `Variant(label: str, params: dict = {})`
  - `GraphSpec(plot_index: int, product_index: int, path: str, knobs: dict = {}, time_offset: float = 0.0, is_colormap: bool = False, y_axis: str | None = None)` with `key -> tuple[int, int]` property `(plot_index, product_index)`.
  - `Side(label: str, specs: list[GraphSpec], t0: float | None = None, duration: float | None = None)` — `t0`/`duration` (epoch s / s) are filled by the time dimension and stay `None` otherwise; unused today, they let a later Epoch view work without a model change.
  - `Anchor = Literal["start", "center", "end"]`
  - `Comparison(base: dict, dimension: str, variants: list[Variant], view: str = "overlay", anchor: Anchor = "start", view_options: dict[str, dict] = {})` — `base` is `PanelTemplate.to_tree()` output; `template() -> PanelTemplate` rebuilds it via `PanelTemplate.from_tree`.
  - `base_specs(template: PanelTemplate) -> list[GraphSpec]` — one spec per product with a non-empty `path`, in plot then product order; skips non-timeseries plots.
  - `sides(comparison, base_side, apply) -> list[Side]` = `[base_side(specs, comparison)] + [apply(specs, v, comparison) for v in comparison.variants]` with `specs = base_specs(comparison.template())`. The two callables are the dimension's (Task 3), passed in so the model has no EP dependency.
  - `changed_keys(sides: list[Side]) -> set[tuple[int, int]]` — keys whose spec differs in any side.

- [ ] **Step 1: Write the failing tests**

```python
def _template(*plots):  # helper: PanelTemplate(name="P", plots=[PlotModel(products=[ProductModel(path=p) ...]) ...])

def test_base_specs_skip_products_without_path():
    t = _template(["a//b", ""], ["c//d"])
    assert [(s.plot_index, s.product_index, s.path) for s in base_specs(t)] == [(0, 0, "a//b"), (1, 0, "c//d")]

def test_comparison_round_trips_through_json():
    c = Comparison(base=_template(["a//b"]).to_tree(), dimension="time", variants=[Variant(label="v", params={"start": 1.0, "stop": 2.0})])
    assert Comparison.model_validate_json(c.model_dump_json()) == c
    assert c.template().plots[0].products[0].path == "a//b"

def test_changed_keys_ignores_identical_specs():
    base = Side(label="b", specs=[GraphSpec(plot_index=0, product_index=0, path="a"), GraphSpec(plot_index=1, product_index=0, path="c")])
    var = Side(label="v", specs=[GraphSpec(plot_index=0, product_index=0, path="a", time_offset=5.0), GraphSpec(plot_index=1, product_index=0, path="c")])
    assert changed_keys([base, var]) == {(0, 0)}
```

- [ ] **Step 2: Run** `uv run pytest --no-xvfb tests/comparison/test_model.py -v` — FAIL (import error).
- [ ] **Step 3: Implement** `model.py` (`is_colormap` from `ProductModel.is_colormap`).
- [ ] **Step 4: Run** — PASS.
- [ ] **Step 5: Commit** `feat(comparison): comparison model`.

---

### Task 3: Dimensions and views extension points

**Files:**
- Create: `backend/dimensions.py`, `backend/views.py`
- Test: `tests/comparison/test_dimensions.py`, `tests/comparison/test_views.py`

**Interfaces:**
- Produces in `dimensions.py`:
  - `@dataclass(frozen=True) ComparisonDimension(id: str, label: str, noun: str, apply: Callable[[list[GraphSpec], Variant, Comparison], Side], validate: Callable[[dict], None], base_side: Callable[[list[GraphSpec], Comparison], Side])` — **Qt-free**; the wizard's picker widgets are mapped by id in `ui/pickers.py` (Task 8). `noun` feeds the panel header ("events", "products", "settings").
  - `COMPARISON_DIMENSIONS = declare(ExtensionPoint("sciqlop.comparison_dimensions", ComparisonDimension, ...))` — declared here (importing the module declares it), never again elsewhere.
  - `anchor_time(start: float, stop: float, anchor: Anchor) -> float`; `ANCHOR_LABELS = {"start": "start", "center": "centre", "end": "end"}` for display.
  - `base_range(comparison) -> tuple[float, float]` — from the template's `time_range`; raises `ValueError("the base panel has no visible time range yet")` when it is `None`.
  - Core functions (contributed in Task 7): `apply_time` — `params = {"start": float, "stop": float}` epoch s; offset = `anchor_time(variant) - anchor_time(*base_range(comparison))` with `comparison.anchor`, applied to every spec; returned Side has `t0 = anchor_time(variant)`, `duration = stop - start`. `validate_time` also rejects `stop <= start`. `apply_product` — `params = {"target": [plot_index, product_index], "path": str}`, replaces `path` of that spec only (also sets `is_colormap` from `params.get("is_colormap", spec.is_colormap)`). `apply_settings` — `params = {"target": [...], "knobs": dict}`, merges knobs into that spec only. Both return `Side(label=variant.label, specs=...)`. Each `validate_*` raises `ValueError` naming the missing/bad key. Base sides: time → `Side(label=template name, specs, t0=anchor_time(*base_range), duration=stop - start)`; product/settings → `Side(label=template name, specs)`.
  - `dimension(id) -> ComparisonDimension` and `resolve_sides(comparison) -> list[Side]` (= `sides(comparison, d.base_side, d.apply)` for `d = dimension(comparison.dimension)`).
- Produces in `views.py`:
  - `@dataclass(frozen=True) ComparisonView(id: str, label: str, applies: Callable[[Comparison, list[Side]], str | None], build: Callable[[Comparison, list[Side], dict, tuple[float, float] | None, QWidget], QWidget], default_options: dict = field(default_factory=dict), order: int = 0)` — `applies` returns `None` when usable, else the reason shown as tooltip. `build(comparison, sides, options, time_range, parent)`: `time_range` is the range carried from the previous view (`None` = the base's); the returned widget exposes a `time_range` attribute (a `TimeSyncPanel` already does), which is how the panel carries the range on the next switch — no per-view special case. (`QWidget` appears only as a type annotation under `TYPE_CHECKING`, so `views.py` stays importable without Qt widgets.)
  - `COMPARISON_VIEWS = declare(ExtensionPoint("sciqlop.comparison_views", ComparisonView, ...))`
  - `available_views(comparison, sides) -> list[tuple[ComparisonView, str | None]]` sorted by `(order, id)`.
  - `options_for(comparison, view) -> dict` = `{**view.default_options, **comparison.view_options.get(view.id, {})}`.

- [ ] **Step 1: Write the failing tests**

```python
def test_time_dimension_shifts_every_graph_by_anchor_difference():
    c = _comparison(time_range=(100.0, 200.0), variants=[Variant(label="e", params={"start": 1100.0, "stop": 1300.0})])
    side = apply_time(base_specs(c.template()), c.variants[0], c)
    assert {s.time_offset for s in side.specs} == {1000.0}
    assert (side.t0, side.duration) == (1100.0, 200.0)
    c2 = c.model_copy(update={"anchor": "end"})
    assert {s.time_offset for s in apply_time(base_specs(c2.template()), c2.variants[0], c2).specs} == {1100.0}

def test_time_dimension_refuses_base_without_range():
    c = _comparison(time_range=None, variants=[Variant(label="e", params={"start": 1.0, "stop": 2.0})])
    with pytest.raises(ValueError, match="no visible time range"):
        apply_time(base_specs(c.template()), c.variants[0], c)

def test_product_dimension_changes_only_target():
    ...  # two specs; target [0, 1] -> only that path changes

def test_settings_dimension_merges_knobs():
    ...  # base knobs {"a": 1, "b": 2}, params knobs {"b": 3} -> {"a": 1, "b": 3}

def test_validate_rejects_missing_keys():
    with pytest.raises(ValueError, match="start"): validate_time({"stop": 1.0})
    with pytest.raises(ValueError, match="stop"): validate_time({"start": 2.0, "stop": 2.0})

def test_available_views_reports_reason():
    # contribute a view whose applies returns "needs two sides" under owned_by("cmp_test"); assert it is listed with that reason; remove_owner after

def test_dimensions_module_does_not_import_qt_widgets():
    # run in a subprocess: `python -I -c "import SciQLop.components.comparison.backend.dimensions, sys; assert 'PySide6.QtWidgets' not in sys.modules"`
```

(Time-range helper: base template `time_range=TimeRangeModel(start=iso, stop=iso)`; convert with `datetime.fromisoformat(...).timestamp()`, like `PanelTemplate._time_range`.)

- [ ] **Step 2: Run** `uv run pytest --no-xvfb tests/comparison -v` — FAIL.
- [ ] **Step 3: Implement** both modules. Contributing the core dimensions/views is Task 7's job; tests contribute what they need under a test owner and `remove_owner` it in a fixture.
- [ ] **Step 4: Run** — PASS.
- [ ] **Step 5: Commit** `feat(comparison): dimension and view extension points`.

---

### Task 4: Difference math

**Files:**
- Create: `backend/difference.py`
- Test: `tests/comparison/test_difference.py`

**Interfaces:**
- Produces:
  - `class ComparisonMismatch(ValueError)`.
  - `Operation = Literal["difference", "ratio", "log_ratio"]`; `relate(a: np.ndarray, b: np.ndarray, op: Operation) -> np.ndarray` — `a - b`, `a / b`, `log10(a / b)`; every non-finite result (division by zero, non-positive `log_ratio` inputs) becomes NaN, computed under `np.errstate` (no warning spam). Unknown `op` → `ValueError` listing the three.
  - `mask_fill(values: np.ndarray, fill_value: float | None) -> np.ndarray` — copy with NaN where `values == fill_value` (when given) or `|values| > 1e30` (ISTP fill fallback).
  - `resample(t_src, values, t_dst, method: str = "linear") -> np.ndarray` — per column (`values` 1-D or `(n, k)`), `np.interp` for `"linear"`, nearest index for `"nearest"`; NaN where `t_dst` is outside `[t_src[0], t_src[-1]]`; empty source → all NaN.
  - `line_relation(a: list, b: list, op, method) -> list` — `a`, `b` are `[t, values]`; raises `ComparisonMismatch("different number of components: 3 vs 1")` when column counts differ; returns `[t_a, relate(values_a, resample(t_b, values_b, t_a))]`.
  - `colormap_relation(a: list, b: list, op, method) -> list` — `[t, y, z]`; bins must be constant in time and equal (`np.allclose`) for A and B, else `ComparisonMismatch("different energy bins — not supported yet")`, with a `simplify:` comment (upgrade: 2D interpolation on A's bins in log-y). Returns `[t_a, y_a, relate(z_a, resample(t_b, z_b, t_a))]`.

- [ ] **Step 1: Write the failing tests**

```python
def test_resample_is_nan_outside_source_span():
    out = resample(np.array([10.0, 20.0]), np.array([1.0, 3.0]), np.array([5.0, 15.0, 25.0]))
    assert np.isnan(out[0]) and out[1] == 2.0 and np.isnan(out[2])

def test_resample_nearest():
    assert resample(np.array([0.0, 10.0]), np.array([1.0, 2.0]), np.array([4.0, 6.0]), "nearest").tolist() == [1.0, 2.0]

def test_line_relation_difference_on_a_grid():
    t = np.array([0.0, 1.0, 2.0])
    _, d = line_relation([t, np.array([[3.0], [3.0], [3.0]])], [t, np.array([[1.0], [2.0], [3.0]])], "difference", "linear")
    assert d[:, 0].tolist() == [2.0, 1.0, 0.0]

def test_component_mismatch_raises():
    t = np.array([0.0, 1.0])
    with pytest.raises(ComparisonMismatch, match="components"):
        line_relation([t, np.ones((2, 3))], [t, np.ones((2, 1))], "difference", "linear")

def test_log_ratio_of_nonpositive_is_nan():
    assert np.isnan(relate(np.array([1.0]), np.array([0.0]), "log_ratio")[0])

def test_ratio_by_zero_is_nan_not_inf():
    assert np.isnan(relate(np.array([1.0]), np.array([0.0]), "ratio")[0])

def test_mask_fill_hides_istp_fill():
    out = mask_fill(np.array([1.0, -1e31, 2.0, -999.0]), -999.0)
    assert out[0] == 1.0 and np.isnan(out[1]) and np.isnan(out[3])

def test_colormap_bins_mismatch_raises():
    t = np.array([0.0, 1.0]); z = np.ones((2, 2))
    with pytest.raises(ComparisonMismatch, match="bins"):
        colormap_relation([t, np.array([1.0, 2.0]), z], [t, np.array([1.0, 3.0]), z], "log_ratio", "linear")
```

- [ ] **Step 2: Run** `uv run pytest --no-xvfb tests/comparison/test_difference.py -v` — FAIL.
- [ ] **Step 3: Implement.** Accept 1-D values by treating them as one column and returning the same shape they came in.
- [ ] **Step 4: Run** — PASS.
- [ ] **Step 5: Commit** `feat(comparison): difference math`.

---

### Task 5: Read-only inner panel, shared checks, Overlay view

**Files:**
- Modify: `SciQLop/components/plotting/ui/time_sync_panel.py` — `TimeSyncPanel.__init__(..., show_search_overlay=True, read_only: bool = False)`: when `read_only`, skip `accept_drop_rules(self)`, skip the search overlay, call `setAcceptDrops(False)`, and `_menu_context`-based `add_menu_entries(menu, PANEL, ...)` is not called (so the inner panel never offers "Compare with…" on itself). Inspector sections stay.
- Modify: `SciQLop/components/plotting/panel_template.py` — `PanelTemplate.apply(panel) -> list` returns the per-`PlotModel` results of `_restore_plot`, index-aligned with `self.plots` (`None` where nothing was restored). Existing callers (`panel_template.py:264`, `proxy_share.py:163`, `agents/tools/_builder.py:1157`) ignore it.
- Create: `backend/checks.py`, `ui/__init__.py`, `ui/inner_panel.py`, `ui/styling.py`, `ui/overlay_view.py`
- Test: `tests/comparison/test_checks.py` (no Qt), `tests/comparison/test_overlay_view.py`

**Interfaces:**
- Consumes: `resolve_sides`, `changed_keys`, `GraphSpec`, `plot_product(target, path_list, time_offset=..., product_inputs=...)` (Task 1), `resolve_product_path`, `_place_on_axis` from `panel_template.py`, `ComparisonMismatch` (Task 4).
- Produces in `backend/checks.py` (pure; takes already-resolved hints so it stays Qt-free):
  - `compatible(a: PlotHints, b: PlotHints, colormap: bool) -> str | None` — `None` when comparable; else `"different units: nT vs mV"` (y unit, or z unit for colormaps, only when both known) or `"different components: Bx/By/Bz vs Bn/Be/Bz"` (when both `component_labels` known and differ).
  - `is_remote(path: str) -> bool` — `remote_registry().is_remote(resolve_product_path(path))`.
- Produces in `ui/inner_panel.py`:
  - `build_inner_panel(comparison, time_range: tuple[float, float] | None, parent) -> tuple[TimeSyncPanel, list]` — `TimeSyncPanel(name=..., parent=parent, time_range=..., read_only=True)`, then the base template applied with its `time_range` replaced by `time_range` when given; returns the panel and `apply()`'s per-`PlotModel` list. **All later lookups of "the plot for `spec.plot_index`" use this list, never `panel.plots()`**: a base plot whose products all went missing leaves `None` there and its ghosts are skipped, so nothing shifts onto the wrong plot.
  - `resolve_hints(spec) -> PlotHints | None` — main-thread lookup of `provider.plot_hints(node)` for the spec's path (`None` when the product is missing).
- Produces in `ui/styling.py`:
  - `ghost_style(graph, base_graph, index: int)` — per component: base component colour `.lighter(130 + 20 * index)`, dash line style (same component setters the `user_api` `Line` wrapper uses). First verify with a 2-component VP that `graph.components()` is populated right after `plot_product` (labels are passed at creation); only if it is not, re-apply on first data with the graph as receiver context.
- Produces in `ui/overlay_view.py`:
  - `add_ghost(plot, spec: GraphSpec, base_graph, label: str, index: int)` — refuses before plotting, with an Info message on that plot's overlay (same overlay API `_PlotErrorReporter` uses), when `checks.compatible(resolve_hints(base), resolve_hints(spec), spec.is_colormap)` returns a reason (`f"{label}: not overlaid — {reason}"`). Otherwise plots via `plot_product(plot, resolve_product_path(spec.path), time_offset=spec.time_offset, product_inputs=spec.knobs or None)`, places it on the base graph's axis with `_place_on_axis(plot, graph, spec.y_axis)`, names it `f"{base_name} — {label}"`, styles it with `ghost_style`. When `plot_product` returns `None` (remote product with an offset, or product missing): Info message `f"{label}: {spec.path} could not be plotted"` and continue.
  - `build_overlay(comparison, sides, options, time_range, parent) -> QWidget` — inner panel + one ghost per (variant side, changed key) on non-colormap specs; for changed colormap specs, an Info message on that plot: `"spectrogram variants are not shown in Overlay — use Difference"`. Above 6 variants, an Info message on the first plot: `"many variants — an Epoch view will summarise them better"`. When a variant's `duration` exceeds the base's by more than 10 %: Info `"some variants are longer than the view; only the first {base duration} are shown"`.
  - `applies_overlay(comparison, sides) -> str | None` — `None` if any changed key exists, else `"nothing differs between the sides"`.

- [ ] **Step 1: Write the failing tests** (VP-based, like `tests/test_plot_panel_plot_args.py:62`; every built widget goes through `qtbot.addWidget`)

```python
def test_compatible_reports_units_and_components():
    nT = PlotHints(y=AxisHints(unit="nT"), component_labels=["Bx", "By", "Bz"])
    assert compatible(nT, PlotHints(y=AxisHints(unit="mV")), False) == "different units: nT vs mV"
    assert "different components" in compatible(nT, PlotHints(y=AxisHints(unit="nT"), component_labels=["Bn", "Be", "Bz"]), False)
    assert compatible(nT, PlotHints(), False) is None          # unknown on one side: allowed
```
(Check the real `PlotHints` / axis-hints class and field names in `SciQLop/core/plot_hints.py` first and use them in the test.)

```python
def test_overlay_adds_one_ghost_per_variant(main_window, qtbot):
    comparison = _time_comparison_of_vp(variants=2)        # helper: VP "test_cmp/vp", base snapshot, two time variants
    panel = build_overlay(comparison, resolve_sides(comparison), {}, None, None); qtbot.addWidget(panel)
    plot = panel.plots()[0]
    qtbot.waitUntil(lambda: len(plot_graphs(plot)) == 3)
    assert [g.name() for g in plot_graphs(plot)][1].endswith("— " + comparison.variants[0].label)

def test_overlay_ghost_with_no_data_stays_empty_without_error(main_window, qtbot):
    # VP callback returns empty arrays when start > some threshold; variant lies beyond it
    # assert the ghost exists, base graph got data, and the ghost callback's last_error is None

def test_overlay_refuses_mismatched_units(main_window, qtbot):
    # product comparison between two VPs whose hints have units nT and mV -> only the base graph on the plot

def test_inner_panel_is_read_only(main_window, qtbot):
    panel, _ = build_inner_panel(comparison, None, None); qtbot.addWidget(panel)
    assert not panel.acceptDrops()
    assert not panel.findChildren(ProductSearchOverlay)
```

- [ ] **Step 2: Run** `uv run pytest --no-xvfb tests/comparison/test_checks.py tests/comparison/test_overlay_view.py -v` — FAIL.
- [ ] **Step 3: Implement.** `plot_graphs` is in `SciQLop/components/plotting/panel_introspection.py`.
- [ ] **Step 4: Run** — PASS; then `uv run pytest --no-xvfb tests/test_panel_tree.py tests/test_panel_kinds.py tests/test_plot_panel_plot_args.py -q` — PASS (the `apply` return and `read_only` changes).
- [ ] **Step 5: Commit** `feat(comparison): read-only inner panel and overlay view`.

---

### Task 6: Difference view

**Files:**
- Create: `ui/difference_view.py`
- Test: `tests/comparison/test_difference_view.py`

**Interfaces:**
- Consumes: `build_inner_panel`, `resolve_hints` (Task 5), `add_ghost` (Task 5), `checks.compatible`, `checks.is_remote` (Task 5); `line_relation`, `colormap_relation`, `mask_fill`, `ComparisonMismatch` (Task 4); `shift_buffers`, `plot_function`, `_with_y_axis`, `_y_is_descending` from `time_sync_panel.py`.
- Produces:
  - `applies_difference(comparison, sides) -> str | None` — `"Difference needs exactly two sides"` unless `len(sides) == 2`; `"nothing differs between the sides"` without changed keys.
  - `relation_callback(a: ResolvedSide, b: ResolvedSide, op: Operation, method: str, colormap: bool) -> Callable[[float, float], list]` where `ResolvedSide = (provider, node, knobs, time_offset, fill_value)` is resolved **on the main thread at build time** (Global Constraints). The callback only: `provider._get_data(node, start + off, stop + off, knobs=knobs or None)` → `shift_buffers` → for colormaps `_with_y_axis` and the same descending-y flip as `_specgram_callback` (so the relation row is not upside down relative to its base row) → `mask_fill` on values with each side's `fill_value` → `line_relation` / `colormap_relation`. A `ComparisonMismatch` propagates, so `plot_function`'s error overlay shows it. `simplify:` comment: each side is fetched twice (ghost + relation); reuse the ghost's buffers when this gets slow.
  - Refusals at build time, as an Error message on the relation row's plot instead of a relation graph: `checks.compatible(...)` reason; `"remote products are not supported in the Difference view"` when `checks.is_remote` is true for either side (same `simplify:` as Task 1).
  - `build_difference(comparison, sides, options, time_range, parent) -> QWidget` — inner panel; for each base plot (from `build_inner_panel`'s list) with ≥1 changed key: ghost for the variant on that plot (colormaps excluded, as in Overlay), then a relation plot placed right after it: `plot_function(panel, callback, ...)` appends it, then `panel.move_plot(new_plot, base_position + 1)` (both exist in the bindings; `base_position` = the base plot's current index in `panel.plots()`, recomputed after each move). Line relations: `plot_function(panel, cb, labels=<base component labels>, name=f"{name}: {symbol}", plot_type=PlotType.TimeSeries)`. Colormap relations: `graph_type=GraphType.ColorMap, y_log_scale=True, z_log_scale=False`, diverging gradient, symmetric z range from the data's max |z| (product colormaps default to log z, which cannot show negatives). Register the base graph's hints on the relation plot (`_get_or_create_registry(plot).register(graph, hints)`) with the y label prefixed by the symbol, so units and labels show. Symbols: `A − B`, `A / B`, `log₁₀(A / B)`.
  - `default_options = {"operation": "difference", "method": "linear"}`; colormap relations use `"log_ratio"` while `operation` is left at its default. An `operation` outside `Operation` is replaced by the default with a log warning (saved options can come from older or hand-edited templates).

- [ ] **Step 1: Write the failing tests**

```python
def test_difference_adds_a_relation_row_after_each_changed_plot(main_window, qtbot):
    comparison = _settings_comparison_of_vp(base_knobs={"gain": 1.0}, variant_knobs={"gain": 3.0})  # VP returns gain * ones
    panel = build_difference(comparison, resolve_sides(comparison), {"operation": "difference", "method": "linear"}, None, None)
    qtbot.addWidget(panel)
    qtbot.waitUntil(lambda: len(panel.plots()) == 2)
    rel = plot_graphs(panel.plots()[1])[0]
    qtbot.waitUntil(lambda: _y_values(rel).size > 0)       # helper reading graph data via the user_api wrapper
    assert np.allclose(_y_values(rel), -2.0)

def test_difference_not_applicable_with_three_sides():
    assert applies_difference(c3, resolve_sides(c3)) == "Difference needs exactly two sides"

def test_difference_masks_fill_values(main_window, qtbot):
    # VP returns -1e31 on half its samples for the variant side -> relation is NaN there, finite elsewhere

def test_spectrogram_relation_keeps_base_orientation(main_window, qtbot):
    # VP spectrogram with descending y; relation graph's y is ascending, like the base row's
```

- [ ] **Step 2: Run** `uv run pytest --no-xvfb tests/comparison/test_difference_view.py -v` — FAIL.
- [ ] **Step 3: Implement.** Confirm `plot_function` on a `TimeSyncPanel` yields a time axis with `plot_type=PlotType.TimeSeries` passed explicitly.
- [ ] **Step 4: Run** — PASS.
- [ ] **Step 5: Commit** `feat(comparison): difference view`.

---

### Task 7: Comparison panel, panel kind, persistence

**Files:**
- Create: `ui/panel.py`, `ui/panel_kind.py`
- Modify: `SciQLop/components/extension_points.py` — import `SciQLop.components.comparison.ui.panel_kind` after the time panel kind line.
- Test: `tests/comparison/test_comparison_panel.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `panel_kind.py` imports `backend.dimensions` and `backend.views` (importing them declares the two EPs — never call `declare` here) and contributes, owner `"sciqlop"`: the three core dimensions (`time`/"events", `product`/"products", `settings`/"settings"), the two views (`overlay` order 0, `difference` order 10), and `PanelKind(COMPARISON_PANEL, "Comparison", create=_create, to_config=_to_config, icon=<an existing registered icon name>, in_new_menu=False)` with `COMPARISON_PANEL = "sciqlop.comparison"`.
  - `ComparisonPanel(QWidget)(name: str, comparison: Comparison)`: header = `QTabBar` (one tab per `available_views`, disabled + tooltip when a reason is returned), alignment combo for the time dimension only (items from `ANCHOR_LABELS`; writes `comparison.anchor` and rebuilds; header text `f"aligned on event {ANCHOR_LABELS[anchor]}"`, since the x axis stays the base's absolute time), title `f"Compare: {len(sides)} {dimension.noun}"`, and a "⋯" `QToolButton` menu with **Edit comparison…** (emits `edit_requested`, a Signal; Task 8 connects the dialog so this task does not import it) and **Save as template…** (name via `QInputDialog` like `TimeSyncPanel._quick_save_template`; path `templates_dir() / f"{name}.json"`; `PanelTemplate.from_panel(self).to_file(path)` then `save_preview(self, path)` so the Templates UI shows a thumbnail).
  - `ComparisonPanel.comparison -> Comparison` (current, with `view` and `view_options` updated); `set_view(view_id: str)`; `set_comparison(c: Comparison)`.
  - Rebuild on view switch / option change: `view.build(comparison, sides, options_for(comparison, view), old_inner.time_range if old_inner else None, self)`, swap it into the layout, `deleteLater()` the old one. Build errors (a `ValueError` from a dimension, e.g. no base time range) show a `QLabel` with the message instead of the inner widget.
  - `_create(name, config)` → `ComparisonPanel(name, Comparison.model_validate(config))`; `_to_config(widget)` → `widget.comparison.model_dump(mode="json")`.
  - A dimension or view id that is not registered on reopen: a `QLabel` naming the missing id instead of the inner panel; `to_config` still returns the stored model unchanged.

- [ ] **Step 1: Write the failing tests** (each test removes the panels it opened: `main_window.remove_panel` + `qtbot.waitUntil`, as `tests/test_panel_kinds.py` `demo_kinds`)

```python
def test_open_and_round_trip(main_window, qtbot):
    c = _time_comparison_of_vp(variants=1)
    w = main_window.open_panel(COMPARISON_PANEL, **c.model_dump(mode="json"))
    assert Comparison.model_validate(panel_tree(w)["config"]) == c

def test_view_switch_keeps_time_range(main_window, qtbot): ...
def test_disabled_tab_for_inapplicable_view(main_window, qtbot): ...   # 3 sides -> Difference tab disabled, tooltip set
def test_reopen_with_missing_product_keeps_other_ghosts_in_place(main_window, qtbot, caplog):
    # base: plot 0 holds only "nope//missing", plot 1 holds the VP; time comparison with 1 variant
    # -> panel opens, a warning is logged, and the VP's ghost sits on the same plot as the VP's base graph
def test_source_panel_closed_after_creation(main_window, qtbot): ...  # snapshot a live panel, remove_panel(source), comparison still draws
def test_template_round_trip(main_window, tmp_path, qtbot):
    # PanelTemplate.from_panel(w).to_file(tmp_path / "c.json"); PanelTemplate.from_file(...).create_panel(main_window) -> a ComparisonPanel with equal comparison
def test_unknown_view_shows_message_and_keeps_config(main_window, qtbot): ...
```

- [ ] **Step 2: Run** `uv run pytest --no-xvfb tests/comparison/test_comparison_panel.py -v` — FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** — PASS; then `uv run pytest --no-xvfb tests/test_panel_kinds.py tests/test_panel_kinds_ui.py tests/test_plugin_interop.py -q` — PASS (the new core kind is not in the New menu; EP listing tests still green).
- [ ] **Step 5: Commit** `feat(comparison): comparison panel kind`.

---

### Task 8: Wizard, pickers, entry points

**Files:**
- Create: `ui/pickers.py`, `ui/wizard.py`, `ui/commands.py`
- Modify: `SciQLop/core/menus.py` — add `CATALOG_EVENTS = "catalog.events"`.
- Modify: `SciQLop/components/command_palette/arg_types.py` — add `EventsArg(CommandArg)` with `name = "events"`; `completions(context)` resolves `resolve_catalog_arg(context["catalog"])` and lists `provider.events(catalog)` (value `event.uuid`, display the start time); no `"catalog"` in context → `[]`.
- Modify: `SciQLop/components/catalogs/ui/catalog_browser.py` — `_build_event_context_menu` ends with `add_menu_entries(menu, CATALOG_EVENTS, self._event_menu_context())`; context = `{"provider": name, "catalog": catalog_arg_value(name, uuid), "events": ",".join(selected uuids)}` (selection walk as in `_on_delete`; no `"events"` key when nothing is selected).
- Modify: `SciQLop/components/catalogs/backend/panel_manager.py` — `panels_showing(main_window, provider_name: str, catalog_uuid: str) -> list` (time panels whose `catalog_manager` shows that catalog).
- Modify: `SciQLop/components/command_palette/commands.py` — call `register_comparison_commands(registry)` next to `register_proxy_share`.
- Test: `tests/comparison/test_wizard.py`

**Interfaces:**
- Produces:
  - `pickers.py`: `PICKERS: dict[str, Callable[[PanelTemplate, QWidget | None], VariantPicker]]` keyed by dimension id (a plugin dimension without an entry gets a `QLabel` "no picker for this kind of comparison — use compare() from Python"). `VariantPicker(QWidget)` has `variants() -> list[Variant]` and a `changed` Signal.
    - time: catalog combo filled by `for provider in CatalogRegistry.instance().providers(): for catalog in provider.catalogs()` + checkable event list from `provider.events(catalog)`; `Variant(label=event.start.isoformat(timespec="minutes"), params={"start": event.start.timestamp(), "stop": event.stop.timestamp()})`. `simplify:` free intervals not offered yet; add a "custom interval" row when asked.
    - product: target combo (base specs, labelled by plot index and product label) + product line edit accepting a pasted path or a product-tree drop (`SciQLop/core/mime` product MIME); `Variant(label=last path segment, params={"target": [...], "path": ..., "is_colormap": ...})`, `is_colormap` = `plot_kind_for_product(path)` gives a colormap graph type, else the target spec's `is_colormap`; an unresolvable path disables Compare with a tooltip.
    - settings: target combo restricted to specs whose provider has knobs (`provider.get_knobs(node)`), one `delegate_for_spec(spec)` per knob (`components/plotting/ui/knob_inspector/delegates.py:356`), an "Add variant" button snapshotting the values; label = the changed knobs, e.g. `"gain=3"`.
  - `CompareDialog(QDialog)(main_window, base_panel: str | None = None, comparison: Comparison | None = None, preset: tuple[str, list[Variant]] | None = None)`: base combo (open time panels), dimension radio list (from `COMPARISON_DIMENSIONS`), picker area — one page, all three steps visible (spec §7), not a `QWizard`. **Compare** builds `Comparison(base=PanelTemplate.from_panel(<unwrapped panel>).to_tree(), dimension=..., variants=...)` and opens it with `main_window.open_panel(COMPARISON_PANEL, **c.model_dump(mode="json"))`. Edit mode (`comparison` given) calls `set_comparison` on that panel instead.
  - `open_compare_events(catalog: str, events: str)` — base panel from `panels_showing(...)`: one → use it; several → the dialog's base combo is limited to them; none → base left for the user to pick. Base template's `time_range` is set to the first event; the remaining events are the variants (spec §3.3); the dialog opens pre-filled (`preset=("time", variants)`) so the user only clicks Compare.
  - Commands in `ui/commands.py`: `sciqlop.compare` (`open_compare_dialog(panel: str = "")`, args `[PanelArg()]`), `sciqlop.compare_events` (args `[CatalogArg(), EventsArg()]`). Menu entries: `MAIN_TOOLS` → `sciqlop.compare` labelled "Compare…"; `PANEL` → `sciqlop.compare` labelled "Compare with…"; `CATALOG_EVENTS` → `sciqlop.compare_events` labelled "Compare", `when=lambda ctx: len(ctx.get("events", "").split(",")) >= 2`.
  - `ComparisonPanel.edit_requested` (Task 7) connected to open `CompareDialog` in edit mode (wired in `ui/panel_kind.py`'s `_create`).

- [ ] **Step 1: Write the failing tests**

```python
def test_dialog_builds_time_comparison(main_window, qtbot): ...       # seed a catalog with 3 events, base panel with VP; pick 2 events; Compare -> a ComparisonPanel docked, 2 variants
def test_time_variant_keeps_event_duration(qtbot): ...                # picker on an event of 2 h -> params stop - start == 7200
def test_menu_entries_are_registered(): ...                           # MENUS has the three entries at MAIN_TOOLS, PANEL, CATALOG_EVENTS
def test_compare_events_needs_two_events(): ...                       # when() False for "a", True for "a,b"
def test_events_arg_lists_catalog_events(): ...
def test_catalog_events_menu_offers_compare(main_window, qtbot): ...  # select 2 rows in the browser event table; the event context menu has a "Compare" action
def test_edit_mode_updates_existing_panel(main_window, qtbot): ...
def test_dialog_accepts_user_api_panel(main_window, qtbot): ...       # base given as a user_api PlotPanel wrapper
```

- [ ] **Step 2: Run** `uv run pytest --no-xvfb tests/comparison/test_wizard.py -v` — FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** — PASS; then the catalog browser and command palette tests: `uv run pytest --no-xvfb $(ls tests/test_catalog_browser*.py tests/test_command_palette*.py tests/test_menu*.py 2>/dev/null) -q` — PASS.
- [ ] **Step 5: Commit** `feat(comparison): compare dialog and menu entries`.

---

### Task 9: user_api, agent tool, docs

**Files:**
- Create: `SciQLop/user_api/comparison.py`, `SciQLop/components/agents/tools/comparison_tool.py`
- Modify: `SciQLop/components/comparison/ui/panel_kind.py` — contribute the agent tools to `AGENT_TOOLS` (owner `"sciqlop"`).
- Modify: `CHANGELOG.md` (Unreleased: "Compare panels: overlay or difference of two events, products or settings"), the agent skill reference listing plot tools if tool names are test-checked there (`grep -rn sciqlop_build_panel SciQLop/components/agents/skills`).
- Test: `tests/comparison/test_user_api.py`

**Interfaces:**
- Produces:
  - `compare(panel, *, over: str, variants: list, view: str = "overlay", labels: list[str] | None = None) -> ComparisonHandle` (`@on_main_thread`). `panel` is a `user_api` `PlotPanel` or panel name. `variants` coercion per dimension: `time` — speasy `Event`, `CatalogEvent`, `TimeRange`, or `(start, stop)` (datetimes or epoch floats); `product` — product path strings or `VirtualProduct` (target = first base graph unless `target=(plot_index, product_index)` is passed); `settings` — knob dicts (same target rule). Unknown `over` → `ValueError` listing registered dimension ids.
  - `ComparisonHandle`: `view` property (get/set; setting an inapplicable view raises `ValueError` with the reason), `variants -> list[str]` (labels), `options(view: str | None = None) -> dict` and `set_options(view: str, **values)`, `panel -> QWidget`-backed name `name -> str`. All Qt-touching members `@on_main_thread`.
  - Agent tools: `sciqlop_compare` (input: `panel`, `over`, `variants` as JSON — time ranges as ISO pairs, product paths, knob dicts — `view`) and `sciqlop_set_comparison_view` (`name`, `view`, optional `options`). Return a short text: panel name, sides, views available with reasons.

- [ ] **Step 1: Write the failing tests**

```python
def test_compare_over_time_from_tuples(plot_panel_with_vp, qtbot):
    h = compare(plot_panel_with_vp, over="time", variants=[(t0 + 86400, t1 + 86400)])
    assert h.view == "overlay" and len(h.variants) == 1
    h.view = "difference"
    assert h.view == "difference"

def test_compare_rejects_unknown_dimension(plot_panel_with_vp):
    with pytest.raises(ValueError, match="time"): compare(plot_panel_with_vp, over="nope", variants=[])

def test_inapplicable_view_raises_with_reason(...): ...  # 2 variants -> h.view = "difference" raises "exactly two sides"
def test_agent_tool_creates_comparison(main_window, qtbot): ...  # AGENT_TOOLS.get("sciqlop_compare").call({...}) -> text naming the new panel
```

- [ ] **Step 2: Run** `uv run pytest --no-xvfb tests/comparison/test_user_api.py -v` — FAIL.
- [ ] **Step 3: Implement.** Re-export `compare` from `SciQLop/user_api/__init__.py` only if other top-level helpers are re-exported there; otherwise users import `from SciQLop.user_api.comparison import compare`.
- [ ] **Step 4: Run** — PASS. Then the whole suite once: `uv run pytest --no-xvfb` — read the real pass/fail count and exit code. Run CI's blocking flake8: `uv run flake8 --select=E9,F63,F7,F82 $(git ls-files '*.py')` — no output.
- [ ] **Step 5: Commit** `feat(comparison): user_api compare() and agent tools` (pathspecs incl. CHANGELOG). Update the global `~/.claude/memory/sciqlop-user-api.md` with `compare()` and `PlotPanel.plot_product(time_offset=)`.
