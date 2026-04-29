# Annotation Layers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reactive annotation layer system — functions that produce visual overlays (markers, spans, horizontal lines) on existing plots, with knobs, product tree integration, DnD, and `%%layer` cell magic.

**Architecture:** Layers are registered via decorator or `%%layer` magic, appear in the product tree under a "Layers" folder, and are attached to existing plots via DnD or programmatic API. A `LayerRenderer` manages the lifecycle of C++ annotation items (VSpan, HLine, scatter graph) on a target plot, re-calling the user callback on time range or knob changes. The entire user-facing API is marked `@experimental_api()`.

**Tech Stack:** PySide6, SciQLopPlots (C++ bindings), IPython cell magic, existing knob introspection system.

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `SciQLop/user_api/layers/__init__.py` | Public API: `Marker`, `Span`, `HLine`, `register_layer` |
| Create | `SciQLop/user_api/layers/types.py` | Annotation dataclasses with metadata |
| Create | `SciQLop/user_api/layers/registry.py` | `LayerRegistry`, `MutableCallback` reuse, layer→product-tree registration |
| Create | `SciQLop/user_api/layers/magic.py` | `%%layer` cell magic |
| Create | `SciQLop/user_api/layers/_renderer.py` | Creates/destroys C++ items on a plot for each annotation type |
| Create | `SciQLop/user_api/layers/_provider.py` | `LayerProvider` — registers in product tree, stores callback + specs |
| Modify | `SciQLop/user_api/magics/__init__.py` | Register `%%layer` magic |
| Modify | `SciQLop/components/plotting/ui/time_sync_panel.py` | Extend `ProductDnDCallback` to handle layers |
| Modify | `SciQLop/user_api/plot/_panel.py` | Add `add_layer()` method |
| Modify | `SciQLop/user_api/plot/__init__.py` | Re-export layer types |
| Create | `tests/test_layers/__init__.py` | Test package |
| Create | `tests/test_layers/test_types.py` | Annotation dataclass tests |
| Create | `tests/test_layers/test_registry.py` | Registry + callback wrapping tests |
| Create | `tests/test_layers/test_renderer.py` | Renderer lifecycle tests (needs Qt) |
| Create | `tests/test_layers/test_magic.py` | Cell magic parsing + function extraction tests |

## Key Design Decisions

1. **Range-only callbacks** for v1: `callback(start, stop, **knobs) -> list[Marker|Span|HLine]`. Data-aware mode (receiving graph data) is a future extension.
2. **Return type from annotation**: `-> list[Marker]` tells the framework what renderer to use. Mixed lists (`list[Marker | Span]`) are supported — the renderer dispatches by item type.
3. **Product tree integration**: Layers appear under a "Layers/" folder using the same `ProductsModel.add_node()` API. The `ProductDnDCallback` checks `isinstance(provider, LayerProvider)` to dispatch correctly.
4. **Rendering**: Markers use a scatter graph via `plot.plot(x, y, graph_type=GraphType.Scatter)`. Spans use `SciQLopVerticalSpan`. HLines use `SciQLopHorizontalLine`. Old items are cleared before each update.
5. **Knobs**: Reuse the existing `extract_specs_from_callback` + `GraphKnobState` + ipywidgets binding entirely.

## Reference: C++ Primitive APIs

```python
# Vertical span (interval annotation)
from SciQLopPlots import SciQLopVerticalSpan, SciQLopPlotRange
span = SciQLopVerticalSpan(plot, SciQLopPlotRange(start, stop))
span.set_color(QColor(r, g, b, a))
span.set_read_only(True)
span.set_tool_tip("label")
span.deleteLater()  # cleanup

# Horizontal line
from SciQLopPlots import SciQLopHorizontalLine
hline = SciQLopHorizontalLine(plot, position_value)
hline.set_color(QColor(...))
hline.deleteLater()

# Scatter graph (for markers) — via plot.plot()
graph = plot.plot(x_array, y_array, graph_type=GraphType.Scatter, name="markers")
graph.set_data(new_x, new_y)  # update
```

---

### Task 1: Annotation Type Dataclasses

**Files:**
- Create: `SciQLop/user_api/layers/types.py`
- Create: `tests/test_layers/__init__.py`
- Create: `tests/test_layers/test_types.py`

- [ ] **Step 1: Write failing tests for Marker, Span, HLine**

```python
# tests/test_layers/test_types.py
from dataclasses import asdict

def test_marker_defaults():
    from SciQLop.user_api.layers.types import Marker
    m = Marker(time=1.0, value=2.0)
    assert m.time == 1.0
    assert m.value == 2.0
    assert m.label is None
    assert m.color is None
    assert m.meta == {}

def test_marker_with_metadata():
    from SciQLop.user_api.layers.types import Marker
    m = Marker(time=1.0, value=2.0, label="peak", color="#ff0000", meta={"confidence": 0.9})
    assert m.label == "peak"
    assert m.color == "#ff0000"
    assert m.meta["confidence"] == 0.9

def test_span_defaults():
    from SciQLop.user_api.layers.types import Span
    s = Span(start=1.0, stop=2.0)
    assert s.start == 1.0
    assert s.stop == 2.0
    assert s.label is None
    assert s.color is None
    assert s.meta == {}

def test_span_with_metadata():
    from SciQLop.user_api.layers.types import Span
    s = Span(start=1.0, stop=2.0, label="event", color="#00ff00", meta={"type": "dipolarization"})
    assert s.label == "event"

def test_hline_defaults():
    from SciQLop.user_api.layers.types import HLine
    h = HLine(value=3.14)
    assert h.value == 3.14
    assert h.label is None
    assert h.color is None

def test_hline_with_metadata():
    from SciQLop.user_api.layers.types import HLine
    h = HLine(value=0.0, label="zero crossing", color="#0000ff")
    assert h.label == "zero crossing"

def test_infer_annotation_type_markers():
    from SciQLop.user_api.layers.types import Marker, infer_annotation_type
    items = [Marker(time=1.0, value=2.0), Marker(time=3.0, value=4.0)]
    assert infer_annotation_type(items) == "marker"

def test_infer_annotation_type_spans():
    from SciQLop.user_api.layers.types import Span, infer_annotation_type
    items = [Span(start=1.0, stop=2.0)]
    assert infer_annotation_type(items) == "span"

def test_infer_annotation_type_hlines():
    from SciQLop.user_api.layers.types import HLine, infer_annotation_type
    items = [HLine(value=1.0)]
    assert infer_annotation_type(items) == "hline"

def test_infer_annotation_type_mixed():
    from SciQLop.user_api.layers.types import Marker, Span, infer_annotation_type
    items = [Marker(time=1.0, value=2.0), Span(start=1.0, stop=2.0)]
    assert infer_annotation_type(items) == "mixed"

def test_infer_annotation_type_empty():
    from SciQLop.user_api.layers.types import infer_annotation_type
    assert infer_annotation_type([]) is None

def test_infer_type_from_return_annotation():
    from SciQLop.user_api.layers.types import Marker, Span, HLine, infer_type_from_annotation
    import typing
    assert infer_type_from_annotation(list[Marker]) == "marker"
    assert infer_type_from_annotation(list[Span]) == "span"
    assert infer_type_from_annotation(list[HLine]) == "hline"
    assert infer_type_from_annotation(list[Marker | Span]) == "mixed"
    assert infer_type_from_annotation(None) is None
    assert infer_type_from_annotation(int) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_layers/test_types.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement annotation types**

```python
# SciQLop/user_api/layers/types.py
"""Annotation types for layer callbacks."""
from dataclasses import dataclass, field
from typing import Any, Optional, Union, get_args, get_origin


@dataclass(frozen=True)
class Marker:
    time: float
    value: float
    label: Optional[str] = None
    color: Optional[str] = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Span:
    start: float
    stop: float
    label: Optional[str] = None
    color: Optional[str] = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HLine:
    value: float
    label: Optional[str] = None
    color: Optional[str] = None
    meta: dict[str, Any] = field(default_factory=dict)


Annotation = Union[Marker, Span, HLine]

_TYPE_MAP = {Marker: "marker", Span: "span", HLine: "hline"}


def infer_annotation_type(items: list) -> Optional[str]:
    if not items:
        return None
    types = {type(item) for item in items}
    if len(types) == 1:
        return _TYPE_MAP.get(types.pop())
    return "mixed"


def infer_type_from_annotation(annotation) -> Optional[str]:
    if annotation is None:
        return None
    origin = get_origin(annotation)
    if origin is not list:
        return None
    args = get_args(annotation)
    if not args:
        return None
    inner = args[0]
    if inner in _TYPE_MAP:
        return _TYPE_MAP[inner]
    inner_origin = get_origin(inner)
    if inner_origin is Union:
        union_args = get_args(inner)
        mapped = {_TYPE_MAP.get(a) for a in union_args}
        mapped.discard(None)
        if len(mapped) > 1:
            return "mixed"
        if len(mapped) == 1:
            return mapped.pop()
    return None
```

Also create the empty `__init__.py`:

```python
# tests/test_layers/__init__.py
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_layers/test_types.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/user_api/layers/types.py tests/test_layers/__init__.py tests/test_layers/test_types.py
git commit -m "feat(layers): add Marker, Span, HLine annotation dataclasses

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: Layer Registry

**Files:**
- Create: `SciQLop/user_api/layers/registry.py`
- Create: `tests/test_layers/test_registry.py`

- [ ] **Step 1: Write failing tests for LayerRegistry**

```python
# tests/test_layers/test_registry.py
import numpy as np
import pytest
from SciQLop.user_api.layers.types import Marker


def _peaks_a(start: float, stop: float, threshold: float = 0.5):
    return [Marker(time=start + 100, value=1.0)]


def _peaks_b(start: float, stop: float, threshold: float = 0.5):
    return [Marker(time=start + 200, value=2.0)]


def _peaks_new_sig(start: float, stop: float, threshold: float = 0.5, window: int = 10):
    return [Marker(time=start + 100, value=1.0)]


class TestMutableCallback:
    def test_calls_wrapped(self):
        from SciQLop.user_api.layers.registry import MutableCallback
        w = MutableCallback(_peaks_a)
        result = w(0.0, 1000.0)
        assert len(result) == 1
        assert result[0].time == 100.0

    def test_swap_callback(self):
        from SciQLop.user_api.layers.registry import MutableCallback
        w = MutableCallback(_peaks_a)
        w.callback = _peaks_b
        result = w(0.0, 1000.0)
        assert result[0].time == 200.0


class TestLayerRegistry:
    def test_register_new(self):
        from SciQLop.user_api.layers.registry import LayerRegistry
        reg = LayerRegistry()
        entry = reg.register("find_peaks", _peaks_a)
        assert entry.wrapper(0.0, 1000.0)[0].time == 100.0
        assert entry.signature_changed is False

    def test_re_register_same_sig_swaps(self):
        from SciQLop.user_api.layers.registry import LayerRegistry
        reg = LayerRegistry()
        entry1 = reg.register("find_peaks", _peaks_a)
        wrapper1 = entry1.wrapper
        entry2 = reg.register("find_peaks", _peaks_b)
        assert entry2.wrapper is wrapper1
        assert entry2.signature_changed is False
        assert entry2.wrapper(0.0, 1000.0)[0].time == 200.0

    def test_re_register_different_sig_rebuilds(self):
        from SciQLop.user_api.layers.registry import LayerRegistry
        reg = LayerRegistry()
        entry1 = reg.register("find_peaks", _peaks_a)
        entry2 = reg.register("find_peaks", _peaks_new_sig)
        assert entry2.wrapper is not entry1.wrapper
        assert entry2.signature_changed is True

    def test_get_existing(self):
        from SciQLop.user_api.layers.registry import LayerRegistry
        reg = LayerRegistry()
        reg.register("find_peaks", _peaks_a)
        assert reg.get("find_peaks") is not None
        assert reg.get("nonexistent") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_layers/test_registry.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement LayerRegistry**

```python
# SciQLop/user_api/layers/registry.py
"""Layer lifecycle: MutableCallback wrapper and registry for hot-reload."""
import inspect
from dataclasses import dataclass
from typing import Callable, Dict, Optional


def _signature_kwargs(callback) -> tuple:
    sig = inspect.signature(callback)
    return tuple(
        (name, p.default.__class__)
        for name, p in sig.parameters.items()
        if p.default is not inspect.Parameter.empty and name not in ("start", "stop")
    )


class MutableCallback:
    def __init__(self, callback: Callable):
        self.callback = callback

    @property
    def callback(self):
        return self._callback

    @callback.setter
    def callback(self, value):
        self._callback = value
        import functools
        functools.update_wrapper(self, value)

    def __call__(self, start, stop, **kwargs):
        return self._callback(start, stop, **kwargs)


@dataclass
class LayerEntry:
    wrapper: MutableCallback
    signature_changed: bool = False


class LayerRegistry:
    def __init__(self):
        self._entries: Dict[str, LayerEntry] = {}

    def register(self, name: str, callback: Callable) -> LayerEntry:
        existing = self._entries.get(name)
        new_sig = _signature_kwargs(callback)
        if existing is not None:
            old_sig = _signature_kwargs(existing.wrapper.callback)
            if old_sig == new_sig:
                existing.wrapper.callback = callback
                existing.signature_changed = False
                return existing

        wrapper = MutableCallback(callback)
        entry = LayerEntry(wrapper=wrapper, signature_changed=existing is not None)
        self._entries[name] = entry
        return entry

    def get(self, name: str) -> Optional[LayerEntry]:
        return self._entries.get(name)


_registry = LayerRegistry()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_layers/test_registry.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/user_api/layers/registry.py tests/test_layers/test_registry.py
git commit -m "feat(layers): add LayerRegistry with hot-reload support

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Layer Provider (Product Tree Registration)

**Files:**
- Create: `SciQLop/user_api/layers/_provider.py`

This task has no pure-logic tests — it depends on the C++ ProductsModel. It will be tested via integration in Task 7.

- [ ] **Step 1: Implement LayerProvider**

```python
# SciQLop/user_api/layers/_provider.py
"""LayerProvider — registers annotation layers in the product tree."""
from typing import Callable, List, Optional

from SciQLop.core.unique_names import make_simple_incr_name
from SciQLop.core.models import products, ProductsModelNode, ProductsModelNodeType
from SciQLop.core.enums import ParameterType
from SciQLop.user_api.knobs import extract_specs_from_callback
from SciQLop.user_api.layers.types import infer_type_from_annotation
from SciQLop.components import sciqlop_logging

log = sciqlop_logging.getLogger(__name__)

_LAYERS_ROOT = "Layers"

_layer_providers: dict[str, "LayerProvider"] = {}


class LayerProvider:
    def __init__(self, path: str, callback: Callable, annotation_type: Optional[str] = None):
        self.name = make_simple_incr_name(getattr(callback, "__name__", "layer"))
        self._path = f"{_LAYERS_ROOT}/{path}".split("/")
        self._callback = callback
        self._knob_specs = extract_specs_from_callback(callback)
        self.annotation_type = annotation_type or self._infer_type()

        product_name = self._path[-1]
        product_path = self._path[:-1]
        metadata = {
            "description": f"Annotation layer: {self.name}",
            "stable_id": f"{_LAYERS_ROOT}/{path}",
            "sciqlop_layer": "true",
        }
        products.add_node(
            product_path,
            ProductsModelNode(product_name, self.name, metadata,
                              ProductsModelNodeType.PARAMETER,
                              ParameterType.Scalar, "", None),
        )
        _layer_providers[self.name] = self

    def _infer_type(self) -> str:
        ann = self._callback.__annotations__.get("return")
        return infer_type_from_annotation(ann) or "mixed"

    def get_knobs(self) -> list:
        return list(self._knob_specs)

    def refresh_knob_specs(self):
        self._knob_specs = extract_specs_from_callback(self._callback)

    @property
    def callback(self):
        return self._callback

    @property
    def path(self):
        return self._path
```

- [ ] **Step 2: Commit**

```bash
git add SciQLop/user_api/layers/_provider.py
git commit -m "feat(layers): add LayerProvider for product tree registration

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 4: Layer Renderer

**Files:**
- Create: `SciQLop/user_api/layers/_renderer.py`
- Create: `tests/test_layers/test_renderer.py`

- [ ] **Step 1: Write failing tests for renderer partitioning logic**

The renderer's `_partition` function splits a mixed list into typed groups. This is pure logic we can test without Qt.

```python
# tests/test_layers/test_renderer.py
from SciQLop.user_api.layers.types import Marker, Span, HLine


def test_partition_markers_only():
    from SciQLop.user_api.layers._renderer import _partition
    items = [Marker(time=1.0, value=2.0), Marker(time=3.0, value=4.0)]
    groups = _partition(items)
    assert len(groups["marker"]) == 2
    assert len(groups["span"]) == 0
    assert len(groups["hline"]) == 0


def test_partition_mixed():
    from SciQLop.user_api.layers._renderer import _partition
    items = [Marker(time=1.0, value=2.0), Span(start=1.0, stop=2.0), HLine(value=3.0)]
    groups = _partition(items)
    assert len(groups["marker"]) == 1
    assert len(groups["span"]) == 1
    assert len(groups["hline"]) == 1


def test_partition_empty():
    from SciQLop.user_api.layers._renderer import _partition
    groups = _partition([])
    assert len(groups["marker"]) == 0
    assert len(groups["span"]) == 0
    assert len(groups["hline"]) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_layers/test_renderer.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement LayerRenderer**

```python
# SciQLop/user_api/layers/_renderer.py
"""Manages C++ annotation items on a SciQLopPlot for a single layer."""
import numpy as np
from typing import Optional
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor

from SciQLop.user_api.layers.types import Marker, Span, HLine, Annotation
from SciQLop.components import sciqlop_logging

log = sciqlop_logging.getLogger(__name__)

_DEFAULT_SPAN_ALPHA = 60
_DEFAULT_MARKER_COLOR = "#e74c3c"
_DEFAULT_SPAN_COLOR = "#3498db"
_DEFAULT_HLINE_COLOR = "#2ecc71"


def _partition(items: list[Annotation]) -> dict[str, list]:
    groups: dict[str, list] = {"marker": [], "span": [], "hline": []}
    for item in items:
        if isinstance(item, Marker):
            groups["marker"].append(item)
        elif isinstance(item, Span):
            groups["span"].append(item)
        elif isinstance(item, HLine):
            groups["hline"].append(item)
    return groups


def _parse_color(color_str: Optional[str], default: str, alpha: int = 255) -> QColor:
    c = QColor(color_str or default)
    if alpha < 255:
        c.setAlpha(alpha)
    return c


class LayerRenderer(QObject):
    """Renders annotation items on a target plot and refreshes on time-range/knob changes."""

    update_requested = Signal()

    def __init__(self, plot, callback, knob_state=None, parent=None):
        super().__init__(parent or plot)
        self._plot = plot
        self._callback = callback
        self._knob_state = knob_state
        self._spans: list = []
        self._hlines: list = []
        self._marker_graph = None

    def update(self, start: float, stop: float):
        knobs = self._knob_state.values if self._knob_state is not None else {}
        try:
            items = self._callback(start, stop, **knobs)
        except Exception:
            log.error("layer callback failed", exc_info=True)
            items = []
        self._render(items or [])

    def _render(self, items: list[Annotation]):
        groups = _partition(items)
        self._render_spans(groups["span"])
        self._render_hlines(groups["hline"])
        self._render_markers(groups["marker"])

    def _render_spans(self, spans: list[Span]):
        for old in self._spans:
            old.deleteLater()
        self._spans.clear()
        from SciQLopPlots import SciQLopVerticalSpan, SciQLopPlotRange
        for s in spans:
            vs = SciQLopVerticalSpan(self._plot, SciQLopPlotRange(s.start, s.stop))
            vs.set_color(_parse_color(s.color, _DEFAULT_SPAN_COLOR, _DEFAULT_SPAN_ALPHA))
            vs.set_read_only(True)
            if s.label:
                vs.set_tool_tip(s.label)
            self._spans.append(vs)

    def _render_hlines(self, hlines: list[HLine]):
        for old in self._hlines:
            old.deleteLater()
        self._hlines.clear()
        from SciQLopPlots import SciQLopHorizontalLine
        for h in hlines:
            hl = SciQLopHorizontalLine(self._plot, h.value)
            hl.set_color(_parse_color(h.color, _DEFAULT_HLINE_COLOR))
            self._hlines.append(hl)

    def _render_markers(self, markers: list[Marker]):
        if not markers:
            if self._marker_graph is not None:
                self._marker_graph.set_data(
                    np.empty(0, dtype=np.float64),
                    np.empty(0, dtype=np.float64),
                )
            return
        times = np.array([m.time for m in markers], dtype=np.float64)
        values = np.array([m.value for m in markers], dtype=np.float64)
        if self._marker_graph is None:
            self._marker_graph = self._create_marker_graph()
        if self._marker_graph is not None:
            self._marker_graph.set_data(times, values)

    def _create_marker_graph(self):
        from SciQLopPlots import GraphType
        try:
            return self._plot.plot(
                np.empty(0, dtype=np.float64),
                np.empty(0, dtype=np.float64),
                graph_type=GraphType.Scatter,
                name="layer_markers",
            )
        except Exception:
            log.warning("scatter graph creation failed, falling back to line graph")
            try:
                return self._plot.plot(
                    np.empty(0, dtype=np.float64),
                    np.empty(0, dtype=np.float64),
                    name="layer_markers",
                )
            except Exception:
                log.error("marker graph creation failed entirely", exc_info=True)
                return None

    def clear(self):
        for s in self._spans:
            s.deleteLater()
        self._spans.clear()
        for h in self._hlines:
            h.deleteLater()
        self._hlines.clear()
        if self._marker_graph is not None:
            self._marker_graph.set_data(
                np.empty(0, dtype=np.float64),
                np.empty(0, dtype=np.float64),
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_layers/test_renderer.py -v`
Expected: all PASS (the `_partition` tests are pure logic)

- [ ] **Step 5: Commit**

```bash
git add SciQLop/user_api/layers/_renderer.py tests/test_layers/test_renderer.py
git commit -m "feat(layers): add LayerRenderer for managing C++ annotation items

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 5: DnD Integration and `attach_layer`

**Files:**
- Modify: `SciQLop/components/plotting/ui/time_sync_panel.py`

- [ ] **Step 1: Add `attach_layer` function and update ProductDnDCallback**

In `time_sync_panel.py`, add the layer attachment function and modify the DnD handler to recognize layers.

Add these imports at the top of the file:

```python
from SciQLop.user_api.layers._provider import _layer_providers
```

Add `attach_layer` function (after `plot_function`):

```python
def attach_layer(plot, product: list[str]):
    """Attach an annotation layer to an existing plot."""
    from SciQLop.user_api.layers._provider import _layer_providers
    from SciQLop.user_api.layers._renderer import LayerRenderer
    from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
    from SciQLop.components.plotting.ui.knob_inspector import KnobInspectorExtension

    node = ProductsModel.node(product)
    if node is None:
        return None
    provider = _layer_providers.get(node.provider())
    if provider is None:
        return None

    renderer = LayerRenderer(plot, provider.callback, parent=plot)

    specs = provider.get_knobs()
    if specs:
        state = GraphKnobState(specs, parent=renderer)
        renderer._knob_state = state
        state.knobs_changed.connect(lambda *_: _trigger_layer_update(renderer, plot))
        if hasattr(plot, "add_inspector_extension"):
            ext = KnobInspectorExtension(state, parent=renderer)
            renderer._knob_inspector_ext = ext
            plot.add_inspector_extension(ext)

    def _on_range_changed(new_range):
        renderer.update(new_range.start(), new_range.stop())

    plot.x_axis().range_changed.connect(_on_range_changed)

    if not hasattr(plot, "_layer_renderers"):
        plot._layer_renderers = []
    plot._layer_renderers.append(renderer)

    try:
        current_range = plot.x_axis().range()
        renderer.update(current_range.start(), current_range.stop())
    except Exception:
        log.debug("initial layer render skipped — no valid range yet")

    return renderer


def _trigger_layer_update(renderer, plot):
    from SciQLop.user_api.threading import on_main_thread

    @on_main_thread
    def _do():
        try:
            current_range = plot.x_axis().range()
            renderer.update(current_range.start(), current_range.stop())
        except Exception:
            log.debug("layer knob-triggered update failed", exc_info=True)

    _do()
```

Modify `ProductDnDCallback.call` to dispatch layers:

```python
class ProductDnDCallback(PlotDragNDropCallback):
    def __init__(self, parent):
        super().__init__(PRODUCT_LIST_MIME_TYPE, True, parent)

    def call(self, plot, mime_data: QMimeData):
        log.debug(f"ProductDnDCallback: {mime_data}")
        for product in decode_mime(mime_data):
            log.debug(f"ProductDnDCallback: {product}")
            node = ProductsModel.node(product)
            if node is not None:
                log.debug(f"ProductDnDCallback: {node}")
                if node.metadata().get("sciqlop_layer") == "true":
                    attach_layer(plot, product)
                else:
                    plot_product(plot, product)
```

- [ ] **Step 2: Commit**

```bash
git add SciQLop/components/plotting/ui/time_sync_panel.py
git commit -m "feat(layers): integrate layer DnD into ProductDnDCallback

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 6: Cell Magic (`%%layer`)

**Files:**
- Create: `SciQLop/user_api/layers/magic.py`
- Create: `tests/test_layers/test_magic.py`
- Modify: `SciQLop/user_api/magics/__init__.py`

- [ ] **Step 1: Write failing tests for magic helper functions**

```python
# tests/test_layers/test_magic.py
import ast
import pytest


def test_extract_function():
    from SciQLop.user_api.layers.magic import _extract_function
    code = """
def find_peaks(start: float, stop: float, threshold: float = 0.5):
    return []
"""
    ns = {}
    func = _extract_function(code, ns)
    assert func.__name__ == "find_peaks"
    assert func(0.0, 1.0) == []


def test_extract_function_no_def_raises():
    from SciQLop.user_api.layers.magic import _extract_function
    with pytest.raises(ValueError, match="No function"):
        _extract_function("x = 1", {})


def test_parse_args_empty():
    from SciQLop.user_api.layers.magic import _parse_args
    args = _parse_args("")
    assert args.path is None
    assert args.debug is False


def test_parse_args_with_path():
    from SciQLop.user_api.layers.magic import _parse_args
    args = _parse_args("--path detectors/peaks")
    assert args.path == "detectors/peaks"


def test_parse_args_debug():
    from SciQLop.user_api.layers.magic import _parse_args
    args = _parse_args("--debug")
    assert args.debug is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_layers/test_magic.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement `%%layer` magic**

```python
# SciQLop/user_api/layers/magic.py
"""%%layer cell magic — define and register annotation layers from notebook cells."""
import ast
from typing import Optional

from IPython.core.magic import needs_local_scope

from SciQLop.user_api.layers.registry import _registry
from SciQLop.user_api.layers.types import Marker, Span, HLine


def _parse_args(line: str):
    import argparse
    import shlex
    parser = argparse.ArgumentParser(prog="%%layer", add_help=False)
    parser.add_argument("--path", type=str, default=None)
    parser.add_argument("--debug", action="store_true", default=False)
    return parser.parse_args(shlex.split(line))


def _extract_function(cell: str, user_ns: dict) -> callable:
    exec(cell, user_ns)
    tree = ast.parse(cell)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            return user_ns[node.name]
    raise ValueError("No function definition found in cell")


def _inject_type_names(user_ns: dict):
    user_ns.setdefault("Marker", Marker)
    user_ns.setdefault("Span", Span)
    user_ns.setdefault("HLine", HLine)


def _get_log():
    from SciQLop.components import sciqlop_logging
    return sciqlop_logging.getLogger(__name__)


def _invoke_on_main_thread(func, *args, **kwargs):
    from SciQLop.user_api.threading import invoke_on_main_thread
    return invoke_on_main_thread(func, *args, **kwargs)


def _register_layer_provider(name, wrapper, path):
    from SciQLop.user_api.layers._provider import LayerProvider, _layer_providers
    existing = _layer_providers.get(name)
    if existing is not None:
        existing._callback = wrapper
        existing.refresh_knob_specs()
        return existing

    def _do():
        return LayerProvider(path, wrapper)

    return _invoke_on_main_thread(_do)


@needs_local_scope
def layer_magic(line: str, cell: str, local_ns=None):
    """%%layer cell magic — define an annotation layer from a function in the cell."""
    user_ns = local_ns if local_ns is not None else {}
    _inject_type_names(user_ns)

    args = _parse_args(line)
    func = _extract_function(cell, user_ns)
    func_name = func.__name__

    entry = _registry.register(func_name, func)

    layer_path = args.path or func_name
    _register_layer_provider(func_name, entry.wrapper, layer_path)

    _get_log().info(f"Layer '{func_name}' registered — drag from product tree onto a plot")

    if args.debug:
        try:
            from SciQLop.user_api.knobs import extract_specs_from_callback
            from SciQLop.user_api.virtual_products.ipywidgets_binding import display_widgets_for_state
            from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
            from IPython.display import display

            specs = extract_specs_from_callback(func)
            if specs:
                state = GraphKnobState(specs)
                box = display_widgets_for_state(state)
                if box is not None:
                    display(box)
        except Exception:
            _get_log().warning("ipywidgets binding failed", exc_info=True)

    return func, args
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_layers/test_magic.py -v`
Expected: all PASS

- [ ] **Step 5: Register the magic in the magics module**

Modify `SciQLop/user_api/magics/__init__.py` — add two lines:

After `from SciQLop.user_api.virtual_products.magic import vp_magic` add:
```python
    from SciQLop.user_api.layers.magic import layer_magic
```

After `shell.register_magic_function(vp_magic, magic_kind="cell", magic_name="vp")` add:
```python
    shell.register_magic_function(layer_magic, magic_kind="cell", magic_name="layer")
```

- [ ] **Step 6: Commit**

```bash
git add SciQLop/user_api/layers/magic.py tests/test_layers/test_magic.py SciQLop/user_api/magics/__init__.py
git commit -m "feat(layers): add %%layer cell magic and register in IPython

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 7: Public API and PlotPanel Integration

**Files:**
- Create: `SciQLop/user_api/layers/__init__.py`
- Modify: `SciQLop/user_api/plot/_panel.py`
- Modify: `SciQLop/user_api/plot/__init__.py`

- [ ] **Step 1: Create the layers package `__init__.py`**

```python
# SciQLop/user_api/layers/__init__.py
"""Annotation layers — experimental API for reactive visual overlays on plots.

Layers are functions that return lists of annotations (Marker, Span, HLine)
and are rendered as visual overlays on existing plots. They react to time-range
changes and support tunable knobs.

.. warning::
    This is an experimental API. It may change or be removed in future versions.
"""
from SciQLop.user_api._annotations import experimental_api
from SciQLop.user_api.layers.types import Marker, Span, HLine, Annotation
from SciQLop.user_api.layers.registry import _registry

__all__ = ["Marker", "Span", "HLine", "Annotation", "register_layer"]


@experimental_api()
def register_layer(path: str = None):
    """Decorator to register a function as an annotation layer.

    The decorated function appears in the product tree under Layers/ and
    can be dragged onto any plot.

    Parameters
    ----------
    path : str, optional
        Path in the product tree (under Layers/). Defaults to the function name.

    Example
    -------
    ::

        @register_layer("detectors/peaks")
        def find_peaks(start: float, stop: float, threshold: float = 0.5) -> list[Marker]:
            ...
    """
    def decorator(func):
        name = func.__name__
        entry = _registry.register(name, func)
        layer_path = path or name

        from SciQLop.user_api.layers._provider import _layer_providers
        if name not in _layer_providers:
            from SciQLop.user_api.threading import invoke_on_main_thread
            from SciQLop.user_api.layers._provider import LayerProvider
            invoke_on_main_thread(lambda: LayerProvider(layer_path, entry.wrapper))

        return func
    return decorator
```

- [ ] **Step 2: Add `add_layer` method to PlotPanel**

In `SciQLop/user_api/plot/_panel.py`, add this method to the `PlotPanel` class (after `histogram2d`):

```python
    @experimental_api()
    @on_main_thread
    def add_layer(self, func, plot_index: int = 0, **initial_knobs):
        """Attach an annotation layer to an existing plot in this panel.

        Parameters
        ----------
        func : callable
            A function ``f(start, stop, **knobs) -> list[Marker|Span|HLine]``.
        plot_index : int
            Index of the subplot to attach the layer to. Defaults to 0 (first plot).
        **initial_knobs
            Initial values for the layer's knob parameters.

        Returns
        -------
        LayerRenderer
            The renderer managing the layer's visual items.
        """
        from SciQLop.user_api.layers._renderer import LayerRenderer
        from SciQLop.user_api.knobs import extract_specs_from_callback
        from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
        from SciQLop.components.plotting.ui.knob_inspector import KnobInspectorExtension
        from SciQLop.components.plotting.ui.time_sync_panel import _trigger_layer_update

        impl = self._get_impl_or_raise()
        plots = impl.plots()
        if not plots or plot_index >= len(plots):
            raise IndexError(f"No plot at index {plot_index}")

        from SciQLopPlots import SciQLopPlot
        target = plots[plot_index]
        name = target.objectName()
        for child in impl.findChildren(SciQLopPlot):
            if child.objectName() == name:
                target = child
                break

        renderer = LayerRenderer(target, func, parent=target)

        specs = extract_specs_from_callback(func)
        if specs:
            state = GraphKnobState(specs, parent=renderer)
            renderer._knob_state = state
            if initial_knobs:
                state.set_all(initial_knobs)
            state.knobs_changed.connect(lambda *_: _trigger_layer_update(renderer, target))
            if hasattr(target, "add_inspector_extension"):
                ext = KnobInspectorExtension(state, parent=renderer)
                renderer._knob_inspector_ext = ext
                target.add_inspector_extension(ext)

        def _on_range_changed(new_range):
            renderer.update(new_range.start(), new_range.stop())

        target.x_axis().range_changed.connect(_on_range_changed)

        if not hasattr(target, "_layer_renderers"):
            target._layer_renderers = []
        target._layer_renderers.append(renderer)

        try:
            current_range = target.x_axis().range()
            renderer.update(current_range.start(), current_range.stop())
        except Exception:
            pass

        return renderer
```

Add the import at the top of `_panel.py`:

```python
from .._annotations import experimental_api
```

(This import already exists — verify and skip if so.)

- [ ] **Step 3: Re-export layer types from plot package**

In `SciQLop/user_api/plot/__init__.py`, add to the imports:

```python
from SciQLop.user_api.layers import Marker, Span, HLine
```

And add `'Marker', 'Span', 'HLine'` to the `__all__` list.

- [ ] **Step 4: Commit**

```bash
git add SciQLop/user_api/layers/__init__.py SciQLop/user_api/plot/_panel.py SciQLop/user_api/plot/__init__.py
git commit -m "feat(layers): public API with register_layer decorator and PlotPanel.add_layer

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 8: Fluent API Integration

**Files:**
- Modify: `SciQLop/user_api/plot/_fluent.py`

- [ ] **Step 1: Add `layer` method to PanelBuilder**

In `SciQLop/user_api/plot/_fluent.py`, add after the `histogram2d` method:

```python
    def layer(self, func, **kwargs) -> PanelBuilder:
        """Attach an annotation layer to the current subplot.

        The layer callback ``f(start, stop, **knobs) -> list[Marker|Span|HLine]``
        is called on time-range changes and renders annotations on the subplot.
        """
        if self._current_plot is None:
            raise RuntimeError("No plot yet — call .plot() first to create a subplot")
        self._panel.add_layer(func, plot_index=self._current_plot_index, **kwargs)
        return self
```

- [ ] **Step 2: Commit**

```bash
git add SciQLop/user_api/plot/_fluent.py
git commit -m "feat(layers): add .layer() to fluent PanelBuilder API

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 9: Integration Tests

**Files:**
- Create: `tests/test_layers/test_integration.py`

These tests verify the end-to-end flow without a running app, testing the pure-logic paths of registration and callback invocation.

- [ ] **Step 1: Write integration tests**

```python
# tests/test_layers/test_integration.py
"""Integration tests for the layer system (pure logic, no Qt)."""
import pytest
from SciQLop.user_api.layers.types import Marker, Span, HLine
from SciQLop.user_api.layers.registry import LayerRegistry


def test_register_and_invoke_marker_layer():
    reg = LayerRegistry()

    def find_peaks(start: float, stop: float, threshold: float = 0.5) -> list[Marker]:
        mid = (start + stop) / 2
        return [Marker(time=mid, value=threshold)]

    entry = reg.register("find_peaks", find_peaks)
    result = entry.wrapper(0.0, 100.0)
    assert len(result) == 1
    assert isinstance(result[0], Marker)
    assert result[0].time == 50.0

    result_with_knob = entry.wrapper(0.0, 100.0, threshold=0.8)
    assert result_with_knob[0].value == 0.8


def test_register_and_invoke_span_layer():
    reg = LayerRegistry()

    def detect_regions(start: float, stop: float, min_duration: float = 10.0) -> list[Span]:
        return [Span(start=start + 5, stop=start + 5 + min_duration, label="region")]

    entry = reg.register("detect_regions", detect_regions)
    result = entry.wrapper(0.0, 100.0)
    assert len(result) == 1
    assert isinstance(result[0], Span)
    assert result[0].label == "region"


def test_register_and_invoke_hline_layer():
    reg = LayerRegistry()

    def thresholds(start: float, stop: float, level: float = 1.0) -> list[HLine]:
        return [HLine(value=level, label="threshold"), HLine(value=-level)]

    entry = reg.register("thresholds", thresholds)
    result = entry.wrapper(0.0, 100.0)
    assert len(result) == 2
    assert all(isinstance(h, HLine) for h in result)


def test_register_mixed_return():
    reg = LayerRegistry()

    def annotate(start: float, stop: float) -> list[Marker | Span]:
        return [
            Marker(time=start + 10, value=1.0),
            Span(start=start + 20, stop=start + 30),
        ]

    entry = reg.register("annotate", annotate)
    result = entry.wrapper(0.0, 100.0)
    assert isinstance(result[0], Marker)
    assert isinstance(result[1], Span)


def test_hot_reload_preserves_wrapper():
    reg = LayerRegistry()

    def v1(start: float, stop: float, threshold: float = 0.5) -> list[Marker]:
        return [Marker(time=0.0, value=1.0)]

    def v2(start: float, stop: float, threshold: float = 0.5) -> list[Marker]:
        return [Marker(time=0.0, value=2.0)]

    entry1 = reg.register("func", v1)
    entry2 = reg.register("func", v2)
    assert entry2.wrapper is entry1.wrapper
    assert entry2.wrapper(0.0, 1.0)[0].value == 2.0


def test_knob_introspection():
    from SciQLop.user_api.knobs import extract_specs_from_callback

    def find_peaks(start: float, stop: float, threshold: float = 0.5, window: int = 10) -> list[Marker]:
        return []

    specs = extract_specs_from_callback(find_peaks)
    names = {s.name for s in specs}
    assert "threshold" in names
    assert "window" in names
    assert "start" not in names
    assert "stop" not in names
```

- [ ] **Step 2: Run all layer tests**

Run: `uv run pytest tests/test_layers/ -v`
Expected: all PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_layers/test_integration.py
git commit -m "test(layers): add integration tests for layer registration and invocation

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 10: Run Full Test Suite

- [ ] **Step 1: Run the full test suite to check for regressions**

Run: `uv run pytest --no-xvfb -x -v`

Expected: no regressions. Any existing test failures should be pre-existing.

- [ ] **Step 2: Fix any regressions if needed**

If tests fail due to import cycles or missing `__init__.py`, fix them. Common issues:
- The `layers/__init__.py` imports `_provider.py` which imports Qt — ensure the import is lazy (inside the `register_layer` decorator body, not at module level).
- The `_renderer.py` imports `SciQLopPlots` — ensure imports are inside methods, not at module level.

---

## Summary of Public API (all `@experimental_api()`)

```python
# Annotation types
from SciQLop.user_api.layers import Marker, Span, HLine

# Decorator registration
from SciQLop.user_api.layers import register_layer

@register_layer("detectors/peaks")
def find_peaks(start: float, stop: float, threshold: float = 0.5) -> list[Marker]:
    ...

# Programmatic attachment
panel.add_layer(find_peaks, plot_index=0)

# Fluent API
fluent.new_panel().plot("speasy//amda//b_gse").layer(find_peaks)

# Cell magic
# %%layer --path detectors/peaks
# def find_peaks(start: float, stop: float, threshold: float = 0.5) -> list[Marker]:
#     ...
```
