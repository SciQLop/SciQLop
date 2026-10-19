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
- Extension point ids: `sciqlop.comparison_dimensions`, `sciqlop.comparison_views`. Panel kind id: `sciqlop.comparison`. Core view ids: `overlay`, `difference`. Core dimension ids: `time`, `product`, `settings`.

## Review Focus

1. A variant whose time window has no data (event outside product coverage) → the ghost is empty, nothing raises, the base still draws. Test in Task 5.
2. A base panel holding a static/function graph (empty product path) → that graph is carried unchanged and never compared; the comparison still builds. Test in Task 2.
3. Reopening a saved comparison whose product is no longer in the products tree → the panel opens, the missing graph is skipped with a log warning, no crash. Test in Task 7.
4. Difference where B covers only part of A's time span → NaN outside B's span, no extrapolation. Test in Task 4.
5. The source panel is closed after the comparison was created → the comparison is unaffected (snapshot). Test in Task 7.

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
  ui/
    __init__.py
    styling.py        # ghost styling
    overlay_view.py   # build_overlay()
    difference_view.py# build_difference()
    panel.py          # ComparisonPanel widget
    panel_kind.py     # PanelKind contribution + view/dimension core contributions
    pickers.py        # step-3 picker widgets, one per core dimension
    wizard.py         # CompareDialog
    commands.py       # palette commands + menu entries
SciQLop/user_api/comparison.py
SciQLop/components/agents/tools/comparison_tool.py
```

Modified: `components/plotting/ui/time_sync_panel.py` (time_offset), `components/plotting/panel_template.py` (`apply` returns plots), `user_api/plot/_panel.py` + `_plots.py` (time_offset keyword), `core/menus.py` (new location), `components/catalogs/ui/catalog_browser.py` (event-menu hook), `components/extension_points.py` (registration), `CHANGELOG.md`.

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
```

- [ ] **Step 2: Run** `uv run pytest --no-xvfb tests/test_time_offset_products.py -v` — expected FAIL (`shift_buffers` not defined / unexpected keyword `time_offset`).
- [ ] **Step 3: Implement** `shift_buffers`, the callback offset, the `time_offset` pop in `_plot_product` (passed to both `_plot_product_callback` and `_specgram_callback`), the remote refusal, and the `user_api` keyword with a docstring line ("Seconds; data is fetched `time_offset` later and drawn at the panel's time, e.g. 27 days to overlay the next solar rotation.").
- [ ] **Step 4: Run** the same command — expected PASS. Then run `uv run pytest --no-xvfb tests/test_plot_panel_plot_args.py tests/test_panel_tree.py -q` — expected all pass.
- [ ] **Step 5: Commit** `feat(plotting): plot a product shifted in time` (pathspecs: the three source files + the test).

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
  - `Side(label: str, specs: list[GraphSpec])`
  - `Comparison(base: dict, dimension: str, variants: list[Variant], view: str = "overlay", dimension_options: dict = {}, view_options: dict[str, dict] = {})` — `base` is `PanelTemplate.to_tree()` output; `template() -> PanelTemplate` rebuilds it via `PanelTemplate.from_tree`.
  - `base_specs(template: PanelTemplate) -> list[GraphSpec]` — one spec per product with a non-empty `path`, in plot then product order; skips non-timeseries plots.
  - `sides(comparison, apply) -> list[Side]` where `apply(specs, variant, comparison) -> list[GraphSpec]` (the dimension's function, passed in so the model has no EP dependency); side 0 is the base, labelled with the template's name.
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
  - `@dataclass(frozen=True) ComparisonDimension(id: str, label: str, apply: Callable[[list[GraphSpec], Variant, Comparison], list[GraphSpec]], validate: Callable[[dict], None], picker: Callable[..., QWidget] | None = None)`
  - `COMPARISON_DIMENSIONS = declare(ExtensionPoint("sciqlop.comparison_dimensions", ComparisonDimension, ...))`
  - `ANCHORS = ("start", "center", "end")`; `anchor_time(start: float, stop: float, anchor: str) -> float`.
  - Core functions (contributed in Task 7): `apply_time` — `params = {"start": float, "stop": float}` epoch s; offset = `anchor_time(variant) - anchor_time(base time_range)`, anchor from `comparison.dimension_options.get("anchor", "start")`, applied to every spec. `apply_product` — `params = {"target": [plot_index, product_index], "path": str}`, replaces `path` of that spec only (also sets `is_colormap` from `params.get("is_colormap", spec.is_colormap)`). `apply_settings` — `params = {"target": [...], "knobs": dict}`, merges knobs into that spec only. Each `validate_*` raises `ValueError` naming the missing/bad key.
  - `dimension(id) -> ComparisonDimension` and `resolve_sides(comparison) -> list[Side]` (= `sides(comparison, dimension(comparison.dimension).apply)`).
- Produces in `views.py`:
  - `@dataclass(frozen=True) ComparisonView(id: str, label: str, applies: Callable[[Comparison, list[Side]], str | None], build: Callable[[Comparison, list[Side], dict], QWidget], default_options: dict = field(default_factory=dict), order: int = 0)` — `applies` returns `None` when usable, else the reason shown as tooltip.
  - `COMPARISON_VIEWS = declare(ExtensionPoint("sciqlop.comparison_views", ComparisonView, ...))`
  - `available_views(comparison, sides) -> list[tuple[ComparisonView, str | None]]` sorted by `(order, id)`.
  - `options_for(comparison, view) -> dict` = `{**view.default_options, **comparison.view_options.get(view.id, {})}`.

- [ ] **Step 1: Write the failing tests**

```python
def test_time_dimension_shifts_every_graph_by_anchor_difference():
    c = _comparison(time_range=(100.0, 200.0), variants=[Variant(label="e", params={"start": 1100.0, "stop": 1300.0})])
    specs = apply_time(base_specs(c.template()), c.variants[0], c)
    assert {s.time_offset for s in specs} == {1000.0}
    c2 = c.model_copy(update={"dimension_options": {"anchor": "end"}})
    assert {s.time_offset for s in apply_time(base_specs(c2.template()), c2.variants[0], c2)} == {1100.0}

def test_product_dimension_changes_only_target():
    ...  # two specs; target [0, 1] -> only that path changes

def test_settings_dimension_merges_knobs():
    ...  # base knobs {"a": 1, "b": 2}, params knobs {"b": 3} -> {"a": 1, "b": 3}

def test_validate_rejects_missing_keys():
    with pytest.raises(ValueError, match="start"): validate_time({"stop": 1.0})

def test_available_views_reports_reason():
    # contribute a view whose applies returns "needs two sides" under owned_by("cmp_test"); assert it is listed with that reason; remove_owner after
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
  - `OPERATIONS = ("difference", "ratio", "log_ratio")`; `relate(a: np.ndarray, b: np.ndarray, op: str) -> np.ndarray` — `a - b`, `a / b`, `log10(a / b)`; non-positive inputs to `log_ratio` give NaN, never a warning-spam (`np.errstate`).
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

### Task 5: Overlay view

**Files:**
- Modify: `SciQLop/components/plotting/panel_template.py` — `PanelTemplate.apply(panel) -> list` returns the per-`PlotModel` results of `_restore_plot` (index-aligned with `self.plots`; `None` where nothing was restored). Existing callers ignore the return value.
- Create: `ui/__init__.py`, `ui/styling.py`, `ui/overlay_view.py`
- Test: `tests/comparison/test_overlay_view.py`

**Interfaces:**
- Consumes: `resolve_sides`, `changed_keys`, `GraphSpec`, `plot_product(target, path_list, time_offset=..., product_inputs=...)` (Task 1), `resolve_product_path` from `panel_template.py`.
- Produces:
  - `build_inner_panel(comparison) -> tuple[TimeSyncPanel, list]` in `overlay_view.py` — new `TimeSyncPanel(parent=None, name=..., time_range=...)` with `setAcceptDrops(False)`, base template applied; returns the panel and the restored-plots list. Reused by the Difference view.
  - `add_ghost(plot, spec: GraphSpec, base_graph, label: str, index: int)` — plots `spec` on `plot` via `plot_product(plot, resolve_product_path(spec.path), time_offset=spec.time_offset, product_inputs=spec.knobs or None)`, names it `f"{base_name} — {label}"`, styles it with `styling.ghost_style(graph, base_graph, index)`. When `plot_product` returns `None` (remote product with an offset, or product missing), show an Info message on that plot's overlay: `f"{label}: {spec.path} could not be plotted"` and continue.
  - `styling.ghost_style(graph, base_graph, index: int)` — per component: base component colour `.lighter(130 + 20 * index)`, dash line style (`GraphLineStyle.Dash` via the `user_api` `Line` wrapper or the same component setters it uses). Components may only exist after the first fetch for some products: if `graph.components()` is empty, re-apply once on the graph's first data (connect with the graph as receiver context).
  - `build_overlay(comparison, sides, options) -> QWidget` — inner panel + one ghost per (variant side, changed key) on non-colormap specs; for changed colormap specs, show an Info-level message on that plot's overlay (same overlay API `_PlotErrorReporter` uses): `"spectrogram variants are not shown in Overlay — use Difference"`. Above 6 variants, an Info message on the first plot: `"many variants — an Epoch view will summarise them better"`.
  - `applies_overlay(comparison, sides) -> str | None` — `None` if any changed key exists, else `"nothing differs between the sides"`.

- [ ] **Step 1: Write the failing tests** (VP-based, like `tests/test_plot_panel_plot_args.py:62`)

```python
def test_overlay_adds_one_ghost_per_variant(main_window, qtbot):
    comparison = _time_comparison_of_vp(variants=2)        # helper: VP "test_cmp/vp", base panel snapshot, two time variants
    panel = build_overlay(comparison, resolve_sides(comparison), {})
    plot = panel.plots()[0]
    qtbot.waitUntil(lambda: len(plot_graphs(plot)) == 3)
    assert [g.name() for g in plot_graphs(plot)][1].endswith("— " + comparison.variants[0].label)

def test_overlay_ghost_with_no_data_stays_empty_without_error(main_window, qtbot):
    # VP callback returns empty arrays when start > some threshold; variant lies beyond it
    # assert the ghost exists, base graph got data, and the ghost callback's last_error is None
```

- [ ] **Step 2: Run** `uv run pytest --no-xvfb tests/comparison/test_overlay_view.py -v` — FAIL.
- [ ] **Step 3: Implement.** `plot_graphs` is in `SciQLop/components/plotting/panel_introspection.py`.
- [ ] **Step 4: Run** — PASS; then `uv run pytest --no-xvfb tests/test_panel_tree.py tests/test_panel_kinds.py -q` — PASS (the `apply` return change).
- [ ] **Step 5: Commit** `feat(comparison): overlay view`.

---

### Task 6: Difference view

**Files:**
- Create: `ui/difference_view.py`
- Test: `tests/comparison/test_difference_view.py`

**Interfaces:**
- Consumes: `build_inner_panel`, `add_ghost` (Task 5); `line_relation`, `colormap_relation`, `ComparisonMismatch` (Task 4); `plot_function(p, f, **kwargs)` in `time_sync_panel.py`.
- Produces:
  - `applies_difference(comparison, sides) -> str | None` — `"Difference needs exactly two sides"` unless `len(sides) == 2`; `"nothing differs between the sides"` without changed keys.
  - `relation_callback(spec_a: GraphSpec, spec_b: GraphSpec, op: str, method: str) -> Callable[[float, float], list]` — resolves each spec's node/provider (`ProductsModel.node`, `providers.get(node.provider())`) and fetches through `provider._get_data(node, start + off, stop + off, knobs=...)` then `shift_buffers`, then `line_relation`/`colormap_relation`. A `ComparisonMismatch` propagates, so `plot_function`'s error overlay shows it.
  - `build_difference(comparison, sides, options) -> QWidget` — inner panel; for each base plot with ≥1 changed key: ghost for the variant on that plot (colormaps excluded as in Overlay), then a new plot appended right after it holding one relation graph per changed key. Plot order: walk base plots in order, inserting relation plots (use `plot_index=` targeting / panel insert API; the builder picks the SciQLopPlots call after checking `type(TimeSyncPanel.<attr>)`). Relation graph name `f"{name}: {symbol}"` with symbol `A − B`, `A / B`, `log₁₀(A / B)`.
  - Units (spec §6.3): before plotting a relation, compare the y (or z, for colormaps) unit of both specs' `provider.plot_hints(node)` (check the `PlotHints` field names first); when both are known and differ, the relation callback raises `ComparisonMismatch(f"different units: {a} vs {b}")`. Test: two VPs with different unit hints → the relation graph's error overlay names both units.
  - `default_options = {"operation": "difference", "method": "linear"}`; colormap relations default to `"log_ratio"` when `operation` is left at its default. Colormap relation plot uses a diverging gradient centred on 0 (symmetric z range from the data's max |z|).

- [ ] **Step 1: Write the failing tests**

```python
def test_difference_adds_a_relation_row_after_each_changed_plot(main_window, qtbot):
    comparison = _settings_comparison_of_vp(base_knobs={"gain": 1.0}, variant_knobs={"gain": 3.0})  # VP returns gain * ones
    panel = build_difference(comparison, resolve_sides(comparison), {"operation": "difference", "method": "linear"})
    qtbot.waitUntil(lambda: len(panel.plots()) == 2)
    rel = plot_graphs(panel.plots()[1])[0]
    qtbot.waitUntil(lambda: _y_values(rel).size > 0)       # helper reading graph data via the user_api wrapper
    assert np.allclose(_y_values(rel), -2.0)

def test_difference_not_applicable_with_three_sides():
    assert applies_difference(c3, resolve_sides(c3)) == "Difference needs exactly two sides"
```

- [ ] **Step 2: Run** `uv run pytest --no-xvfb tests/comparison/test_difference_view.py -v` — FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** — PASS.
- [ ] **Step 5: Commit** `feat(comparison): difference view`.

---

### Task 7: Comparison panel, panel kind, persistence

**Files:**
- Create: `ui/panel.py`, `ui/panel_kind.py`
- Modify: `SciQLop/components/extension_points.py` — import `SciQLop.components.comparison.ui.panel_kind` after the time panel kind line (declares both EPs, contributes core dimensions, views, panel kind).
- Test: `tests/comparison/test_comparison_panel.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `COMPARISON_PANEL = "sciqlop.comparison"`; `PanelKind(COMPARISON_PANEL, "Comparison", create=_create, to_config=_to_config, icon=<existing icon name>, in_new_menu=False)`, owner `"sciqlop"`.
  - `ComparisonPanel(QWidget)(name: str, comparison: Comparison)`: header = `QTabBar` (one tab per `available_views`, disabled + tooltip when a reason is returned), alignment combo (time dimension only; writes `dimension_options["anchor"]` and rebuilds), "⋯" `QToolButton` menu with **Edit comparison…** (opens `CompareDialog` pre-filled, Task 8 — wire through a `edit_requested` Signal so this task does not import the wizard) and **Save as template…** (`PanelTemplate.from_panel(self).to_file(templates_dir() / f"{name}.json")`, name via `QInputDialog` like `TimeSyncPanel._quick_save_template`).
  - `ComparisonPanel.comparison -> Comparison` (current, with `view` and `view_options` updated); `set_view(view_id: str)`; `set_comparison(c: Comparison)`.
  - Rebuild on view switch / option change: build the new inner widget, carry `time_axis_range()` of the old inner panel to the new one, swap it in the layout, `deleteLater()` the old one. The header title is `f"Compare: {len(sides)} {noun}"` (`events`/`products`/`settings`); for the time dimension it also shows `f"aligned on event {anchor}"` (spec §5: the x axis stays the base's absolute time).
  - `_create(name, config)` → `ComparisonPanel(name, Comparison.model_validate(config))`; `_to_config(widget)` → `widget.comparison.model_dump(mode="json")`.
  - A dimension or view id that is not registered on reopen: show a `QLabel` explaining which plugin id is missing instead of the inner panel; `to_config` still returns the stored model unchanged.

- [ ] **Step 1: Write the failing tests**

```python
def test_open_and_round_trip(main_window, qtbot):
    c = _time_comparison_of_vp(variants=1)
    w = main_window.open_panel(COMPARISON_PANEL, **c.model_dump(mode="json"))
    assert Comparison.model_validate(panel_tree(w)["config"]) == c

def test_view_switch_keeps_time_range(main_window, qtbot): ...
def test_disabled_tab_for_inapplicable_view(main_window, qtbot): ...   # 3 sides -> Difference tab disabled, tooltip set
def test_reopen_with_missing_product_skips_it(main_window, qtbot, caplog): ...   # path "nope//missing" in base; panel opens
def test_source_panel_closed_after_creation(main_window, qtbot): ...  # build from a live panel snapshot, remove_panel(source), comparison still draws
def test_template_round_trip(main_window, tmp_path, qtbot):
    # PanelTemplate.from_panel(w).to_file(tmp_path / "c.json"); PanelTemplate.from_file(...).create_panel(main_window) -> a ComparisonPanel with equal comparison
```

- [ ] **Step 2: Run** `uv run pytest --no-xvfb tests/comparison/test_comparison_panel.py -v` — FAIL.
- [ ] **Step 3: Implement.** Close-time cleanup: panels with fixtures are removed with `main_window.remove_panel` and `qtbot.waitUntil`, like `tests/test_panel_kinds.py` `demo_kinds`.
- [ ] **Step 4: Run** — PASS; then `uv run pytest --no-xvfb tests/test_panel_kinds.py tests/test_panel_kinds_ui.py tests/test_plugin_interop.py -q` — PASS (new core kind not shown in the New menu, EP list tests still green).
- [ ] **Step 5: Commit** `feat(comparison): comparison panel kind`.

---

### Task 8: Wizard, pickers, entry points

**Files:**
- Create: `ui/pickers.py`, `ui/wizard.py`, `ui/commands.py`
- Modify: `SciQLop/core/menus.py` — add `CATALOG_EVENTS = "catalog.events"`.
- Modify: `SciQLop/components/catalogs/ui/catalog_browser.py` — `_build_event_context_menu` calls `add_menu_entries(menu, CATALOG_EVENTS, self._event_menu_context())`; context = `{"provider": name, "catalog": catalog_arg_value(...), "events": ",".join(selected uuids)}` (no `"events"` key when nothing is selected).
- Modify: `SciQLop/components/command_palette/commands.py` — call `register_comparison_commands(registry)` next to `register_proxy_share`.
- Modify: `ui/panel_kind.py` — set `picker=` on the three core dimensions.
- Test: `tests/comparison/test_wizard.py`

**Interfaces:**
- Produces:
  - Picker contract: `picker(base: PanelTemplate, parent=None) -> VariantPicker`, where `VariantPicker(QWidget)` has `variants() -> list[Variant]` and `changed` Signal.
    - time: catalog combo (`CatalogRegistry.instance().providers()`/`catalogs()`/`events()`) + checkable event list; `Variant(label=start.isoformat(timespec="minutes"), params={"start": ts, "stop": ts})`. `simplify:` free intervals not offered yet; add a "custom interval" row when asked.
    - product: target combo (base specs, labelled by plot index and product label) + product line edit accepting a pasted path or a product-tree drop (`SciQLop/core/mime` product MIME); `Variant(label=last path segment, params={"target": [...], "path": ..., "is_colormap": ...})` (`is_colormap` from `product_kind_of(node).arity == 3`).
    - settings: target combo restricted to specs whose provider has knobs (`provider.get_knobs(node)`), one `delegate_for_spec(spec)` per knob (`components/plotting/ui/knob_inspector/delegates.py:356`), "Add variant" button snapshotting the values; label = changed knobs `"gain=3"`.
  - `CompareDialog(QDialog)(main_window, base_panel: str | None = None, comparison: Comparison | None = None)`: base combo (open time panels), dimension radio list (from `COMPARISON_DIMENSIONS`), picker area; **Compare** builds `Comparison(base=PanelTemplate.from_panel(panel).to_tree(), dimension=..., variants=...)` and opens it with `main_window.open_panel(COMPARISON_PANEL, **c.model_dump(mode="json"))`. Edit mode (`comparison` given) updates that panel via `set_comparison` instead.
  - `open_compare_events(catalog: str, events: str)` — base panel = the time panel showing that catalog (`catalogs.backend.panel_manager`); several → dialog asks; none → dialog with base empty. Base template's `time_range` set to the first event; remaining events are variants (spec §3.3). Uses the same dialog, pre-filled, so the user only clicks Compare.
  - Commands: `sciqlop.compare` (`open_compare_dialog(panel: str = "")`, args `[PanelArg()]`), `sciqlop.compare_events` (args `[CatalogArg(), EventsArg()]`, `EventsArg.completions` lists the context catalog's events). Menu entries: `MAIN_TOOLS` → `sciqlop.compare` labelled "Compare…"; `PANEL` → `sciqlop.compare` labelled "Compare with…"; `CATALOG_EVENTS` → `sciqlop.compare_events` labelled "Compare", `when=lambda ctx: len(ctx.get("events", "").split(",")) >= 2`.
  - `ComparisonPanel.edit_requested` (Task 7) connected to open `CompareDialog` in edit mode.

- [ ] **Step 1: Write the failing tests**

```python
def test_dialog_builds_time_comparison(main_window, qtbot): ...       # seed a catalog with 3 events, base panel with VP; pick 2 events; Compare -> a ComparisonPanel docked, 2 variants
def test_menu_entries_are_registered(): ...                            # MENUS has the three entries at MAIN_TOOLS, PANEL, CATALOG_EVENTS
def test_compare_events_needs_two_events(): ...                        # when() False for "a", True for "a,b"
def test_catalog_events_menu_offers_compare(main_window, qtbot): ...   # select 2 rows in the browser event table, _build_event_context_menu(None) has a "Compare" action
def test_edit_mode_updates_existing_panel(main_window, qtbot): ...
```

- [ ] **Step 2: Run** `uv run pytest --no-xvfb tests/comparison/test_wizard.py -v` — FAIL.
- [ ] **Step 3: Implement.** The dialog is one page with all three steps visible (spec §7), not a `QWizard`.
- [ ] **Step 4: Run** — PASS; then `uv run pytest --no-xvfb tests/test_catalog_browser*.py tests/test_menus*.py -q` (whichever exist) — PASS.
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
