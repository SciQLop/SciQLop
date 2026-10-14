# Plot kinds, drop rules and the panel tree (plan 1c) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Plugins add plot kinds and drop rules. Panels are saved as a `{kind, config, slots}` tree that restores plugin plots, and it keeps a placeholder when a plugin is missing.

**Architecture:** This plan adds two extension points on plan 1a's `ExtensionPoint`:
- `sciqlop.plot_kinds` says how to plot a product, how to recognize a plot, and how to save and restore one.
- `sciqlop.drop_rules` says what dropping a payload of one MIME type on a plot does, chosen by the dragged product's kind and the target plot's kind.

`time_sync_panel.plot_product` and the scenes drop table become clients of these two points. Panel templates move to file format v3, a tree. The in-memory `PanelTemplate` keeps its published shape: each `PlotModel` gains `kind` and `config`. A plot whose kind is not registered restores as a placeholder that keeps its node, so saving again loses nothing.

**Tech Stack:** Python 3.10+, PySide6, SciQLopPlots (`PlotDragNDropCallback`, `ProductsModel`, overlays), pydantic v2, PyYAML, pytest + pytest-qt (+ pytest-xvfb).

**Spec:** `docs/superpowers/specs/2026-10-14-plugin-extension-points-design.md`. The sections that matter here:
- §4.3: the tier-1 rows for `sciqlop.plot_kinds` and `sciqlop.drop_rules`;
- §5: panels as trees;
- §7: migration rules;
- §8: an unknown kind on restore becomes a placeholder;
- §10: the interop proof and the round trip.

Plans 1a and 1b are already on main:
- 1a: `docs/superpowers/plans/2026-10-14-plugin-contract-and-extension-points.md`;
- 1b: `docs/superpowers/plans/2026-10-14-plugin-data-contracts.md`.

## Global Constraints

- Work and commit on `main`, with explicit pathspecs. Never push. Never stage these untracked files: `importlib.metadata`, `setWidget`, `pydata/`, `.claude/`, the untracked `docs/` drafts, `tests/noop_script.py`.
- Run one pytest invocation at a time, in the foreground: `uv run --no-sync pytest <files> -q -p no:cacheprovider`, with Bash `timeout: 600000`. Never `--no-xvfb`. Never `uv sync`. Never rebuild or edit SciQLopPlots or speasy.
- Write files with the Write/Edit tools. Never use shell heredocs, `cat` or `ls`.
- Ids follow `sciqlop.<name>` / `sciqlop.<component>.<name>` for core, and `<plugin id>.<name>` for plugins. The new core ids are:
  - `sciqlop.timeseries` and `sciqlop.scenes.projection` (plot kinds);
  - `sciqlop.time_panel` (the panel tree's root kind);
  - `sciqlop.plot_product`, `sciqlop.time_range`, `sciqlop.catalogs.overlay`, `sciqlop.scenes.plot_scene`, `sciqlop.scenes.set_boundary`, `sciqlop.scenes.refuse_boundary`, `sciqlop.scenes.add_trajectory` and `sciqlop.layers.attach` (drop rules).
- Core contributions are owned by `"sciqlop"`. Pass it explicitly at import. Extension points are main-thread objects.
- `user_api` is published, so no existing signature changes. The new `PlotPanel.add(kind, **config)` is additive. `PanelTemplate`, `PlotModel` and `ProductModel` keep every existing field, so the agents' `build_panel` tool and `user_api.templates` keep working.
- Template files: v1 and v2 still load. `TEMPLATE_VERSION` becomes 3, and the user's templates directory rewrites older files as v3 when it lists them, as it already does for v1→v2 (spec §5).
- Qt lifetimes: never connect an app-lifetime signal to a panel's bound method. Follow `docs/qt-lifetime-patterns.md`, and give the connection a receiver context.
- Plugin-author docs move with the code (spec §7). Update `SciQLop/components/agents/skills/sciqlop-plugin-design/` in the same commit. When `user_api` gains a method, also update the global `/home/jeandet/.claude/memory/sciqlop-user-api.md`; that file is outside the repo and not committed.
- Code style (CLAUDE.md): small functions, data over code, no comment-decorated blocks, a `simplify:` comment on deliberate shortcuts.
- Commit trailer: `Co-Authored-By: <the model writing the commit> <noreply@anthropic.com>`.

## Review Focus

1. **A template saved by an older SciQLop (v1 or v2 YAML/JSON)** loads, plots the same products on the same axes, and is rewritten as v3 with the same content. → Task 3: a v2 file round-trips through v3 with an equal model.
2. **A panel holding a scene plot** (Earth GSM with MMS1) is saved as a template and restored with the same scene, boundaries and trajectories. Today scene plots vanish from saved templates without a word. → Task 4.
3. **A template naming a plot kind whose plugin is not installed** restores everything else and shows a placeholder plot that names the plugin. Saving the panel again keeps the unknown node unchanged. → Task 3.
4. **Every drop that works today keeps working:**
   - a speasy product dropped between plots creates a plot;
   - a product dropped on a scene adds a trajectory;
   - a boundary dropped on a time-series plot is refused, with a message;
   - a layer attaches;
   - a time range zooms;
   - a catalog overlays.
   
   → Task 2's rule table test, plus the existing scenes and drop tests.
5. **A plugin that adds a drop rule for a new MIME type after panels are open:** the open panels accept that MIME type with no restart. → Task 2.

---

## File map

| File | Role | Task |
|---|---|---|
| `SciQLop/core/plot_kinds.py` (new) | `PlotKind`, `PLOT_KINDS`, ids, `plot_kind_of(plot)`, `plot_kind_for_product(product)` | 1 |
| `SciQLop/components/plotting/core_kinds.py` (new) | contributes `sciqlop.timeseries` (plot kind) and the core drop rules | 1, 2, 3 |
| `SciQLop/components/scenes/contributions.py` (new) | contributes `sciqlop.scenes.projection` and the scenes drop rules | 1, 2, 4 |
| `SciQLop/components/plotting/ui/time_sync_panel.py` | `plot_product` dispatches on plot kinds; drop callbacks come from drop rules | 1, 2 |
| `SciQLop/core/drop_rules.py` (new) | `DropRule`, `DROP_RULES`, `rule_for(...)` | 2 |
| `SciQLop/components/plotting/drops.py` (new) | `dispatch_drop(panel, plot, mime_type, payload)`, the panel's rule callbacks | 2 |
| `SciQLop/components/scenes/tree.py` | the `_TABLE` dispatch goes; `drop()` delegates to `drops` | 2 |
| `SciQLop/components/plotting/panel_template.py` | `PlotModel.kind/config`, v3 tree read/write, restore via plot kinds | 3 |
| `SciQLop/components/plotting/placeholder.py` (new) | placeholder plot for an unknown kind, which keeps its node | 3 |
| `SciQLop/components/plotting/panel_introspection.py` | `ordered_panel_plots(panel)`: every plot, any type, in panel order | 3 |
| `SciQLop/user_api/scenes/__init__.py` | `ScenePlot` remembers its trajectories | 4 |
| `SciQLop/user_api/plot/_panel.py` | `PlotPanel.add(kind, **config)` | 5 |
| `SciQLop/components/extension_points.py` | imports the new declaring and contributing modules | 1, 2 |
| `tests/test_plugin_panel_interop.py` (new), skill references, spec, global memory | interop proof and docs | 6 |

---

### Task 1: `sciqlop.plot_kinds`, and `plot_product` dispatches through it

**Files:**
- Create: `SciQLop/core/plot_kinds.py`
- Create: `SciQLop/components/plotting/core_kinds.py`
- Create: `SciQLop/components/scenes/contributions.py`
- Modify: `SciQLop/components/plotting/ui/time_sync_panel.py` (`plot_product`, `_plot_scene_item`)
- Modify: `SciQLop/components/extension_points.py`
- Test: `tests/test_plot_kinds.py` (new)

**Interfaces:**
- Consumes (plan 1b):
  - `SciQLop.core.product_kinds.product_kind_of(node)`, `ProductKind.default_plot_kind`, `PRODUCT_KIND_KEY`, `SCENE`, `BOUNDARY`;
  - `ExtensionPoint`, `declare`, `key in ep`.
- Produces:
  - `SciQLop.core.plot_kinds.PlotKind(id, label, plot_product, owns=<never>, to_config=None, from_config=None)`, a frozen dataclass. Its callables:
    - `plot_product(target, product: list[str], kwargs: dict)` returns what `time_sync_panel.plot_product` returns: a `(plot, graph)` pair, a bare graph, or None.
    - `owns(plot) -> bool`.
    - `to_config(plot) -> dict`.
    - `from_config(panel, config: dict)` returns the user-facing plot object (a user_api wrapper) or None.
  - `PLOT_KINDS: ExtensionPoint`, keyed by `id`.
  - The constants `TIMESERIES = "sciqlop.timeseries"`, `PROJECTION = "sciqlop.scenes.projection"` and `TIME_PANEL = "sciqlop.time_panel"`.
  - `plot_kind_of(plot) -> PlotKind | None`: the first non-time-series kind that owns the plot, else `sciqlop.timeseries`. None when `plot` is None.
  - `plot_kind_for_product(product) -> PlotKind | None`.
  - `plugin_of(kind_id: str) -> str`: the id prefix.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_plot_kinds.py`:

```python
"""Plot kinds (spec §4.3, §5): a product plots through its kind's default plot kind."""
import pytest

from SciQLop.core.extensions import owned_by
from SciQLop.core.plot_kinds import (PLOT_KINDS, PROJECTION, TIMESERIES, PlotKind, plot_kind_for_product,
                                     plot_kind_of, plugin_of)
from SciQLop.core.product_kinds import PRODUCT_KIND_KEY, PRODUCT_KINDS, ProductKind


@pytest.fixture
def plugin_kinds(qapp):
    """A plugin product kind plotted by a plugin plot kind, and one product node of that kind."""
    from SciQLop.core.enums import ParameterType
    from SciQLop.core.models import ProductsModelNodeType, add_product_node
    calls = []
    with owned_by("pk1c"):
        PRODUCT_KINDS.contribute(ProductKind("pk1c.distribution", "VDF", 3, "pk1c.slice_plot"))
        PRODUCT_KINDS.contribute(ProductKind("pk1c.orphan", "Orphan", 3, "pk1c.gone_plot"))
        PLOT_KINDS.contribute(PlotKind("pk1c.slice_plot", "Slice",
                                       plot_product=lambda target, product, kw: calls.append((target, product, kw))
                                       or ("plot", "graph")))
    add_product_node(["pk1c"], "dist", "pk1c", {PRODUCT_KIND_KEY: "pk1c.distribution"},
                     ProductsModelNodeType.PARAMETER, ParameterType.Scalar)
    add_product_node(["pk1c"], "orphan", "pk1c", {PRODUCT_KIND_KEY: "pk1c.orphan"},
                     ProductsModelNodeType.PARAMETER, ParameterType.Scalar)
    yield calls
    PLOT_KINDS.remove_owner("pk1c")
    PRODUCT_KINDS.remove_owner("pk1c")


def test_core_plot_kinds_are_owned_by_sciqlop(qapp):
    for kid in (TIMESERIES, PROJECTION):
        assert PLOT_KINDS.owner_of(kid) == "sciqlop"


def test_a_product_plots_through_its_kinds_default_plot_kind(plugin_kinds):
    from SciQLop.components.plotting.ui.time_sync_panel import plot_product
    target = object()
    assert plot_kind_for_product(["pk1c", "dist"]).id == "pk1c.slice_plot"
    assert plot_product(target, ["pk1c", "dist"], plot_type="x") == ("plot", "graph")
    assert plugin_kinds == [(target, ["pk1c", "dist"], {"plot_type": "x"})]


def test_a_missing_plot_kind_plots_nothing(plugin_kinds):
    from SciQLop.components.plotting.ui.time_sync_panel import plot_product
    assert plot_kind_for_product(["pk1c", "orphan"]) is None
    assert plot_product(object(), ["pk1c", "orphan"]) is None


def test_unknown_products_have_no_plot_kind(qapp):
    assert plot_kind_for_product(["pk1c_nowhere", "x"]) is None
    assert plot_kind_for_product("not a list") is None


def test_plot_kind_of_defaults_to_time_series(qapp):
    assert plot_kind_of(None) is None
    assert plot_kind_of(object()).id == TIMESERIES


def test_plugin_of_is_the_id_prefix():
    assert plugin_of("vdf.slice_plot") == "vdf"
```

- [ ] **Step 2: Run them and see them fail**

Run: `uv run --no-sync pytest tests/test_plot_kinds.py -q -p no:cacheprovider`
Expected: FAIL with an ImportError on `SciQLop.core.plot_kinds`.

- [ ] **Step 3: Implement**

Create `SciQLop/core/plot_kinds.py`:

```python
"""How products are plotted and how plots are saved: the sciqlop.plot_kinds extension point (spec §4.3, §5)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.extensions import ExtensionPoint, declare

log = getLogger(__name__)

TIMESERIES, PROJECTION, TIME_PANEL = "sciqlop.timeseries", "sciqlop.scenes.projection", "sciqlop.time_panel"


def _never(plot) -> bool:
    return False


@dataclass(frozen=True)
class PlotKind:
    id: str
    label: str
    plot_product: Callable[[Any, list, dict], Any]       # (target panel or plot, product path, kwargs) -> (plot, graph)
    owns: Callable[[Any], bool] = _never                 # is this existing plot one of this kind
    to_config: Optional[Callable[[Any], dict]] = None    # what a template saves; None: not saved
    from_config: Optional[Callable[[Any, dict], Any]] = None  # (panel, config) -> the user-facing plot, or None


PLOT_KINDS = declare(ExtensionPoint("sciqlop.plot_kinds", PlotKind, what="plot kind",
                                    doc="Plots a panel can hold: how products go on them, how they are saved."))


def plugin_of(kind_id: str) -> str:
    return kind_id.split(".", 1)[0]


def plot_kind_of(plot) -> Optional[PlotKind]:
    """The kind that owns *plot*; a plot no plugin claims is a time-series plot."""
    if plot is None:
        return None
    claimed = (k for k in PLOT_KINDS.list() if k.id != TIMESERIES and k.owns(plot))
    return next(claimed, None) or PLOT_KINDS.get(TIMESERIES)


def plot_kind_for_product(product) -> Optional[PlotKind]:
    """The default plot kind of the product's kind; None for unknown products or when that plot kind's plugin
    is not loaded."""
    from SciQLopPlots import ProductsModel
    from SciQLop.core.product_kinds import product_kind_of
    if not isinstance(product, list):
        return None
    node = ProductsModel.node(product)
    kind = product_kind_of(node) if node is not None else None
    if kind is None:
        return None
    if kind.default_plot_kind not in PLOT_KINDS:
        log.warning(f"{'/'.join(product)}: plot kind {kind.default_plot_kind!r} is not available "
                    f"(plugin {plugin_of(kind.default_plot_kind)!r} not loaded)")
        return None
    return PLOT_KINDS.get(kind.default_plot_kind)
```

`SciQLop.components.sciqlop_logging` is fine to import from core: `core/graph_context.py` already does.

Create `SciQLop/components/plotting/core_kinds.py`:

```python
"""Core contributions of the plotting component: the time-series plot kind (and, from Task 2, the core drop rules)."""
from SciQLop.core.plot_kinds import PLOT_KINDS, TIMESERIES, PlotKind


def _plot_timeseries(target, product, kwargs):
    from SciQLop.components.plotting.ui.time_sync_panel import (_owning_time_sync_panel, _plot_product,
                                                                 offer_jump_to_data)
    r = _plot_product(target, product, **kwargs)
    panel = _owning_time_sync_panel(target) if r is not None else None
    if panel is not None:
        offer_jump_to_data(panel, product)
    return r


PLOT_KINDS.contribute(PlotKind(TIMESERIES, "Time series", plot_product=_plot_timeseries), owner="sciqlop")
```

Before writing this, check where `offer_jump_to_data` is defined (grep). If it is not in `time_sync_panel.py`, import it from its real module.

Create `SciQLop/components/scenes/contributions.py`. Move `_plot_scene_item` here from `time_sync_panel.py` unchanged, and adapt its signature:

```python
"""Core contributions of the scenes component: the projection plot kind (and, from Task 2, the scenes drop rules)."""
from SciQLop.core.plot_kinds import PLOT_KINDS, PROJECTION, PlotKind


def _plot_scene_item(target, product, kwargs):
    """Scenes and models have no data provider: they go where a drop would put them."""
    from SciQLop.components.plotting.ui.time_sync_panel import _owning_time_sync_panel, _resolve_plot_target
    from SciQLop.components.scenes.scene_plot import concrete_plot, scene_plot_for
    from SciQLop.components.scenes.tree import drop
    plot = concrete_plot(_resolve_plot_target(target, kwargs)[0])
    panel = _owning_time_sync_panel(plot)
    sp = drop(None if plot is panel else plot, product, panel)
    return None if sp is None else (sp._get_impl_or_raise(), None)


def _owns(plot) -> bool:
    """Any object may be asked (plot_kind_of tries every kind); only a Qt object can be a scene plot."""
    from SciQLop.components.scenes.scene_plot import scene_plot_for
    try:
        return scene_plot_for(plot) is not None
    except (TypeError, AttributeError):
        return False


PLOT_KINDS.contribute(PlotKind(PROJECTION, "Scene", plot_product=_plot_scene_item, owns=_owns), owner="sciqlop")
```

Copy the body from the real `_plot_scene_item` in `time_sync_panel.py`, not from the sketch above. Keep its logic exactly, then delete it from `time_sync_panel.py`. `scene_plot_for` is imported in the sketch but unused; drop it if flake8 flags it.

In `time_sync_panel.py`, replace `plot_product`'s body:

```python
def plot_product(p: Union[SciQLopPlot, SciQLopMultiPlotPanel, SciQLopNDProjectionPlot], product: List[str], **kwargs):
    from SciQLop.core.plot_kinds import plot_kind_for_product
    kind = plot_kind_for_product(product)
    return None if kind is None else kind.plot_product(p, product, kwargs)
```

Remove the `SCENE_KINDS`/`kind_of` import there if nothing else in the function uses it.

In `prepare_extension_points`, import `SciQLop.core.plot_kinds`, `SciQLop.components.plotting.core_kinds` and `SciQLop.components.scenes.contributions` (with `# noqa: F401` and a short "declares/contributes" note, like the existing lines).

Docs: in `references/products-and-data.md`, rewrite the "Product kinds" sentence about how plugin kinds plot. A product plots through its kind's `default_plot_kind`: `sciqlop.timeseries` (series or colour map by arity), `sciqlop.scenes.projection`, or a plugin plot kind. Say that Task 6 adds the plot-kind contract page.

- [ ] **Step 4: Run them and see them pass**

Run: `uv run --no-sync pytest tests/test_plot_kinds.py tests/test_product_kinds.py tests/test_plot_product_inputs.py tests/test_coverage_notice.py tests/scenes tests/test_plotting tests/remote/test_plot_remote.py -q -p no:cacheprovider`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/core/plot_kinds.py SciQLop/components/plotting/core_kinds.py SciQLop/components/scenes/contributions.py SciQLop/components/plotting/ui/time_sync_panel.py SciQLop/components/extension_points.py SciQLop/components/agents/skills/sciqlop-plugin-design/references/products-and-data.md tests/test_plot_kinds.py
git commit -m "feat(plugins): plot kinds are contributions to sciqlop.plot_kinds; plot_product dispatches through them"
```

---

### Task 2: `sciqlop.drop_rules` replaces the scenes drop table and the three panel drop callbacks

**Files:**
- Create: `SciQLop/core/drop_rules.py`
- Create: `SciQLop/components/plotting/drops.py`
- Modify: `SciQLop/components/plotting/core_kinds.py` (core rules)
- Modify: `SciQLop/components/scenes/contributions.py` (scenes rules)
- Modify: `SciQLop/components/scenes/tree.py` (drop `_TABLE` and `drop_handler`; `drop()` delegates)
- Modify: `SciQLop/components/plotting/ui/time_sync_panel.py` (`ProductDnDCallback`, `TimeRangeDnDCallback` and `CatalogDnDCallback` give way to rule callbacks)
- Modify: `SciQLop/components/extension_points.py`
- Test: `tests/test_drop_rules.py` (new); existing `tests/scenes/test_scene_tree.py`, `tests/test_coverage_notice.py`, the DnD tests

**Interfaces:**
- Consumes: `PlotKind`, `plot_kind_of`, `PROJECTION`, `TIMESERIES` (Task 1); `product_kind_of`, `SCENE`, `BOUNDARY`, `LAYER` (plan 1b); `decode_mime`, `MIME_TYPES` (plan 1b); the MIME constants in `SciQLop.core.mime.types`.
- Produces:
  - `SciQLop.core.drop_rules.DropRule(id, mime_type, drop, product_kind=None, target=None, creates_plot=False)`, a frozen dataclass. `drop(plot, payload, panel)`; for product-list drops the payload is one product path.
  - `DROP_RULES: ExtensionPoint`.
  - `rule_for(mime_type, product_kind: str | None, target: str | None) -> DropRule | None`. It returns the most specific matching rule: a matching `product_kind` weighs 2, a matching `target` weighs 1, and ties go to the smallest id.
  - `SciQLop.components.plotting.drops.dispatch_drop(panel, plot, mime_type, payload) -> Any`.
  - `drops.drop_product(plot, product, panel)`: the old `tree.drop` behaviour. It never raises, shows a refusal on failure, and returns what the rule returned.
  - `drops.accept_drop_rules(panel)`: gives the panel one callback per MIME type that has rules, now and as rules are added. The panel keeps them in `panel._drop_callbacks: dict[str, PlotDragNDropCallback]`, and `panel._product_plot_callback` stays as the product-list callback.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_drop_rules.py`:

```python
"""Drop rules (spec §4.3): what a drop does is chosen by MIME type, product kind and target plot kind."""
import pytest

from SciQLop.core.drop_rules import DROP_RULES, DropRule, rule_for
from SciQLop.core.extensions import owned_by
from SciQLop.core.mime.types import CATALOG_LIST_MIME_TYPE, PRODUCT_LIST_MIME_TYPE, TIME_RANGE_MIME_TYPE
from SciQLop.core.plot_kinds import PROJECTION, TIMESERIES
from SciQLop.core.product_kinds import BOUNDARY, LAYER, SCALAR, SCENE

_THING = "application/x.drop-rules-test.thing"


@pytest.fixture
def withdraw(qapp):
    yield
    DROP_RULES.remove_owner("dr_demo")


@pytest.mark.parametrize("product_kind, target, rule_id", [
    (SCENE, PROJECTION, "sciqlop.scenes.plot_scene"), (SCENE, TIMESERIES, "sciqlop.scenes.plot_scene"),
    (SCENE, None, "sciqlop.scenes.plot_scene"),
    (BOUNDARY, PROJECTION, "sciqlop.scenes.set_boundary"), (BOUNDARY, TIMESERIES, "sciqlop.scenes.refuse_boundary"),
    (SCALAR, PROJECTION, "sciqlop.scenes.add_trajectory"), (SCALAR, TIMESERIES, "sciqlop.plot_product"),
    (None, TIMESERIES, "sciqlop.plot_product"), (None, PROJECTION, "sciqlop.scenes.add_trajectory"),
    (LAYER, PROJECTION, "sciqlop.layers.attach"), (LAYER, TIMESERIES, "sciqlop.layers.attach"),
])
def test_core_product_rules_reproduce_the_old_drop_table(qapp, product_kind, target, rule_id):
    assert rule_for(PRODUCT_LIST_MIME_TYPE, product_kind, target).id == rule_id


def test_core_rules_for_time_ranges_and_catalogs(qapp):
    assert rule_for(TIME_RANGE_MIME_TYPE, None, TIMESERIES).id == "sciqlop.time_range"
    assert rule_for(CATALOG_LIST_MIME_TYPE, None, TIMESERIES).id == "sciqlop.catalogs.overlay"
    assert all(DROP_RULES.owner_of(r.id) == "sciqlop" for r in DROP_RULES.list() if r.id.startswith("sciqlop."))


def test_the_product_kind_outweighs_the_target(withdraw):
    with owned_by("dr_demo"):
        for rid, pk, target in (("dr_demo.any", None, None), ("dr_demo.kind", "dr_demo.k", None),
                                ("dr_demo.target", None, "dr_demo.t"), ("dr_demo.both", "dr_demo.k", "dr_demo.t")):
            DROP_RULES.contribute(DropRule(rid, _THING, lambda *a: None, product_kind=pk, target=target))
    assert rule_for(_THING, "dr_demo.k", "dr_demo.t").id == "dr_demo.both"
    assert rule_for(_THING, "dr_demo.k", "other").id == "dr_demo.kind"
    assert rule_for(_THING, "other", "dr_demo.t").id == "dr_demo.target"
    assert rule_for(_THING, "other", "other").id == "dr_demo.any"
    assert rule_for("application/x.nobody", None, None) is None


def test_open_panels_accept_a_mime_type_added_later(qtbot, withdraw):
    from PySide6.QtCore import QMimeData
    from SciQLopPlots import PlotType
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.core.mime import MIME_TYPES, MimeType
    panel = TimeSyncPanel("dr_panel", show_search_overlay=False)
    qtbot.addWidget(panel)
    panel.create_plot(0, PlotType.TimeSeries)
    dropped = []
    with owned_by("dr_demo"):
        MIME_TYPES.contribute(MimeType(_THING, lambda md: bytes(md.data(_THING)).decode()))
        DROP_RULES.contribute(DropRule("dr_demo.thing", _THING, lambda plot, payload, p: dropped.append(payload)))
    try:
        assert _THING in panel._drop_callbacks
        md = QMimeData()
        md.setData(_THING, b"hello")
        panel._drop_callbacks[_THING].call(panel.plots()[0], md)
        assert dropped == ["hello"]
    finally:
        MIME_TYPES.remove_owner("dr_demo")
```

- [ ] **Step 2: Run them and see them fail**

Run: `uv run --no-sync pytest tests/test_drop_rules.py -q -p no:cacheprovider`
Expected: FAIL with an ImportError on `SciQLop.core.drop_rules`.

- [ ] **Step 3: Implement**

Create `SciQLop/core/drop_rules.py`:

```python
"""What dropping something on a plot does: the sciqlop.drop_rules extension point (spec §4.3)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from SciQLop.core.extensions import ExtensionPoint, declare


@dataclass(frozen=True)
class DropRule:
    id: str
    mime_type: str
    drop: Callable[[Any, Any, Any], Any]   # (plot or None, payload, panel); product drops get one product path
    product_kind: Optional[str] = None     # product-list drops: the dragged product's kind; None = any
    target: Optional[str] = None           # plot kind of the plot dropped on; None = any
    creates_plot: bool = False             # a drop between plots makes a new plot for it


DROP_RULES = declare(ExtensionPoint("sciqlop.drop_rules", DropRule, what="drop rule",
                                    doc="What a drop of one MIME type does, by product kind and target plot kind."))


def _weight(rule: DropRule) -> int:
    return 2 * (rule.product_kind is not None) + (rule.target is not None)


def rule_for(mime_type: str, product_kind: Optional[str], target: Optional[str]) -> Optional[DropRule]:
    """The most specific rule: a matching product kind outweighs a matching target; ties go to the smallest id."""
    matching = [r for r in DROP_RULES.list() if r.mime_type == mime_type
                and r.product_kind in (None, product_kind) and r.target in (None, target)]
    return min(matching, key=lambda r: (-_weight(r), r.id), default=None)
```

Create `SciQLop/components/plotting/drops.py`. It contains:
- `drop_product`: the old `tree.drop` behaviour, generalised;
- `dispatch_drop`;
- the rule callback class;
- `accept_drop_rules`.

```python
"""Drops on a plot panel go through sciqlop.drop_rules."""
from SciQLopPlots import PlotDragNDropCallback, ProductsModel

from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.drop_rules import DROP_RULES, rule_for
from SciQLop.core.mime import decode_mime
from SciQLop.core.mime.types import PRODUCT_LIST_MIME_TYPE
from SciQLop.core.plot_kinds import plot_kind_of
from SciQLop.core.product_kinds import product_kind_of

log = getLogger(__name__)


def _kind_id(kind):
    return kind.id if kind is not None else None


def drop_product(plot, product: list[str], panel):
    """Put *product* on *plot* (None: on *panel*) as the drop rules say. Never raises: a refusal or failure
    shows why. Returns what the rule returned."""
    from SciQLop.components.scenes.scene_plot import concrete_plot
    from SciQLop.components.scenes.tree import show_refusal
    node = ProductsModel.node(product)
    if node is None:
        return None
    plot = concrete_plot(plot)
    rule = rule_for(PRODUCT_LIST_MIME_TYPE, _kind_id(product_kind_of(node)), _kind_id(plot_kind_of(plot)))
    if rule is None:
        return None
    try:
        return rule.drop(plot, product, panel)
    except Exception as e:
        log.error(f"drop of {product} failed", exc_info=True)
        show_refusal(plot, panel, f"{product[-1]}: {e}")
        return None


def dispatch_drop(panel, plot, mime_type: str, payload):
    if payload is None:
        return None
    if mime_type == PRODUCT_LIST_MIME_TYPE:
        return [drop_product(plot, product, panel) for product in payload]
    rule = rule_for(mime_type, None, _kind_id(plot_kind_of(plot)))
    return None if rule is None else rule.drop(plot, payload, panel)


class RuleDnDCallback(PlotDragNDropCallback):
    def __init__(self, mime_type: str, creates_plot: bool, parent):
        super().__init__(mime_type, creates_plot, parent)
        self._mime_type = mime_type

    def call(self, plot, mime_data):
        dispatch_drop(self.parent(), plot, self._mime_type, decode_mime(mime_data, [self._mime_type]))


def _creates_plot(mime_type: str) -> bool:
    return any(r.creates_plot for r in DROP_RULES.list(mime_type=mime_type))


def _accept(panel, mime_type: str) -> None:
    """simplify: the placeholder flag is fixed when the MIME type's first callback is made; a rule added later
    with creates_plot=True for an already-accepted MIME type does not change it. Recreate the callback if a
    plugin ever needs that."""
    if mime_type in panel._drop_callbacks:
        return
    callback = RuleDnDCallback(mime_type, _creates_plot(mime_type), panel)
    panel._drop_callbacks[mime_type] = callback
    panel.add_accepted_mime_type(callback)


def accept_drop_rules(panel) -> None:
    """One callback per MIME type with rules, now and whenever a rule for a new MIME type is contributed."""
    panel._drop_callbacks = {}
    for mime_type in sorted({r.mime_type for r in DROP_RULES.list()}):
        _accept(panel, mime_type)
    panel._product_plot_callback = panel._drop_callbacks.get(PRODUCT_LIST_MIME_TYPE)
    DROP_RULES.signals.added.connect(panel, lambda rule: _accept(panel, rule.mime_type))
```

Check the exact receiver-context `connect` form against `docs/qt-lifetime-patterns.md` before using the last line, which connects with the panel as context. The connection must die with the panel and must never call into a destroyed panel. If that document prescribes another form, use it, and say so in the report. Check `PlotDragNDropCallback`'s constructor in the installed SciQLopPlots (`mime_type, create_placeholder=False, parent=None`) and the panel method `add_accepted_mime_type`.

Core rules go at the end of `components/plotting/core_kinds.py`:

```python
def _plot_product_drop(plot, product, panel):
    from SciQLop.components.plotting.ui.time_sync_panel import plot_product
    plot_product(plot, product)


def _zoom(plot, time_range, panel):
    plot.time_axis().set_range(time_range)


def _overlay_catalogs(plot, catalogs, panel):
    for cat in catalogs or []:
        panel.catalog_manager.add_catalog(cat)


def _attach_layer(plot, product, panel):
    from SciQLop.components.plotting.ui.time_sync_panel import attach_layer
    return attach_layer(plot, product, panel=panel)


for _rule in (DropRule("sciqlop.plot_product", PRODUCT_LIST_MIME_TYPE, _plot_product_drop, creates_plot=True),
              DropRule("sciqlop.layers.attach", PRODUCT_LIST_MIME_TYPE, _attach_layer, product_kind=LAYER),
              DropRule("sciqlop.time_range", TIME_RANGE_MIME_TYPE, _zoom),
              DropRule("sciqlop.catalogs.overlay", CATALOG_LIST_MIME_TYPE, _overlay_catalogs)):
    DROP_RULES.contribute(_rule, owner="sciqlop")
```

`_plot_product_drop` must do exactly what the old `tree.plot_product` handler did: read that handler, which calls `time_sync_panel.plot_product`, and call the same function. Two cases to watch. A product without a kind, such as an unknown speasy node, lands on the `sciqlop.plot_product` rule. A drop between plots arrives with the placeholder plot SciQLopPlots made. Both behave as before.

Scenes rules go at the end of `components/scenes/contributions.py`. They reuse the handlers that stay in `tree.py` (`plot_scene`, `set_boundary`, `refuse`, `add_trajectory`):

```python
def _scene_rules():
    from SciQLop.components.scenes import tree
    return (DropRule("sciqlop.scenes.plot_scene", PRODUCT_LIST_MIME_TYPE, tree.plot_scene, product_kind=SCENE,
                     creates_plot=True),
            DropRule("sciqlop.scenes.set_boundary", PRODUCT_LIST_MIME_TYPE, tree.set_boundary,
                     product_kind=BOUNDARY, target=PROJECTION),
            DropRule("sciqlop.scenes.refuse_boundary", PRODUCT_LIST_MIME_TYPE, tree.refuse, product_kind=BOUNDARY),
            DropRule("sciqlop.scenes.add_trajectory", PRODUCT_LIST_MIME_TYPE, tree.add_trajectory,
                     target=PROJECTION))


for _rule in _scene_rules():
    DROP_RULES.contribute(_rule, owner="sciqlop")
```

If importing `tree` at module level from `contributions.py` creates a cycle, keep the function-local import as shown. Otherwise import it at the top.

In `scenes/tree.py`:
- delete `_TABLE`, `drop_handler` and the `plot_product`/`attach_layer` handler wrappers that the core rules now replace;
- `drop(plot, product, panel)` becomes a thin wrapper that keeps its docstring and returns `drops.drop_product(plot, product, panel)`;
- grep for `drop_handler` and `_TABLE` users in SciQLop/ and tests/, and update them to `rule_for`/`drop_product`. `tests/scenes/test_scene_tree.py:15-20` (`test_drop_table`) parametrizes the old `(kind, on_scene) → handler name` table. Rewrite it to assert `rule_for(PRODUCT_LIST_MIME_TYPE, <product kind id>, PROJECTION if on_scene else TIMESERIES).drop` is the same handler. Use the mapping "scene" → `SCENE`, "boundary" → `BOUNDARY`, "layer" → `LAYER`, "product" → `SCALAR`. Keep every row.

In `time_sync_panel.py`, delete `ProductDnDCallback`, `TimeRangeDnDCallback` and `CatalogDnDCallback`. In `TimeSyncPanel.__init__`, replace the six callback lines with `accept_drop_rules(self)`, imported from `SciQLop.components.plotting.drops`. Grep tests for `_time_range_plot_callback`/`_catalog_plot_callback` and switch them to `panel._drop_callbacks[<MIME>]`.

In `prepare_extension_points`, add `import SciQLop.core.drop_rules  # noqa: F401  declares sciqlop.drop_rules`, placed before the contribution modules.

Docs: in `references/ui-and-settings.md`, add a "Drop rules" paragraph covering the `DropRule` fields, the weighting, and a 5-line example of a plugin rule for its product kind.

- [ ] **Step 4: Run them and see them pass**

Run: `uv run --no-sync pytest tests/test_drop_rules.py tests/scenes tests/test_coverage_notice.py tests/test_catalog_dnd.py tests/test_event_dnd.py tests/test_wf_drag_and_drop.py tests/test_layers tests/test_plot_kinds.py -q -p no:cacheprovider`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/core/drop_rules.py SciQLop/components/plotting/drops.py SciQLop/components/plotting/core_kinds.py SciQLop/components/scenes/contributions.py SciQLop/components/scenes/tree.py SciQLop/components/plotting/ui/time_sync_panel.py SciQLop/components/extension_points.py SciQLop/components/agents/skills/sciqlop-plugin-design/references/ui-and-settings.md tests/test_drop_rules.py
```

Also add any test file you adjusted. Then:

```bash
git commit -m "feat(plugins): drop rules are contributions to sciqlop.drop_rules; panels accept every MIME type with rules"
```

---

### Task 3: The panel tree file format (v3), restore through plot kinds, and placeholders

**Files:**
- Modify: `SciQLop/components/plotting/panel_template.py`
- Create: `SciQLop/components/plotting/placeholder.py`
- Modify: `SciQLop/components/plotting/panel_introspection.py` (`ordered_panel_plots`)
- Modify: `SciQLop/components/plotting/core_kinds.py` (`sciqlop.timeseries` gains `to_config`/`from_config`)
- Test: `tests/test_panel_tree.py` (new); the existing template tests

**Interfaces:**
- Consumes: `PLOT_KINDS`, `PlotKind`, `plot_kind_of`, `plugin_of`, `TIMESERIES`, `TIME_PANEL` (Task 1).
- Produces:
  - `PlotModel` gains `kind: str = TIMESERIES` and `config: dict = {}`, and `products` defaults to `[]`. A time-series plot uses the existing fields; any other kind keeps everything in `config`.
  - `TEMPLATE_VERSION = 3`.
  - `PanelTemplate.to_tree() -> dict` and `PanelTemplate.from_tree(data: dict) -> PanelTemplate`.
  - `PanelNode(kind, id="", config={}, slots={})`, a pydantic model.
  - `placeholder.add_placeholder(panel, model: PlotModel, reason: str = "") -> plot` and `placeholder.placeholder_model(plot) -> PlotModel | None`.
  - `panel_introspection.ordered_panel_plots(panel) -> list`: every plot in panel order, each a concrete widget.
  - `core_kinds` time-series `from_config(panel, config)` returns a user_api plot wrapper.

The v3 file layout (JSON shown; YAML is the same tree):

```json
{"version": 3, "name": "event", "description": "", "max_zoom_seconds": null, "intervals": [],
 "panel": {"kind": "sciqlop.time_panel", "id": "", "config": {"time_range": {"start": "...", "stop": "..."}},
           "slots": {"plots": [
             {"kind": "sciqlop.timeseries", "id": "", "slots": {},
              "config": {"products": [...], "y_axis": {...}, "y2_axis": {...}, "z_axis": {...}}},
             {"kind": "vdf.slice_plot", "id": "", "slots": {}, "config": {"plane": "XY"}}]}}}
```

- [ ] **Step 1: Write the failing tests**

Create `tests/test_panel_tree.py`:

```python
"""Panels as trees (spec §5): v3 files, older files migrate, unknown kinds survive as placeholders."""
import json

import pytest

from SciQLop.components.plotting.panel_template import (TEMPLATE_VERSION, PanelTemplate, PlotModel,
                                                        ProductModel, TimeRangeModel)
from SciQLop.core.extensions import owned_by
from SciQLop.core.plot_kinds import PLOT_KINDS, TIME_PANEL, TIMESERIES, PlotKind


def _template():
    return PanelTemplate(
        name="tree", time_range=TimeRangeModel(start="2020-01-01T00:00:00+00:00", stop="2020-01-02T00:00:00+00:00"),
        plots=[PlotModel(products=[ProductModel(path="speasy//amda//imf", kind="speasy", graph_type="Line",
                                                y_axis="y")]),
               PlotModel(kind="pt_demo.slice_plot", config={"plane": "XY"})])


def test_v3_is_a_panel_tree(tmp_path):
    path = tmp_path / "t.json"
    _template().to_file(str(path))
    data = json.loads(path.read_text())
    assert TEMPLATE_VERSION == 3 and data["version"] == 3
    assert data["panel"]["kind"] == TIME_PANEL
    assert data["panel"]["config"]["time_range"]["start"].startswith("2020-01-01")
    plots = data["panel"]["slots"]["plots"]
    assert [p["kind"] for p in plots] == [TIMESERIES, "pt_demo.slice_plot"]
    assert plots[0]["config"]["products"][0]["path"] == "speasy//amda//imf"
    assert plots[1]["config"] == {"plane": "XY"}


@pytest.mark.parametrize("suffix", [".json", ".yaml"])
def test_v3_round_trips(tmp_path, suffix):
    path = tmp_path / f"t{suffix}"
    _template().to_file(str(path))
    assert PanelTemplate.from_file(str(path)).model_dump() == _template().model_dump()


def test_a_v2_file_reads_as_the_same_model_and_rewrites_as_v3(tmp_path):
    v2 = {"name": "old", "version": 2, "plots": [{"products": [{"path": "speasy//amda//imf", "graph_type": "Line",
                                                                "y_axis": "y"}]}]}
    path = tmp_path / "old.json"
    path.write_text(json.dumps(v2))
    t = PanelTemplate.from_file(str(path))
    assert t.plots[0].kind == TIMESERIES and t.plots[0].products[0].path == "speasy//amda//imf"
    t.to_file(str(path))
    assert json.loads(path.read_text())["version"] == 3
    assert PanelTemplate.from_file(str(path)).model_dump() == t.model_dump()


def test_a_v1_file_still_gets_its_axes(tmp_path):
    v1 = {"name": "older", "plots": [{"products": [{"path": "a//b", "graph_type": "ColorMap"}]}]}
    path = tmp_path / "older.json"
    path.write_text(json.dumps(v1))
    assert PanelTemplate.from_file(str(path)).plots[0].products[0].y_axis == "y2"


def test_an_unknown_panel_kind_is_refused_with_its_plugin(tmp_path):
    path = tmp_path / "x.json"
    path.write_text(json.dumps({"version": 3, "name": "x", "panel": {"kind": "vdf.study_panel"}}))
    with pytest.raises(ValueError, match="vdf"):
        PanelTemplate.from_file(str(path))


def test_unknown_plot_kind_restores_as_a_placeholder_that_keeps_its_node(qtbot):
    from SciQLop.components.plotting.placeholder import placeholder_model
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    panel = TimeSyncPanel("pt_panel", show_search_overlay=False)
    qtbot.addWidget(panel)
    t = PanelTemplate(name="p", plots=[PlotModel(kind="pt_gone.slice_plot", config={"plane": "YZ"})])
    t.apply(panel)
    assert len(panel.plots()) == 1
    saved = PanelTemplate.from_panel(panel)
    assert [(p.kind, p.config) for p in saved.plots] == [("pt_gone.slice_plot", {"plane": "YZ"})]


def test_a_plot_kind_restores_through_from_config_and_saves_through_to_config(qtbot):
    from SciQLopPlots import PlotType
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    made = {}

    def from_config(panel, config):
        panel.create_plot(-1, PlotType.TimeSeries)
        plot = panel.plots()[-1]
        made[plot.objectName()] = dict(config)
        return plot

    def owns(plot):
        return plot.objectName() in made

    with owned_by("pt_demo"):
        PLOT_KINDS.contribute(PlotKind("pt_demo.slice_plot", "Slice", plot_product=lambda *a: None, owns=owns,
                                       to_config=lambda plot: made[plot.objectName()], from_config=from_config))
    try:
        panel = TimeSyncPanel("pt_panel2", show_search_overlay=False)
        qtbot.addWidget(panel)
        PanelTemplate(name="p", plots=[PlotModel(kind="pt_demo.slice_plot", config={"plane": "XY"})]).apply(panel)
        assert list(made.values()) == [{"plane": "XY"}]
        assert [(p.kind, p.config) for p in PanelTemplate.from_panel(panel).plots] == [
            ("pt_demo.slice_plot", {"plane": "XY"})]
    finally:
        PLOT_KINDS.remove_owner("pt_demo")


def test_a_failing_from_config_leaves_a_placeholder_not_a_broken_panel(qtbot):
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel

    def boom(panel, config):
        raise RuntimeError("bad config")

    with owned_by("pt_demo"):
        PLOT_KINDS.contribute(PlotKind("pt_demo.broken", "Broken", plot_product=lambda *a: None, from_config=boom))
    try:
        panel = TimeSyncPanel("pt_panel3", show_search_overlay=False)
        qtbot.addWidget(panel)
        PanelTemplate(name="p", plots=[PlotModel(kind="pt_demo.broken", config={"a": 1})]).apply(panel)
        assert [(p.kind, p.config) for p in PanelTemplate.from_panel(panel).plots] == [("pt_demo.broken", {"a": 1})]
    finally:
        PLOT_KINDS.remove_owner("pt_demo")
```

Check `panel.create_plot`'s signature and return value in the existing tests before relying on them; `tests/test_coverage_notice.py` uses `panel.create_plot(0, PlotType.TimeSeries)`. If `-1` does not append, use `len(panel.plots())`.

- [ ] **Step 2: Run them and see them fail**

Run: `uv run --no-sync pytest tests/test_panel_tree.py -q -p no:cacheprovider`
Expected: FAIL. `PlotModel` has no `kind`, and `TEMPLATE_VERSION` is 2.

- [ ] **Step 3: Implement**

**`PlotModel`** (panel_template.py): `products: list[ProductModel] = []`, `kind: str = TIMESERIES`, `config: dict[str, Any] = {}`. Import `TIMESERIES` and `TIME_PANEL` from `SciQLop.core.plot_kinds`.

**Tree model and format:**

```python
TEMPLATE_VERSION = 3
_V2 = 2


class PanelNode(BaseModel):
    """A node of the panel tree (spec §5); its kind names a sciqlop.plot_kinds contribution or a panel kind."""
    kind: str
    id: str = ""
    config: dict[str, Any] = {}
    slots: dict[str, list["PanelNode"]] = {}


def _plot_node(plot: PlotModel) -> PanelNode:
    if plot.kind == TIMESERIES:
        return PanelNode(kind=TIMESERIES, config=plot.model_dump(mode="json", exclude={"kind", "config"}))
    return PanelNode(kind=plot.kind, config=plot.config)


def _plot_model(node: PanelNode) -> PlotModel:
    if node.kind == TIMESERIES:
        return PlotModel.model_validate(node.config)
    return PlotModel(kind=node.kind, config=node.config)
```

The name `_plot_model` is already taken by the restore function. Name the new one `_plot_model_of(node)`, and rename the existing restore function `_restore_timeseries(panel, plot_model)`. Grep for its callers.

`PanelTemplate` gains:

```python
    def to_tree(self) -> dict:
        root = PanelNode(kind=TIME_PANEL,
                         config={"time_range": self.time_range.model_dump() if self.time_range else None},
                         slots={"plots": [_plot_node(p) for p in self.plots]})
        return {"version": TEMPLATE_VERSION, "name": self.name, "description": self.description,
                "max_zoom_seconds": self.max_zoom_seconds,
                "intervals": [i.model_dump() for i in self.intervals], "panel": root.model_dump(mode="json")}

    @staticmethod
    def from_tree(data: dict) -> "PanelTemplate":
        root = PanelNode.model_validate(data["panel"])
        if root.kind != TIME_PANEL:
            raise ValueError(f"panel kind {root.kind!r} needs plugin {plugin_of(root.kind)!r} (panel kinds other "
                             f"than {TIME_PANEL} are not supported yet)")
        time_range = root.config.get("time_range")
        return PanelTemplate(name=data["name"], description=data.get("description", ""),
                             max_zoom_seconds=data.get("max_zoom_seconds"),
                             intervals=data.get("intervals", []),
                             time_range=TimeRangeModel(**time_range) if time_range else None,
                             plots=[_plot_model_of(n) for n in root.slots.get("plots", [])])
```

The `from_file` and `to_file` changes:
- `from_file` dispatches with `PanelTemplate.from_tree(data) if data.get("version", 1) >= 3 else PanelTemplate.model_validate({**_upgrade(data), "version": TEMPLATE_VERSION})`. The in-memory model always carries the current version; the file's own version is kept in `_saved_version`. `_upgrade` keeps producing the v2 shape: compare with `_V2`, set `"version": _V2`, and leave its v1→v2 logic unchanged.
- Keep `t._saved_version = data.get("version", 1)` so `list_templates` rewrites v1 and v2 files as v3. It already compares with `TEMPLATE_VERSION`.
- `to_file` writes `self.to_tree()`: `json.dumps(..., indent=2)` for `.json`, and `yaml.dump(..., default_flow_style=False, sort_keys=False)` for YAML.
- `version` stays a field on the in-memory model with default `TEMPLATE_VERSION`.

**Restore via plot kinds.** `apply` calls `_restore_plot(panel, plot_model)` for each plot:

```python
def _restore_plot(panel, model: PlotModel):
    """A plot kind that is not registered, or whose from_config fails, leaves a placeholder that keeps the node."""
    from SciQLop.components.plotting.placeholder import add_placeholder
    if model.kind == TIMESERIES:
        return _restore_timeseries(panel, model)
    kind = PLOT_KINDS.get(model.kind) if model.kind in PLOT_KINDS else None
    if kind is None or kind.from_config is None:
        return add_placeholder(panel, model)
    try:
        return kind.from_config(panel, model.config)
    except Exception as e:
        log.error(f"restoring a {model.kind} plot failed", exc_info=True)
        return add_placeholder(panel, model, reason=str(e))
```

**Save via plot kinds.** `from_panel` iterates `ordered_panel_plots(panel)` and maps each plot with `_saved_plot(plot)`:

```python
def _saved_plot(plot) -> Optional[PlotModel]:
    from SciQLop.components.plotting.placeholder import placeholder_model
    kept = placeholder_model(plot)
    if kept is not None:
        return kept
    kind = plot_kind_of(plot)
    if kind.id == TIMESERIES:
        return _timeseries_model(plot)
    if kind.to_config is None:
        log.warning(f"a {kind.id} plot is not saved: its plot kind has no to_config")
        return None
    return PlotModel(kind=kind.id, config=kind.to_config(plot))
```

`_timeseries_model(plot)` is today's per-plot body of `from_panel`: `plot_graphs`, the product models with `y_axis`, and the three captured axes. It returns None when the plot has no graphs, exactly as today.

`ordered_panel_plots(panel)` (panel_introspection.py) returns `[_concrete(ptr) for ptr in panel.plots()]`, where `_concrete` unwraps `SciQLopPlotInterfacePtr` with `ptr.data()` the way `scenes.scene_plot.concrete_plot` does. Copy that three-line helper rather than importing scenes into plotting. Check that time-series plots unwrap to the same widgets `ordered_plots` returns: the existing template tests must keep passing. `ordered_plots` stays for its other callers.

**Time-series plot kind.** In `core_kinds.py`, give the `sciqlop.timeseries` contribution:
- `to_config=lambda plot: _timeseries_config(plot)`, which returns the `_timeseries_model(plot)` dump with `kind` and `config` excluded;
- `from_config=_timeseries_from_config`. It validates `PlotModel.model_validate(config)`, calls `_restore_timeseries(panel, model)`, and returns `SciQLop.user_api.plot._plots.to_plot(subplot)` when a subplot was made (check the real name of `to_plot` in `user_api/plot`). Make `_restore_timeseries` return the subplot it created; today it returns nothing.

**Placeholder** (`SciQLop/components/plotting/placeholder.py`):

```python
"""A plot that stands in for one whose kind is not available; it keeps its node so saving again loses nothing."""
import shiboken6
from SciQLopPlots import OverlayLevel, OverlayPosition, OverlaySizeMode, PlotType

from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.plot_kinds import plugin_of

log = getLogger(__name__)
_KEPT: dict = {}


def _key(plot) -> int:
    return shiboken6.getCppPointer(plot)[0]


def _message(model, reason: str) -> str:
    why = f": {reason}" if reason else f" (plugin {plugin_of(model.kind)!r} is not installed or not enabled)"
    return f"This {model.kind} plot cannot be shown{why}. Install or enable the plugin, then reopen the template."


def add_placeholder(panel, model, reason: str = ""):
    """simplify: names the plugin from the kind's id prefix; look it up in the app-store index by `provides`
    once that index carries it (sciqlop-appstore generator)."""
    from SciQLop.components.plotting.ui.diagnostic_overlay import overlay_of
    from SciQLop.components.scenes.scene_plot import concrete_plot
    panel.create_plot(len(panel.plots()), PlotType.TimeSeries)
    plot = concrete_plot(panel.plots()[-1])
    key = _key(plot)
    _KEPT[key] = model
    plot.destroyed.connect(lambda *_: _KEPT.pop(key, None))
    message = _message(model, reason)
    log.warning(message)
    overlay_of(plot).show_message(message, OverlayLevel.Warning, OverlaySizeMode.FitContent, OverlayPosition.Top)
    return plot


def placeholder_model(plot):
    try:
        return _KEPT.get(_key(plot))
    except Exception:
        return None
```

Check that `OverlayLevel.Warning` exists (scenes uses `OverlayLevel.Error`), and check `panel.create_plot`'s signature. Adapt to what you find and say so in the report.

**Callers of `template.plots`** (proxy_share, graph_context_snippets, agents `build_panel`). They read `products` and axes. A non-time-series `PlotModel` now has `products == []`, so those callers skip it naturally. Grep for `.plots` uses on templates and confirm that none breaks on `kind != TIMESERIES`.

Docs: none in this task. Task 6 documents the tree.

- [ ] **Step 4: Run them and see them pass**

Run: `uv run --no-sync pytest tests/test_panel_tree.py tests/test_panel_template.py tests/test_panel_template_integration.py tests/test_panel_template_fetches.py tests/test_template_axes.py tests/test_proxy_share.py tests/test_panel_container.py tests/test_agent_build_panel.py -q -p no:cacheprovider`
Expected: all PASS. If `tests/test_agent_build_panel.py` doesn't exist, find the build_panel tests with `grep -rln build_panel tests` and run those instead.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/plotting/panel_template.py SciQLop/components/plotting/placeholder.py SciQLop/components/plotting/panel_introspection.py SciQLop/components/plotting/core_kinds.py tests/test_panel_tree.py
git commit -m "feat(plugins): panels are saved as a {kind, config, slots} tree (template v3); unknown plot kinds restore as placeholders"
```

---

### Task 4: Scene plots are saved and restored

**Files:**
- Modify: `SciQLop/user_api/scenes/__init__.py` (`ScenePlot` records trajectories)
- Modify: `SciQLop/components/scenes/contributions.py` (`sciqlop.scenes.projection` gains `to_config`/`from_config`)
- Test: `tests/scenes/test_scene_plot_persistence.py` (new)

**Interfaces:**
- Consumes: `PlotKind`, `PROJECTION` (Task 1); `_restore_plot` and `_saved_plot` in the template (Task 3); `ScenePlot`, `scene_plot_for`, `PlotPanel.plot_scene`.
- Produces: scene-plot config `{"scene": <registered scene name>, "boundaries": {<kind>: <boundary model name>}, "trajectories": [<source>, ...]}`.

- [ ] **Step 1: Write the failing tests**

Create `tests/scenes/test_scene_plot_persistence.py`. It uses the existing fixtures:
- `plot_panel` (tests/fixtures.py: a user_api `PlotPanel` in the test main window);
- `registered` (tests/scenes/conftest.py: the built-in planetary scenes registered and listed in the tree; it pulls in `earth`, which stubs frame rotations).

The scene "Earth environment" has the boundaries `{"magnetopause": "shue1998", "bow_shock": "jelinek2012"}`.

```python
"""Scene plots are saved in templates (spec §5) and restored by name."""
from SciQLop.components.plotting.panel_template import PanelTemplate, PlotModel
from SciQLop.core.plot_kinds import PROJECTION

_EARTH = {"scene": "Earth environment", "boundaries": {"magnetopause": "shue1998", "bow_shock": "jelinek2012"}}


def test_a_scene_plot_round_trips_through_a_template(plot_panel, registered, monkeypatch, tmp_path):
    from SciQLop.components.scenes.scene_plot import scene_plot_for
    from SciQLop.user_api.plot import create_plot_panel
    from SciQLop.user_api.scenes import ScenePlot
    sp = plot_panel.plot_scene("Earth environment")
    sp._trajectories.append("speasy//amda//mms1_xyz")  # recorded without fetching: no network in tests
    saved = PanelTemplate.from_panel(plot_panel._get_impl_or_raise())
    assert [(p.kind, p.config) for p in saved.plots] == [
        (PROJECTION, {**_EARTH, "trajectories": ["speasy//amda//mms1_xyz"]})]

    path = tmp_path / "scene.yaml"
    saved.to_file(str(path))
    restored = []
    monkeypatch.setattr(ScenePlot, "add_trajectory", lambda self, source: restored.append(source))
    other = create_plot_panel()._get_impl_or_raise()
    PanelTemplate.from_file(str(path)).apply(other)
    sp2 = next(s for s in map(scene_plot_for, other.plots()) if s is not None)
    assert sp2.scene.name == "Earth environment"
    assert {k: m.name for k, m in sp2._resolved.boundaries.items()} == _EARTH["boundaries"]
    assert restored == ["speasy//amda//mms1_xyz"]


def test_an_unregistered_scene_restores_as_a_placeholder(plot_panel, registered):
    impl = plot_panel._get_impl_or_raise()
    t = PanelTemplate(name="s", plots=[PlotModel(kind=PROJECTION, config={"scene": "nowhere_gsm", "boundaries": {},
                                                                          "trajectories": []})])
    t.apply(impl)
    assert [(p.kind, p.config["scene"]) for p in PanelTemplate.from_panel(impl).plots] == [(PROJECTION, "nowhere_gsm")]
```

If `scene_plot_for(ptr)` for an item of `other.plots()` does not find the ScenePlot because of the pointer wrapper, unwrap with `concrete_plot` first; it does that already. If `create_plot_panel()` needs the `main_window` fixture explicitly, add it: `plot_panel` depends on it already.

- [ ] **Step 2: Run them and see them fail**

Run: `uv run --no-sync pytest tests/scenes/test_scene_plot_persistence.py -q -p no:cacheprovider`
Expected: FAIL. `_trajectories` doesn't exist, and scene plots aren't saved.

- [ ] **Step 3: Implement**

In `ScenePlot.__init__`, set `self._trajectories: list[str] = []`. In `add_trajectory`, append `source` after the trajectory was added successfully, so a refused source is not saved.

In `contributions.py`:

```python
def _scene_config(plot) -> dict:
    from SciQLop.components.scenes.scene_plot import scene_plot_for
    sp = scene_plot_for(plot)
    return {"scene": sp.scene.name,
            "boundaries": {kind: model.name for kind, model in sp._resolved.boundaries.items()},
            "trajectories": list(sp._trajectories)}


def _scene_from_config(panel, config: dict):
    """simplify: only registered scenes and boundaries round-trip (by name); an ad-hoc Scene object is saved by
    name and restores as a placeholder. Save full scene definitions if users plot unregistered scenes."""
    from SciQLop.user_api.plot import PlotPanel
    sp = PlotPanel(panel).plot_scene(config["scene"])
    for kind, name in config.get("boundaries", {}).items():
        sp.set_boundary(kind, name)
    for source in config.get("trajectories", []):
        sp.add_trajectory(source)
    return sp
```

Add `to_config=_scene_config, from_config=_scene_from_config` to the `sciqlop.scenes.projection` contribution.

Two things to check before wiring this in. First, `resolved.boundaries` maps kind → model, and models carry `.name`; read `components/scenes/model.py`. Second, `PlotPanel(panel)` accepts the panel impl, as `tree.plot_scene` does. A boundary that is not registered any more makes `set_boundary` raise. The template's `_restore_plot` catches that and leaves a placeholder (Task 3), so no extra handling is needed here.

Docs: in `references/ui-and-settings.md`, say that scene plots are saved in templates, but only registered scenes and boundaries.

- [ ] **Step 4: Run them and see them pass**

Run: `uv run --no-sync pytest tests/scenes tests/test_panel_tree.py -q -p no:cacheprovider`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/user_api/scenes/__init__.py SciQLop/components/scenes/contributions.py SciQLop/components/agents/skills/sciqlop-plugin-design/references/ui-and-settings.md tests/scenes/test_scene_plot_persistence.py
git commit -m "feat(scenes): scene plots are saved in templates and restored (registered scenes and boundaries)"
```

---

### Task 5: `PlotPanel.add(kind, **config)`

**Files:**
- Modify: `SciQLop/user_api/plot/_panel.py` (new method on `PlotPanel`)
- Test: `tests/test_plot_panel_add.py` (new)
- Global memory: `/home/jeandet/.claude/memory/sciqlop-user-api.md` (outside the repo, not committed)

**Interfaces:**
- Consumes: `PLOT_KINDS`, `TIMESERIES`, `PlotKind.from_config` (Tasks 1, 3, 4).
- Produces: `PlotPanel.add(kind: str, **config)`, which returns what that plot kind's `from_config` returns: a user_api `TimeSeriesPlot` for `sciqlop.timeseries`, a `ScenePlot` for `sciqlop.scenes.projection`, or the plugin's object. It raises `NotRegistered`, naming the available kinds, when the kind is unknown. It raises `ValueError` when the kind cannot be built from a config.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_plot_panel_add.py`:

```python
"""panel.add(kind, **config): one call builds any plot kind, the same path templates and plugins use (spec §5)."""
import pytest

from SciQLop.core.extensions import NotRegistered, owned_by
from SciQLop.core.plot_kinds import PLOT_KINDS, PlotKind


@pytest.fixture
def panel(qtbot, main_window):
    from SciQLop.user_api.plot import create_plot_panel
    return create_plot_panel()


def test_add_builds_a_plugin_plot_kind_from_its_config(panel):
    got = []
    with owned_by("pa_demo"):
        PLOT_KINDS.contribute(PlotKind("pa_demo.slice_plot", "Slice", plot_product=lambda *a: None,
                                       from_config=lambda p, config: got.append(config) or "slice"))
    try:
        assert panel.add("pa_demo.slice_plot", plane="XY") == "slice"
        assert got == [{"plane": "XY"}]
    finally:
        PLOT_KINDS.remove_owner("pa_demo")


def test_add_unknown_kind_names_the_available_ones(panel):
    with pytest.raises(NotRegistered, match="sciqlop.timeseries"):
        panel.add("pa_nowhere.plot")


def test_add_kind_without_from_config_is_a_value_error(panel):
    with owned_by("pa_demo"):
        PLOT_KINDS.contribute(PlotKind("pa_demo.view_only", "View", plot_product=lambda *a: None))
    try:
        with pytest.raises(ValueError, match="pa_demo.view_only"):
            panel.add("pa_demo.view_only")
    finally:
        PLOT_KINDS.remove_owner("pa_demo")


def test_add_time_series_from_products(panel):
    from SciQLop.user_api.plot import TimeSeriesPlot
    plot = panel.add("sciqlop.timeseries", products=[])
    assert plot is None or isinstance(plot, TimeSeriesPlot)
```

Before writing these, check how tests get a user_api `PlotPanel`: `grep -rn "create_plot_panel\|def main_window" tests/fixtures.py tests/conftest.py`. Use the existing fixture and helper, and adapt the `panel` fixture to what you find.

- [ ] **Step 2: Run them and see them fail**

Run: `uv run --no-sync pytest tests/test_plot_panel_add.py -q -p no:cacheprovider`
Expected: FAIL with `AttributeError: 'PlotPanel' object has no attribute 'add'`.

- [ ] **Step 3: Implement**

In `PlotPanel` (`user_api/plot/_panel.py`), next to `plot_scene`:

```python
    @on_main_thread
    def add(self, kind: str, **config):
        """Add a plot of a registered plot kind, built from its config — the same path templates and plugins use.

        ``panel.add("sciqlop.scenes.projection", scene="earth_gsm", trajectories=["MMS1"])``,
        ``panel.add("vdf.slice_plot", product="vdf//mms1/dis", plane="XY")``. Returns what the plot kind builds
        (a TimeSeriesPlot, a ScenePlot, or the plugin's own object)."""
        from SciQLop.core.plot_kinds import PLOT_KINDS
        plot_kind = PLOT_KINDS.get(kind)
        if plot_kind.from_config is None:
            raise ValueError(f"plot kind {kind!r} cannot be built from a config")
        return plot_kind.from_config(self._get_impl_or_raise(), config)
```

`PLOT_KINDS.get` already raises `NotRegistered` listing the available ids (plan 1a).

Global memory: in `/home/jeandet/.claude/memory/sciqlop-user-api.md`, add `PlotPanel.add(kind, **config)` with the two examples above, in the PlotPanel section. Read the file first, and match its format.

Docs: in `references/ui-and-settings.md`, add one line: plugins and users build mixed panels with `panel.add(kind, **config)`.

- [ ] **Step 4: Run them and see them pass**

Run: `uv run --no-sync pytest tests/test_plot_panel_add.py tests/test_panel_tree.py -q -p no:cacheprovider`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/user_api/plot/_panel.py SciQLop/components/agents/skills/sciqlop-plugin-design/references/ui-and-settings.md tests/test_plot_panel_add.py
git commit -m "feat(user_api): PlotPanel.add(kind, **config) builds any registered plot kind"
```

---

### Task 6: Interop proof (spec §10) and plugin-author docs

**Files:**
- Create: `tests/test_plugin_panel_interop.py`
- Modify: `SciQLop/components/agents/skills/sciqlop-plugin-design/references/plugin-contract.md` and `SKILL.md`
- Modify: the spec's §4.3 status line

**Interfaces:**
- Consumes: everything from Tasks 1–5, plus `loader.activate_all(plugin_list, main_window, ep_plugins={})` and `context.STATES` (plan 1a).
- Produces: none (a test and docs).

- [ ] **Step 1: Write the test**

Create `tests/test_plugin_panel_interop.py`. Like plan 1b's interop test, it uses a local fixture that saves and restores `STATES`, `loader._attempted`, `loaded_plugins` and `_EXTENSION_POINTS`, and removes its owners from every extension point. Copy that fixture and the `_plugin` helper from `tests/test_plugin_interop.py`; don't import them from there.

There are two plugins:
- `pi_vdf` contributes:
  - `ProductKind("pi_vdf.distribution", "VDF", 0, "pi_vdf.slice_plot")`;
  - a `PlotKind("pi_vdf.slice_plot", ...)`, whose `from_config(panel, config)` creates one time-series plot (`panel.create_plot(len(panel.plots()), PlotType.TimeSeries)`) and records `config` in a module-level dict keyed by the plot's `objectName()`. Its `owns` and `to_config` read that dict, and its `plot_product(target, product, kwargs)` calls `from_config(<owning panel>, {"product": "//".join(product), "plane": "XY"})`;
  - a `DropRule("pi_vdf.drop", PRODUCT_LIST_MIME_TYPE, lambda plot, product, panel: <the same from_config call>, product_kind="pi_vdf.distribution", creates_plot=True)`.
  
  Its activate returns an `Api` with `SLICE = "pi_vdf.slice_plot"`.
- `pi_study` has `dependencies=["pi-vdf>=1"]`. Its activate stores `ctx.plugin("pi_vdf").SLICE` in a module global.

The test does this:
1. `activate_all` both plugins. Both must be `active`.
2. Add a product node `["pi_vdf_products", "dis"]` tagged `PRODUCT_KIND_KEY: "pi_vdf.distribution"`, with `add_product_node(..., ProductsModelNodeType.PARAMETER, ParameterType.Scalar)`.
3. Build a `TimeSyncPanel` and wrap it in user_api `PlotPanel`. As pi_study would, call `PlotPanel(panel).add(sys.modules["pi_study"].SLICE, product="pi_vdf_products//dis", plane="YZ")`.
4. Drop the product: call `SciQLop.components.plotting.drops.dispatch_drop(panel, None, PRODUCT_LIST_MIME_TYPE, [["pi_vdf_products", "dis"]])`. The panel now has two plugin plots.
5. `PanelTemplate.from_panel(panel).to_file(tmp/"study.yaml")`. Read the YAML back with `yaml.safe_load` and assert:
   - `panel.kind == "sciqlop.time_panel"`;
   - both plot nodes have kind `pi_vdf.slice_plot`;
   - their configs are `{"product": "pi_vdf_products//dis", "plane": "YZ"}` and `{"product": "pi_vdf_products//dis", "plane": "XY"}`.
6. Apply the file to a second panel. The plugin's dict now has two more entries with the same configs.
7. Remove the `pi_vdf` owner from every extension point (the plugin "is gone"). Apply the file to a third panel, then save that panel. The saved plot nodes are unchanged (the placeholders kept them), and the third panel has two plots.

- [ ] **Step 2: Run it**

Run: `uv run --no-sync pytest tests/test_plugin_panel_interop.py -q -p no:cacheprovider`
Expected: PASS. A failure is a real gap in an earlier task's code. Fix it minimally in that module and report it; don't weaken the test.

- [ ] **Step 3: Docs**

In `references/plugin-contract.md`, add a section "Plot kinds, drop rules and saved panels" covering:
- the `PlotKind` fields and their contracts:
  - `plot_product` returns `(plot, graph)` or None;
  - `from_config` returns the user-facing object;
  - `to_config` returns JSON-friendly values only;
- the `DropRule` fields and the weighting (product kind 2, target 1, ties by id);
- the v3 tree with a short YAML example;
- placeholders and the fact that unknown nodes survive re-saving;
- `panel.add(kind, **config)`;
- an example of under 25 lines: a plugin contributing a product kind, a plot kind and a drop rule.

Point to the `ui-and-settings.md` paragraphs instead of repeating them. In `SKILL.md`, add one line pointing to the section. In the spec's §4.3 status, mark 1c implemented and name this plan file.

- [ ] **Step 4: Run the skill-name test and the touched suites**

Run: `uv run --no-sync pytest tests/test_plugin_panel_interop.py tests/test_agent_skills.py -q -p no:cacheprovider`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_plugin_panel_interop.py SciQLop/components/agents/skills/sciqlop-plugin-design/references/plugin-contract.md SciQLop/components/agents/skills/sciqlop-plugin-design/SKILL.md docs/superpowers/specs/2026-10-14-plugin-extension-points-design.md
git commit -m "test(plugins): interop proof for plot kinds, drop rules and the panel tree; plugin-author docs"
```

Then the controller runs the full suite once and reads the real pass/fail count and exit code.

---

## Decisions this plan makes (each is a ruling; the spec stays the authority)

- **Templates keep their in-memory shape.** `PanelTemplate.plots: list[PlotModel]` stays, and each `PlotModel` gains `kind` and `config`; only the file becomes the spec's tree. Why: `user_api.templates`, the agents' `build_panel`, the proxy share and the snippets all read `template.plots`, and spec §7 forbids breaking published API. Cost if wrong: panel kinds with nested slots (tier 2) need a richer in-memory tree, so that model is extended then.
- **Older SciQLop versions cannot read v3 files**, and `list_templates` rewrites the user's v1 and v2 files as v3, as v1→v2 already did. Cost: a user who switches back to an older SciQLop, for example through the other A/B venv slot, loses their saved templates there.
- **Only `sciqlop.time_panel` is a valid root.** Other panel kinds are refused with the plugin's name. Panel kinds are tier 2 (spec §4.3, §11).
- **Placeholders name the plugin from the id prefix.** The app-store index does not carry `provides` yet; that needs the sciqlop-appstore generator. The "install it?" offer is a message, not a button. Cost: the user opens the App Store by hand.
- **Catalog-tree drops stay as they are.** Their target is a tree item, not a plot, so drop rules cover plot panels only. The trigger to revisit is a plugin that needs to accept drops on the catalog tree.
- **Only registered scenes and boundaries round-trip.** They are saved by name. An ad-hoc `Scene` object restores as a placeholder.
- **The time-series kind keeps the arity dispatch inside it** (line versus colour map). `GraphType` stays the rendering choice inside a plot kind (spec §4.2).
