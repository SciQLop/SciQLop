# Colour-axis virtual products (SciQLop side) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A virtual product can return `Colored(data, color=c)`, and SciQLop draws it as a line graph or projection curve coloured by `c`.

**Architecture:** `Colored` (user API) is unwrapped once, in `DataProvider._get_data`, into a per-batch dict `{"data": [t, values], "color": c}`. SciQLopPlots (Part 1 of the spec, built by another session) turns that dict into its `new_data_colored` signal. The provider carries a `ColorAxis` (label and gradient) that `plot_product` applies to the graph at plot time.

**Tech Stack:** Python 3.13+, PySide6, SciQLopPlots (Shiboken bindings), speasy, numpy, pytest-qt.

**Spec:** `docs/superpowers/specs/2026-09-24-colour-axis-virtual-products-design.md`. Read it before any task, especially "Principle" and "Rejected alternatives".

**Deliberate deviation from the spec:** Part 2 says `wrap_graph_data` should keep a coloured result's colour. It doesn't need to. `wrap_graph_data` wraps `graph.data()` output for layers, and SciQLopPlots never returns the colour there, so there is nothing to keep. It is dropped from this plan. Add it when `graph.data()` returns colour.

## Global Constraints

- Run everything through `uv run` (`uv run pytest --no-xvfb ...`). Never `uv sync`.
- Only ONE pytest invocation at a time, in the foreground. Never background a test run, never overlap two.
- Never rebuild or edit SciQLopPlots from this plan. Tasks 7 and 8 need the SciQLopPlots build that contains Part 1; the user installs it. If `SciQLopPlots.SciQLopLineGraph` has no `set_color_gradient`, stop at Task 7 and report.
- `user_api/` is published: add keyword arguments with defaults only; never change an existing signature.
- Part 1 API names this plan depends on (from the spec): callback result dict `{"data": [...], "color": c}`; remote pipeline `set_data_colored(data: list, color)`; `SciQLopLineGraph.set_color_gradient(gradient)`; `SciQLopNDProjectionCurves.set_color_gradient(gradient)` (exists today). If Part 1's report (`/tmp/claude-6516/-home-jeandet-Documents-prog-SciQLop/03e47c22-c742-4cc2-a894-6702e1db8733/scratchpad/sciqlopplots-part1-report.md`) names them differently, use Part 1's names.
- Commit after each task with explicit pathspecs (the tree has unrelated untracked files). End commit messages with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`. Never push.
- Code style: small functions, no comment-labelled blocks, comments only for non-obvious "why".

## Review Focus

1. **Unsorted time.** A `Colored` whose time is not sorted: SciQLop sorts the data, and the colour must be permuted with it, or colours land on the wrong points. Test in Task 2.
2. **Colour length ≠ sample count, outside debug mode.** Expect one logged error and no data for that batch, not a crash and not a partly-coloured plot. Test in Task 2.
3. **Coloured/uncoloured mismatch.** A VP declared coloured returning plain data, or a plain VP returning `Colored`: expect a logged error naming the VP, and no data. It must not silently return nothing. Test in Task 2.
4. **Colour dtypes.** Colour given as `(N, 1)`, as int, or as datetime64 (colour by time): expect it to work, converted to float64 (datetime64 becomes epoch seconds). Test in Task 2.
5. **Hot reload from uncoloured to coloured in `%%vp`.** Same name and signature, but now `-> Colored[...]`: the VP must be re-registered as coloured, not hot-swapped as plain. Test in Task 5.

---

## File structure

- Modify `SciQLop/user_api/data_types.py`: `Colored` container, `Colored[...]` annotation marker, `VPTypeInfo.colored`.
- Create `SciQLop/components/plotting/backend/color_axis.py`: `ColorAxis`, `as_color_values`, `sort_colored`, `apply_color_axis`. One module for everything about colour on the backend side.
- Modify `SciQLop/components/plotting/backend/data_provider.py`: `color_axis()` default; `_get_data` handles `Colored`.
- Modify `SciQLop/components/plotting/backend/easy_provider.py`: `color_axis` parameter; `get_data` dispatch into `_to_variable` + `_checked_colored`.
- Modify `SciQLop/user_api/virtual_products/__init__.py`: `colored`, `color_label`, `color_gradient` keyword arguments.
- Modify `SciQLop/user_api/virtual_products/validation.py` and `debug.py`: unwrap `Colored`.
- Modify `SciQLop/user_api/virtual_products/magic.py` and `registry.py`: `Colored` injection, inference, and registry identity.
- Modify `SciQLop/components/plotting/ui/time_sync_panel.py`: dict-aware projection reshape; apply the colour axis in `plot_product`.
- Modify `SciQLop/components/plotting/backend/remote/{registry,reduction,channel,plot_remote}.py`: out-of-process colour.
- Tests: `tests/test_colored_vp_types.py`, `tests/test_virtual_products/test_colored_easy_provider.py`, `tests/test_colored_vp_validation.py`, `tests/test_colored_vp_magic.py`, `tests/test_projection_product_shape.py` (extend), `tests/test_colored_vp_plot.py`, `tests/remote/test_colored_remote.py`.

---

### Task 1: `Colored` type and annotation

**Files:**
- Modify: `SciQLop/user_api/data_types.py`
- Test: `tests/test_colored_vp_types.py`

**Interfaces:**
- Produces: `Colored(data, color)`, a frozen dataclass with fields `data` and `color`. `Colored[X]` returns `_ColoredAnnotation(inner=X)`. `VPTypeInfo(product_type, labels, colored=False)`. `extract_vp_type_info(Colored[Vector["a","b","c"]])` returns `VPTypeInfo("vector", ["a","b","c"], colored=True)`. `Colored[Spectrogram]` raises `TypeError`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_colored_vp_types.py
import numpy as np
import pytest

from SciQLop.user_api.data_types import (
    Colored, Scalar, Vector, MultiComponent, Spectrogram, VPTypeInfo, extract_vp_type_info,
)


def test_colored_vector_annotation_keeps_labels_and_is_colored():
    info = extract_vp_type_info(Colored[Vector["X", "Y", "Z"]])
    assert info == VPTypeInfo(product_type="vector", labels=["X", "Y", "Z"], colored=True)


def test_colored_bare_type_annotation():
    assert extract_vp_type_info(Colored[Scalar]) == VPTypeInfo("scalar", None, colored=True)
    assert extract_vp_type_info(Colored[MultiComponent]).colored is True


def test_plain_annotation_is_not_colored():
    assert extract_vp_type_info(Vector).colored is False


def test_colored_spectrogram_is_rejected():
    with pytest.raises(TypeError, match="Spectrogram"):
        Colored[Spectrogram]


def test_colored_holds_data_and_color():
    t = np.arange(3.0)
    c = Colored((t, t), color=t)
    assert c.data[0] is t and c.color is t
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest --no-xvfb tests/test_colored_vp_types.py -v`
Expected: FAIL with `ImportError: cannot import name 'Colored'`.

- [ ] **Step 3: Implement**

In `SciQLop/user_api/data_types.py`, change `VPTypeInfo` and add the new types after `Spectrogram`:

```python
@dataclass(frozen=True)
class VPTypeInfo:
    product_type: str  # "scalar", "vector", "multicomponent", "spectrogram"
    labels: Optional[List[str]]
    colored: bool = False
```

```python
@dataclass(frozen=True)
class _ColoredAnnotation:
    inner: Any


@dataclass(frozen=True)
class Colored:
    """A VP result coloured point by point: ``return Colored(data, color=c)``.

    ``data`` is anything the inner type accepts (SpeasyVariable or ``(t, values)``);
    ``color`` has one value per time sample. Annotate with ``-> Colored[Vector[...]]``.
    """
    data: Any
    color: Any

    def __class_getitem__(cls, inner):
        if inner is Spectrogram or getattr(inner, "product_type", None) == "spectrogram":
            raise TypeError("Colored[Spectrogram] is not supported: a spectrogram already has a colour axis")
        return _ColoredAnnotation(inner)
```

Add `Any` to the `typing` import. Then make `extract_vp_type_info` unwrap the marker (add at the top of the function body, and `import dataclasses` at module top):

```python
    if isinstance(annotation, _ColoredAnnotation):
        inner = extract_vp_type_info(annotation.inner)
        return dataclasses.replace(inner, colored=True) if inner is not None else None
```

Export `Colored` wherever the other types are re-exported: add it to the import list in `SciQLop/user_api/virtual_products/types.py`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest --no-xvfb tests/test_colored_vp_types.py tests/test_vp_types.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/user_api/data_types.py SciQLop/user_api/virtual_products/types.py tests/test_colored_vp_types.py
git commit -m "feat(vp): Colored result type and Colored[...] annotation"
```

---

### Task 2: providers turn `Colored` into a per-batch colour dict

**Files:**
- Create: `SciQLop/components/plotting/backend/color_axis.py`
- Modify: `SciQLop/components/plotting/backend/data_provider.py` (`_get_data`, ~lines 133-184; add `color_axis`)
- Modify: `SciQLop/components/plotting/backend/easy_provider.py` (`EasyProvider.__init__`, `get_data`; `EasyScalar`, `EasyVector`, `EasyMultiComponent`, `EasySpectrogram`)
- Test: `tests/test_virtual_products/test_colored_easy_provider.py`

**Interfaces:**
- Consumes: `Colored` from Task 1.
- Produces:
  - `ColorAxis(label: str = "", gradient: ColorGradient = ColorGradient.Jet)`, a frozen dataclass.
  - `as_color_values(color, n: int) -> np.ndarray`: float64, 1-D, length n. Raises `ValueError`.
  - `sort_colored(c: Colored) -> Colored`.
  - `DataProvider.color_axis(node) -> Optional[ColorAxis]`, which returns `None` by default.
  - `EasyScalar/EasyVector/EasyMultiComponent(..., color_axis: Optional[ColorAxis] = None)`.
  - `DataProvider._get_data` returns `{"data": [t, values], "color": np.ndarray}` for a coloured result. It returns `[]` when there is no data or on a rejected batch.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_virtual_products/test_colored_easy_provider.py
import logging

import numpy as np
import pytest

from SciQLop.user_api.data_types import Colored


@pytest.fixture(autouse=True)
def _isolate_products(qapp, monkeypatch):
    from SciQLop.core.models import products
    monkeypatch.setattr(products, "add_node", lambda *a, **k: None)


def _vector(callback, colored=True):
    from SciQLop.components.plotting.backend.easy_provider import EasyVector
    from SciQLop.components.plotting.backend.color_axis import ColorAxis
    return EasyVector(path=f"vp/{id(callback):x}", get_data_callback=callback,
                      components_names=["x", "y", "z"], metadata={},
                      color_axis=ColorAxis(label="|B|") if colored else None)


def _fetch(p):
    return p._get_data("node", 0.0, 10.0)


def test_colored_result_becomes_a_data_color_dict():
    t = np.linspace(0.0, 10.0, 5)
    xyz = np.random.rand(5, 3)
    c = np.arange(5.0)
    out = _fetch(_vector(lambda start, stop: Colored((t, xyz), color=c)))
    assert set(out) == {"data", "color"}
    assert np.array_equal(out["data"][0], t)
    assert np.array_equal(out["data"][1], xyz)
    assert np.array_equal(out["color"], c)


def test_unsorted_time_permutes_the_colour_with_the_data():
    t = np.array([3.0, 1.0, 2.0])
    xyz = np.array([[3, 3, 3], [1, 1, 1], [2, 2, 2]], dtype=float)
    c = np.array([30.0, 10.0, 20.0])
    out = _fetch(_vector(lambda start, stop: Colored((t, xyz), color=c)))
    assert np.array_equal(out["data"][0], [1.0, 2.0, 3.0])
    assert np.array_equal(out["color"], [10.0, 20.0, 30.0])


def test_wrong_colour_length_is_rejected_with_an_error(caplog):
    t = np.linspace(0.0, 10.0, 5)
    p = _vector(lambda start, stop: Colored((t, np.zeros((5, 3))), color=np.zeros(4)))
    with caplog.at_level(logging.ERROR):
        assert _fetch(p) == []
    assert "colour" in caplog.text


def test_coloured_vp_returning_plain_data_is_an_error(caplog):
    t = np.linspace(0.0, 10.0, 5)
    p = _vector(lambda start, stop: (t, np.zeros((5, 3))))
    with caplog.at_level(logging.ERROR):
        assert _fetch(p) == []
    assert "Colored" in caplog.text


def test_plain_vp_returning_colored_is_an_error(caplog):
    t = np.linspace(0.0, 10.0, 5)
    p = _vector(lambda start, stop: Colored((t, np.zeros((5, 3))), color=t), colored=False)
    with caplog.at_level(logging.ERROR):
        assert _fetch(p) == []
    assert "colored=True" in caplog.text


@pytest.mark.parametrize("color", [
    np.arange(5.0).reshape(5, 1),
    np.arange(5),
    np.arange(5).astype("datetime64[s]"),
])
def test_colour_dtypes_and_column_shape_become_float64(color):
    t = np.linspace(0.0, 10.0, 5)
    out = _fetch(_vector(lambda start, stop: Colored((t, np.zeros((5, 3))), color=color)))
    assert out["color"].dtype == np.float64 and out["color"].shape == (5,)
    assert np.array_equal(out["color"], np.arange(5.0))


def test_plain_vector_returning_three_arrays_is_unchanged():
    """Regression guard for the rejected 'three buffers mean colour' rule."""
    t = np.linspace(0.0, 10.0, 5)
    payload = (t, np.zeros(5), np.ones(5))
    out = _fetch(_vector(lambda start, stop: payload, colored=False))
    assert isinstance(out, tuple) and len(out) == 3


def test_color_axis_is_exposed_by_the_provider():
    p = _vector(lambda start, stop: None)
    assert p.color_axis("node").label == "|B|"
    assert _vector(lambda start, stop: None, colored=False).color_axis("node") is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest --no-xvfb tests/test_virtual_products/test_colored_easy_provider.py -v`
Expected: FAIL with `ModuleNotFoundError: ... color_axis`.

- [ ] **Step 3: Create `color_axis.py`**

```python
# SciQLop/components/plotting/backend/color_axis.py
"""Colour axis of a virtual product: what it looks like, and its per-sample values."""
from dataclasses import dataclass

import numpy as np
from speasy.products import SpeasyVariable
from SciQLopPlots import ColorGradient

from SciQLop.user_api.data_types import Colored


@dataclass(frozen=True)
class ColorAxis:
    label: str = ""
    gradient: ColorGradient = ColorGradient.Jet


def _time_of(data) -> np.ndarray:
    return data.time if isinstance(data, SpeasyVariable) else np.asarray(data[0])


def as_color_values(color, n: int) -> np.ndarray:
    values = np.squeeze(np.asarray(color))
    if np.issubdtype(values.dtype, np.datetime64):
        values = values.astype("datetime64[ns]").astype(np.int64) / 1e9
    if values.ndim != 1 or len(values) != n:
        raise ValueError(f"expected one colour value per time sample ({n}), got shape {np.shape(color)}")
    return np.ascontiguousarray(values, dtype=np.float64)


def sort_colored(c: Colored) -> Colored:
    """Sort by time; the colour follows the data (SciQLop sorts unsorted variables)."""
    t = _time_of(c.data)
    order = np.argsort(t, kind="stable")
    if np.array_equal(order, np.arange(len(t))):
        return c
    data = c.data[order] if isinstance(c.data, SpeasyVariable) else \
        (np.asarray(c.data[0])[order], np.asarray(c.data[1])[order])
    return Colored(data, np.asarray(c.color)[order])
```

Before relying on `SpeasyVariable[order]`, check it once: `uv run python -c "import numpy as np; from speasy.products import SpeasyVariable, VariableTimeAxis, DataContainer; v=SpeasyVariable(axes=[VariableTimeAxis(np.array([3,1,2],dtype='datetime64[s]').astype('datetime64[ns]'))], values=DataContainer(np.arange(3.0))); print(v[np.array([1,2,0])].time)"`. If integer-array indexing is not supported, sort with the existing `_sort_variable_by_time` in `data_provider.py` and use `np.argsort(v.time, kind="stable")` for the colour.

- [ ] **Step 4: `DataProvider` understands `Colored`**

In `data_provider.py`:
- Add `from SciQLop.user_api.data_types import Colored` and `from .color_axis import ColorAxis, as_color_values, sort_colored`.
- Add to `DataProvider`:

```python
    def color_axis(self, node) -> Optional[ColorAxis]:
        return None
```

- Extract the body of `_get_data` that runs after the `on_variable` call into `_to_buffers(self, node, product, v)`. That is the `None` check, the list/tuple branch and the SpeasyVariable branch. It must behave exactly as today.
- Add the coloured branch:

```python
    def _colored_buffers(self, node, product, c: Colored):
        c = sort_colored(c)
        data = self._to_buffers(node, product, c.data)
        if not len(data):
            return []
        try:
            color = as_color_values(c.color, len(data[0]))
        except ValueError as e:
            log.error(f"{product}: dropping batch, bad colour values: {e}")
            return []
        return {"data": list(data), "color": color}
```

- In `_get_data`, pass the inner data to `on_variable`, so plot hints still see a SpeasyVariable. Then dispatch:

```python
                if v is not None and on_variable is not None:
                    try:
                        on_variable(v.data if isinstance(v, Colored) else v)
                    except Exception:
                        log.debug("on_variable callback failed", exc_info=True)
                if isinstance(v, Colored):
                    return self._colored_buffers(node, product, v)
                return self._to_buffers(node, product, v)
```

- [ ] **Step 5: Easy providers check the declared kind**

In `easy_provider.py`:
- Add `color_axis: Optional[ColorAxis] = None` to `EasyProvider.__init__` and store it as `self._color_axis`.
- Add `def color_axis(self, node): return self._color_axis`.
- Rename each subclass's `get_data` body to `_to_variable(self, res)`. `EasyScalar`, `EasyVector` and `EasySpectrogram` each take the callback result and return what `get_data` returned before.
- Keep `get_data` only in `EasyProvider`:

```python
    def get_data(self, product, start, stop, knobs=None):
        res = self._invoke_callback(start, stop, knobs)
        if res is None:
            return None
        res = self._checked_colored(res)
        if isinstance(res, Colored):
            return Colored(self._to_variable(res.data), res.color)
        return self._to_variable(res) if res is not None else None

    def _checked_colored(self, res):
        if (self._color_axis is not None) == isinstance(res, Colored):
            return res
        if isinstance(res, Colored):
            log.error(f"{self.name}: returned Colored(...) but was not declared with colored=True")
        else:
            log.error(f"{self.name}: declared colored=True but did not return Colored(...)")
        return None
```

- Add `color_axis=None` to the `EasyScalar`, `EasyVector` and `EasyMultiComponent` constructors and forward it. `EasySpectrogram` does not take it.
- Out-of-process VPs need nothing here; Task 8 handles them.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest --no-xvfb tests/test_virtual_products/ tests/test_colored_vp_types.py -v`
Expected: all PASS, including the pre-existing easy-provider and knob tests.

- [ ] **Step 7: Commit**

```bash
git add SciQLop/components/plotting/backend/color_axis.py SciQLop/components/plotting/backend/data_provider.py SciQLop/components/plotting/backend/easy_provider.py tests/test_virtual_products/test_colored_easy_provider.py
git commit -m "feat(vp): providers send a Colored result as one data+colour batch"
```

---

### Task 3: `create_virtual_product` declares a colour axis

**Files:**
- Modify: `SciQLop/user_api/virtual_products/__init__.py` (`VirtualScalar`, `VirtualVector`, `VirtualMultiComponent`, `create_virtual_product`)
- Test: `tests/test_colored_vp_types.py` (append)

**Interfaces:**
- Consumes: `ColorAxis` from Task 2; `_as_color_gradient` from `SciQLop/user_api/plot/_graphs.py`.
- Produces: `create_virtual_product(..., colored: bool = False, color_label: str = "", color_gradient="jet")`. The virtual product's `_impl.color_axis(None)` returns a `ColorAxis`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_colored_vp_types.py`)

```python
@pytest.fixture
def _no_product_tree(qapp, monkeypatch):
    from SciQLop.core.models import products
    monkeypatch.setattr(products, "add_node", lambda *a, **k: None)


def test_create_virtual_product_declares_a_colour_axis(_no_product_tree):
    from SciQLopPlots import ColorGradient
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType
    vp = create_virtual_product("t/colored", lambda start, stop: None, VirtualProductType.Vector,
                                labels=["X", "Y", "Z"], colored=True,
                                color_label="|B| (nT)", color_gradient="viridis")
    axis = vp._impl.color_axis(None)
    assert axis.label == "|B| (nT)" and axis.gradient == ColorGradient.Viridis


def test_uncoloured_by_default(_no_product_tree):
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType
    vp = create_virtual_product("t/plain", lambda start, stop: None, VirtualProductType.Scalar, labels=["a"])
    assert vp._impl.color_axis(None) is None


def test_colored_spectrogram_is_refused(_no_product_tree):
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType
    with pytest.raises(ValueError, match="Spectrogram"):
        create_virtual_product("t/spec", lambda start, stop: None, VirtualProductType.Spectrogram,
                               colored=True)


def test_unknown_gradient_is_refused_early(_no_product_tree):
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType
    with pytest.raises(ValueError, match="gradient"):
        create_virtual_product("t/bad", lambda start, stop: None, VirtualProductType.Scalar,
                               labels=["a"], colored=True, color_gradient="nope")
```

`ColorGradient.Viridis` is assumed to exist. Check with `uv run python -c "from SciQLopPlots import ColorGradient; print([n for n in dir(ColorGradient) if not n.startswith('_')])"`, and use any listed name other than `Jet` if it doesn't.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest --no-xvfb tests/test_colored_vp_types.py -v`
Expected: FAIL with `TypeError: create_virtual_product() got an unexpected keyword argument 'colored'`.

- [ ] **Step 3: Implement**

In `create_virtual_product`, add the three keyword arguments at the end of the signature, then build the axis once:

```python
def _color_axis(colored: bool, label: str, gradient, product_type) -> Optional["ColorAxis"]:
    if not colored:
        return None
    if product_type == VirtualProductType.Spectrogram:
        raise ValueError("Spectrogram virtual products cannot be colored: they already have a colour axis")
    from SciQLop.components.plotting.backend.color_axis import ColorAxis
    from SciQLop.user_api.plot._graphs import _as_color_gradient
    return ColorAxis(label=label, gradient=_as_color_gradient(gradient))
```

Call `color_axis = _color_axis(colored, color_label, color_gradient, product_type)` right after the `product_type` type check. Pass `color_axis=color_axis` to `VirtualScalar`, `VirtualVector` and `VirtualMultiComponent`. Each of them gets a `color_axis=None` keyword argument and forwards it to its `_Easy*` constructor. Document the three parameters in the docstring, in the existing numpy style:

```
    colored : bool
        The callback returns ``Colored(data, color=c)``: one colour value per sample,
        drawn on the plot's colour scale. Not for Spectrogram.
    color_label : str
        Label of the colour axis.
    color_gradient : ColorGradient or str
        Gradient of the colour axis, e.g. "viridis" (default "jet").
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest --no-xvfb tests/test_colored_vp_types.py tests/test_user_api_validation.py tests/test_api_consistency.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/user_api/virtual_products/__init__.py tests/test_colored_vp_types.py
git commit -m "feat(vp): create_virtual_product(colored=, color_label=, color_gradient=)"
```

---

### Task 4: debug validation understands `Colored`

**Files:**
- Modify: `SciQLop/user_api/virtual_products/validation.py` (`validate_with_data`)
- Modify: `SciQLop/user_api/virtual_products/debug.py` (`_extract_data_info`)
- Test: `tests/test_colored_vp_validation.py`

**Interfaces:**
- Consumes: `Colored` (Task 1), `as_color_values` (Task 2).
- Produces: `validate_with_data(Colored(...), ...)` validates `.data` as before, and adds an error `Diagnostic` for a bad colour. `ValidationResult.data` stays the `Colored` object.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_colored_vp_validation.py
import numpy as np

from SciQLop.user_api.data_types import Colored
from SciQLop.user_api.virtual_products.validation import validate_with_data


def _errors(result):
    return [d.message for d in result.diagnostics if d.level == "error"]


def test_valid_colored_vector_has_no_errors():
    t = np.linspace(0.0, 10.0, 5)
    r = validate_with_data(Colored((t, np.zeros((5, 3))), color=t), "vector", None)
    assert _errors(r) == []
    assert isinstance(r.data, Colored)


def test_colour_of_the_wrong_length_is_an_error():
    t = np.linspace(0.0, 10.0, 5)
    r = validate_with_data(Colored((t, np.zeros((5, 3))), color=np.zeros(3)), "vector", None)
    assert any("colour" in m for m in _errors(r))


def test_two_dimensional_colour_is_an_error():
    t = np.linspace(0.0, 10.0, 5)
    r = validate_with_data(Colored((t, np.zeros((5, 3))), color=np.zeros((5, 2))), "vector", None)
    assert any("colour" in m for m in _errors(r))


def test_inner_data_is_still_checked():
    t = np.linspace(0.0, 10.0, 5)
    r = validate_with_data(Colored((t, np.zeros((5, 2))), color=t), "vector", None)
    assert any("components" in m for m in _errors(r))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest --no-xvfb tests/test_colored_vp_validation.py -v`
Expected: FAIL. Today `_check_return_type` reports "Expected SpeasyVariable or (x, y) tuple, got Colored".

- [ ] **Step 3: Implement**

In `validation.py`, wrap the existing `validate_with_data`. Rename the current function to `_validate_plain` with the same signature, and add:

```python
def _check_color(c) -> List[Diagnostic]:
    from SciQLop.components.plotting.backend.color_axis import as_color_values
    t = _extract_time_vector(c.data)
    if t is None:
        return []
    try:
        as_color_values(c.color, len(t))
    except ValueError as e:
        return [Diagnostic("error", f"Bad colour values: {e}")]
    return []


def validate_with_data(data, declared_type: str, labels: Optional[List[str]],
                       elapsed: float = 0.0, *,
                       start: Optional[float] = None,
                       stop: Optional[float] = None) -> ValidationResult:
    """Validate pre-computed data without re-calling the callback."""
    from SciQLop.user_api.data_types import Colored
    if not isinstance(data, Colored):
        return _validate_plain(data, declared_type, labels, elapsed, start=start, stop=stop)
    inner = _validate_plain(data.data, declared_type, labels, elapsed, start=start, stop=stop)
    return ValidationResult(data=data, diagnostics=inner.diagnostics + _check_color(data),
                            elapsed=inner.elapsed)
```

`_validate_plain` may convert the data (`_check_contiguity`). Keep `data` as the user's `Colored` object in the result: `get_data` already makes the arrays contiguous later.

In `debug.py`, make `_extract_data_info(data)` unwrap first: add `if isinstance(data, Colored): data = data.data` as its first line, with the import from `SciQLop.user_api.data_types`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest --no-xvfb tests/test_colored_vp_validation.py tests/test_vp_validation.py tests/test_virtual_products/test_debug_knobs.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/user_api/virtual_products/validation.py SciQLop/user_api/virtual_products/debug.py tests/test_colored_vp_validation.py
git commit -m "feat(vp): debug validation checks a Colored result's colour"
```

---

### Task 5: `%%vp` magic and registry

**Files:**
- Modify: `SciQLop/user_api/virtual_products/magic.py` (`_infer_type_from_data`, `_inject_type_names`, the `_registry.register` / `_register_virtual_product` calls)
- Modify: `SciQLop/user_api/virtual_products/registry.py` (`RegistryEntry`, `VPRegistry.register`, `register_virtual_product`)
- Test: `tests/test_colored_vp_magic.py`

**Interfaces:**
- Consumes: `VPTypeInfo.colored` (Task 1), `create_virtual_product(colored=...)` (Task 3).
- Produces: `VPRegistry.register(name, callback, product_type, labels, colored=False)`; `RegistryEntry.colored`; `register_virtual_product(..., colored=False)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_colored_vp_magic.py
import numpy as np

from SciQLop.user_api.data_types import Colored, VPTypeInfo
from SciQLop.user_api.virtual_products.magic import _infer_type_from_data, _inject_type_names
from SciQLop.user_api.virtual_products.registry import VPRegistry


def test_colored_name_is_injected_for_annotations():
    ns = {}
    _inject_type_names(ns)
    assert ns["Colored"] is Colored


def test_unannotated_colored_result_is_inferred_as_coloured_inner_type():
    t = np.linspace(0.0, 1.0, 4)
    info = _infer_type_from_data(Colored((t, np.zeros((4, 3))), color=t))
    assert info == VPTypeInfo("vector", None, colored=True)


def test_redeclaring_as_colored_is_a_new_registration():
    reg = VPRegistry()
    f = lambda start, stop: None
    reg.register("vp", f, "vector", None)
    entry = reg.register("vp", f, "vector", None, colored=True)
    assert entry.signature_changed is True and entry.colored is True


def test_same_declaration_is_hot_swapped():
    reg = VPRegistry()
    f = lambda start, stop: None
    reg.register("vp", f, "vector", None, colored=True)
    assert reg.register("vp", f, "vector", None, colored=True).signature_changed is False
```

End to end, the magic path with `from __future__ import annotations`: add this to the same file. It uses the GUI fixture, as `tests/test_virtual_products/test_vp_redeclare_refetch.py` does.

```python
from tests.fixtures import *  # noqa: F401,F403


def test_vp_magic_registers_a_colored_vp_from_a_string_annotation(qtbot, qapp, main_window):
    from SciQLop.user_api.virtual_products.magic import vp_magic
    cell = (
        "from __future__ import annotations\n"
        "def colored_vp(start: float, stop: float) -> Colored[Vector['X', 'Y', 'Z']]:\n"
        "    import numpy as np\n"
        "    t = np.linspace(start, stop, 8)\n"
        "    return Colored((t, np.zeros((8, 3))), color=t)\n"
    )
    _func, _args, info = vp_magic("--start 0 --stop 10", cell, local_ns={})
    assert info.colored is True and info.labels == ["X", "Y", "Z"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest --no-xvfb tests/test_colored_vp_magic.py -v`
Expected: FAIL (`KeyError: 'Colored'`, and `register()` got an unexpected keyword argument).

- [ ] **Step 3: Implement**

`magic.py`:
- `_inject_type_names`: also import `Colored` and `user_ns.setdefault("Colored", Colored)`.
- `_infer_type_from_data`: first lines

```python
    from SciQLop.user_api.data_types import Colored
    if isinstance(data, Colored):
        return dataclasses.replace(_infer_type_from_data(data.data), colored=True)
```

  (add `import dataclasses` at module top).
- The register calls pass the flag:
  `entry = _registry.register(func_name, func, type_info.product_type, type_info.labels, colored=type_info.colored)`, and `_register_virtual_product(..., cachable=args.cachable, colored=type_info.colored)`.

`registry.py`:
- `RegistryEntry` gets `colored: bool = False`.
- `VPRegistry.register(..., colored: bool = False)`: the hot-swap condition becomes `existing.product_type == product_type and existing.labels == labels and existing.colored == colored`, and the new `RegistryEntry(...)` gets `colored=colored`.
- `register_virtual_product(..., cachable: bool = False, colored: bool = False)` passes `colored=colored` to both `create_virtual_product` calls in `_do_register`. For the Spectrogram call, pass nothing: `Colored[Spectrogram]` is already refused in Task 1.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest --no-xvfb tests/test_colored_vp_magic.py tests/test_vp_magic.py tests/test_virtual_products/test_vp_redeclare_refetch.py tests/test_virtual_products/test_registry_knobs.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/user_api/virtual_products/magic.py SciQLop/user_api/virtual_products/registry.py tests/test_colored_vp_magic.py
git commit -m "feat(vp): %%vp understands Colored[...] and re-registers on a colour change"
```

---

### Task 6: projection reshape keeps the colour

**Files:**
- Modify: `SciQLop/components/plotting/ui/time_sync_panel.py:280-310` (`_projection_shaped_callback`)
- Test: `tests/test_projection_product_shape.py` (append)

**Interfaces:**
- Consumes: the dict shape from Task 2.
- Produces: `_projection_shaped_callback(cb)(start, stop)` maps `{"data": [t, (N,k)], "color": c}` to `{"data": [t, d0..dk-1], "color": c}`.

- [ ] **Step 1: Write the failing tests** (append)

```python
def test_a_coloured_result_is_split_and_keeps_its_colour():
    t = np.linspace(0.0, 10.0, 20)
    values = np.random.rand(20, 3)
    c = np.arange(20.0)
    shaped = _projection_shaped_callback(lambda a, b: {"data": [t, values], "color": c})(0.0, 10.0)
    assert shaped["color"] is c
    assert len(shaped["data"]) == 4
    for i in range(3):
        assert np.array_equal(shaped["data"][i + 1], values[:, i])


def test_a_coloured_scalar_cannot_be_projected():
    t = np.linspace(0.0, 1.0, 5)
    got = _projection_shaped_callback(lambda a, b: {"data": [t, np.arange(5.0)], "color": t})(0.0, 1.0)
    assert got is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest --no-xvfb tests/test_projection_product_shape.py -v`
Expected: the two new tests FAIL (the dict is passed through unchanged).

- [ ] **Step 3: Implement**

Move the column split out of `__call__` into a method, and make `__call__` dict-aware:

```python
    def __call__(self, start, stop):
        result = self._inner(start, stop)
        if isinstance(result, dict):
            data = self._split(result["data"])
            return None if data is None else {"data": data, "color": result["color"]}
        return self._split(result)

    def _split(self, result):
        if result is None:
            return result
        if not isinstance(result, (tuple, list)) or len(result) != 2:
            return result                  # already shaped, or something we don't know
        time, values = result
        values = np.asarray(values)
        if values.ndim != 2:
            log.error("a projection plot needs several dimensions; %s is 1-D, "
                      "so there is nothing to project", getattr(self, "node", "product"))
            return None
        return [time] + [np.ascontiguousarray(values[:, i])
                         for i in range(values.shape[1])]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest --no-xvfb tests/test_projection_product_shape.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/plotting/ui/time_sync_panel.py tests/test_projection_product_shape.py
git commit -m "feat(projection): the product reshape keeps a batch's colour"
```

---

### Task 7: plotting a coloured VP (needs SciQLopPlots Part 1)

**Precondition:** `uv run python -c "import SciQLopPlots as s; assert hasattr(s.SciQLopLineGraph, 'set_color_gradient')"` succeeds. If it fails, stop and report: the user has to install the Part 1 build.

**Files:**
- Modify: `SciQLop/components/plotting/backend/color_axis.py` (add `apply_color_axis`)
- Modify: `SciQLop/components/plotting/ui/time_sync_panel.py` (`plot_product`, Scalar/Vector/Multicomponents branch)
- Modify: `pyproject.toml` + `uv.lock` (raise the `SciQLopPlots==` pin to the Part 1 release, once it exists; `uv lock --upgrade-package SciQLopPlots`)
- Test: `tests/test_colored_vp_plot.py`

**Interfaces:**
- Consumes: `DataProvider.color_axis(node)` (Task 2); `SciQLopLineGraph.set_color_gradient`, `SciQLopNDProjectionCurves.set_color_gradient`; the plot's `z_axis().set_label`.
- Produces: `apply_color_axis(plot, graph, axis: Optional[ColorAxis]) -> None`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_colored_vp_plot.py
"""A coloured VP plotted for real: the colour reaches the plot's colour scale."""
import numpy as np
import pytest

from tests.fixtures import *  # noqa: F401,F403
from SciQLop.user_api.data_types import Colored


def _traj(start: float, stop: float):
    t = np.linspace(start, stop, 64)
    a = np.linspace(0, 2 * np.pi, 64)
    return Colored((t, np.column_stack([np.cos(a), np.sin(a), a])), color=np.linspace(5.0, 25.0, 64))


def _declare(path):
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType
    return create_virtual_product(path, _traj, VirtualProductType.Vector, labels=["X", "Y", "Z"],
                                  colored=True, color_label="|B| (nT)", color_gradient="viridis")


def _z_range(plot):
    r = plot.z_axis().range()
    return r.start(), r.stop()


def test_time_series_line_is_coloured(qtbot, main_window):
    from SciQLop.components.plotting.ui.time_sync_panel import plot_product
    from SciQLop.user_api.plot import create_plot_panel
    _declare("colored_test/ts")
    panel = create_plot_panel()
    panel.time_range = (0.0, 100.0)
    plot, graph = plot_product(panel._impl, ["colored_test", "ts"])
    qtbot.waitUntil(lambda: _z_range(plot) == pytest.approx((5.0, 25.0)), timeout=5000)
    assert plot.z_axis().label() == "|B| (nT)"


def test_projection_curve_is_coloured_and_keeps_time(qtbot, main_window):
    from SciQLopPlots import PlotType
    from SciQLop.components.plotting.ui.time_sync_panel import plot_product
    from SciQLop.user_api.plot import create_plot_panel
    _declare("colored_test/proj")
    panel = create_plot_panel()
    panel.time_range = (0.0, 100.0)
    plot, graph = plot_product(panel._impl, ["colored_test", "proj"], plot_type=PlotType.Projections)
    qtbot.waitUntil(lambda: _z_range(plot) == pytest.approx((5.0, 25.0)), timeout=5000)
```

Before writing these assertions, check two things by introspection. First, what `plot_product` returns for a projection: a `(plot, graph)` tuple whose `plot` is the `SciQLopNDProjectionPlot`. Second, whether `panel.time_range = (0.0, 100.0)` is how existing tests set a range: grep `tests/` for `time_range =`. Adjust the fixture code to what you find, and keep the assertions.

For "keeps time": check the time marker through whatever Part 1's report names. If it names no getter, assert the SciQLopPlots side only there: its integration test already covers it. Leave a one-line comment in the test saying so.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest --no-xvfb tests/test_colored_vp_plot.py -v`
Expected: FAIL (the z-axis range never becomes (5, 25), or the label stays empty).

- [ ] **Step 3: Implement**

In `color_axis.py`:

```python
def apply_color_axis(plot, graph, axis: Optional[ColorAxis]) -> None:
    if axis is None or graph is None:
        return
    graph.set_color_gradient(axis.gradient)
    if axis.label:
        plot.z_axis().set_label(axis.label)
```

(add `from typing import Optional`). In `plot_product`, in the Scalar/Vector/Multicomponents branch, right after `r.set_name(...)`:

```python
        plot, graph = r if hasattr(r, '__iter__') else (existing_plot, r)
        apply_color_axis(plot, graph, provider.color_axis(node))
```

This is applied on every plot, so a hot-reloaded VP gets its current axis (spec, Part 3, step 5). If `plot` can be `None` here (a bare graph with no `existing_plot`), use `graph`'s parent plot the way `_post_plot` resolves it. Read `_graph_from_result` and `_post_plot` first, and reuse whatever they use.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest --no-xvfb tests/test_colored_vp_plot.py tests/test_projection_product_shape.py tests/test_projection_time_colored_curve.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/plotting/backend/color_axis.py SciQLop/components/plotting/ui/time_sync_panel.py pyproject.toml uv.lock tests/test_colored_vp_plot.py
git commit -m "feat(plotting): coloured VPs draw on the plot's colour scale"
```

---

### Task 8: out-of-process coloured VPs (needs SciQLopPlots Part 1)

**Files:**
- Modify: `SciQLop/components/plotting/backend/easy_provider.py` (the `out_of_process` registration, ~line 196)
- Modify: `SciQLop/components/plotting/backend/remote/registry.py` (`register`, `spec_for`, `_specs`)
- Modify: `SciQLop/components/plotting/backend/remote/reduction.py` (`reduce_result`, module docstring)
- Modify: `SciQLop/components/plotting/backend/remote/channel.py` (`RemoteChannel.__init__`, `on_result`)
- Modify: `SciQLop/components/plotting/backend/remote/plot_remote.py`
- Test: `tests/remote/test_colored_remote.py`

**Interfaces:**
- Consumes: `Colored`, `as_color_values`, `apply_color_axis`; SciQLopPlots remote pipeline `set_data_colored(data: list, color)`.
- Produces: `RemoteRegistry.register(path, callback, arity, colored=False)`; `spec_for(path) -> (blob, arity, colored)`; `reduce_result(Colored, arity)` returns the inner arrays plus the colour as the last array; `RemoteChannel(..., colored=False)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/remote/test_colored_remote.py
import numpy as np
import pytest

from tests.helpers import *  # noqa: F401,F403
from SciQLop.user_api.data_types import Colored


def _colored_source(start: float, stop: float):
    t = np.linspace(start, stop, 16)
    return Colored((t, np.column_stack([t, t, t])), color=np.linspace(1.0, 2.0, 16))


@pytest.fixture(autouse=True)
def _isolate_registry():
    import SciQLop.components.plotting.backend.remote.registry as reg_mod
    old = reg_mod._REGISTRY
    reg_mod._REGISTRY = None
    yield
    if reg_mod._REGISTRY is not None:
        try:
            reg_mod._REGISTRY.shutdown_all()
        except Exception:
            pass
    reg_mod._REGISTRY = old


def test_reduce_result_appends_the_colour():
    from SciQLop.components.plotting.backend.remote.reduction import reduce_result
    arrays = reduce_result(_colored_source(0.0, 1.0), 2)
    assert len(arrays) == 3
    assert np.array_equal(arrays[2], np.linspace(1.0, 2.0, 16))


def test_remote_colored_vector_is_coloured_and_not_left_busy(qtbot, main_window):
    from SciQLop.components.plotting.backend.easy_provider import EasyVector
    from SciQLop.components.plotting.backend.color_axis import ColorAxis
    from SciQLop.components.plotting.ui.time_sync_panel import plot_product
    from SciQLop.user_api.plot import create_plot_panel
    EasyVector(path="colored_remote/vec", get_data_callback=_colored_source,
               components_names=["x", "y", "z"], metadata={}, out_of_process=True,
               color_axis=ColorAxis(label="c"))
    panel = create_plot_panel()
    plot, graph = plot_product(panel._impl, ["colored_remote", "vec"])
    qtbot.waitUntil(lambda: not graph.busy(), timeout=10000)
    qtbot.waitUntil(lambda: (plot.z_axis().range().start(), plot.z_axis().range().stop())
                    == pytest.approx((1.0, 2.0)), timeout=10000)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest --no-xvfb tests/remote/test_colored_remote.py -v`
Expected: FAIL (`reduce_result` raises on a `Colored`).

- [ ] **Step 3: Implement**

`reduction.py`:

```python
def reduce_result(result, arity: int) -> List[np.ndarray]:
    from SciQLop.user_api.data_types import Colored
    if isinstance(result, Colored):
        from SciQLop.components.plotting.backend.color_axis import as_color_values, sort_colored
        result = sort_colored(result)
        arrays = reduce_result(result.data, arity)
        return arrays + [as_color_values(result.color, len(arrays[0]))]
    if _is_speasy_variable(result):
        return _from_speasy(result, arity)
    return _from_sequence(result, arity)
```

Update the module docstring: "arity is fixed by the graph type at INSTALL (2 = line/curve, 3 = colormap); a coloured channel receives one extra, last array: the colour."

`registry.py`: store `(blob, arity, plugin_key, colored)`. `register(self, path, callback, arity, colored: bool = False)`. `spec_for` returns `blob, arity, colored`. Update the `worker_for` unpacking to four fields.

`easy_provider.py` (out_of_process block): `remote_registry().register(path, remote_callback, arity, colored=self._color_axis is not None)`. `self._color_axis` must be assigned before this block runs, so move it up if needed.

`channel.py`: add `colored: bool = False` to `RemoteChannel.__init__` and store it as `self._colored`. In `on_result`, replace `self._pipeline.set_data(*views)` with `self._deliver(views)`:

```python
    def _deliver(self, views) -> None:
        if not self._colored:
            self._pipeline.set_data(*views)
        elif len(views) == 3:
            self._pipeline.set_data_colored(list(views[:-1]), views[-1])
        else:
            log.error("coloured remote channel %s got %d arrays instead of 3 (did the "
                      "callback return Colored(...)?)", self.channel_id, len(views))
```

The error path drops the batch, the same way `on_error` (`channel.py:86-88`) drops a failed fetch today: it logs and sends nothing to the pipeline. Whatever `on_error` leaves in the graph's busy state, this path leaves the same. It does not fix or change that behaviour.

`plot_remote.py`: `blob, arity, colored = reg.spec_for(product)`, and pass `colored=colored` to `RemoteChannel(...)`. After the graph is created, call `apply_color_axis(plot, graph, provider.color_axis(node))`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest --no-xvfb tests/remote/ -v`
Expected: all PASS, including the existing remote tests.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/plotting/backend/easy_provider.py SciQLop/components/plotting/backend/remote/ tests/remote/test_colored_remote.py
git commit -m "feat(remote): out-of-process VPs can return Colored results"
```

---

### Task 9: changelog, public API memory, full suite

**Files:**
- Modify: `CHANGELOG.md` (Unreleased section, following the existing entry style)
- Modify: `/home/jeandet/.claude/memory/sciqlop-user-api.md` (the virtual products section)

- [ ] **Step 1: Changelog entry.** Add, under the unreleased heading and following the file's style: "Virtual products can colour their line or projection curve by a scalar: return `Colored(data, color=c)` and declare `colored=True` (or annotate `-> Colored[Vector[...]]` in `%%vp`)."
- [ ] **Step 2: Update the public API memory** with `Colored`, `Colored[...]`, and the three `create_virtual_product` keyword arguments. Include a 5-line example.
- [ ] **Step 3: Full suite, once, in the foreground.** First check `df -h /tmp`. If it's above 70%, clean the leaked `/tmp/sciqlop_test_*` directories (see memory `pitfall-tmp-quota-stalls-test-suite`). Then run `uv run pytest --no-xvfb -q -p no:cacheprovider` and read the real summary line (about 24 minutes).
  Expected: 0 failed. The baseline is 3140 passed on 2026-09-24, plus the new tests.
- [ ] **Step 4: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: changelog for colour-axis virtual products"
```
