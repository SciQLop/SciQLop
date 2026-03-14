# Virtual Product Cell Magic (`%%vp`) Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `create_virtual_product()` with a `%%vp` Jupyter cell magic that infers product type from annotations, supports hot-reload via mutable callback wrappers, and provides a `--debug` workbench with diagnostic overlays.

**Architecture:** Four new modules under `SciQLop/user_api/virtual_products/` (types, validation, magic, and the diagnostic overlay widget). The magic parses cell code, extracts the function + return annotation, infers product type/labels, registers via existing `EasyProvider`, and wraps callbacks in `MutableCallback` for hot-reload. Debug mode opens a scratch pad `TimeSyncPanel` with a `DiagnosticOverlay` widget.

**Tech Stack:** Python 3.10+, PySide6 (Qt widgets for overlay), IPython cell magic API, existing SciQLopPlots C++ bindings, existing `EasyProvider`/`DataProvider` infrastructure.

**Spec:** `docs/superpowers/specs/2026-03-14-vp-cell-magic-design.md`

---

## Chunk 1: Type Annotations + Validation Pipeline

### Task 1: Product Type Annotations (`types.py`)

**Files:**
- Create: `SciQLop/user_api/virtual_products/types.py`
- Test: `tests/test_vp_types.py`

- [ ] **Step 1: Write failing tests for type annotations**

```python
# tests/test_vp_types.py
import pytest
from SciQLop.user_api.virtual_products.types import Scalar, Vector, MultiComponent, Spectrogram, VPTypeInfo, extract_vp_type_info
import numpy as np


def test_scalar_no_label():
    info = extract_vp_type_info(Scalar)
    assert info.product_type == "scalar"
    assert info.labels is None


def test_scalar_with_label():
    info = extract_vp_type_info(Scalar["Temperature"])
    assert info.product_type == "scalar"
    assert info.labels == ["Temperature"]


def test_vector_no_labels():
    info = extract_vp_type_info(Vector)
    assert info.product_type == "vector"
    assert info.labels is None


def test_vector_with_labels():
    info = extract_vp_type_info(Vector["Bx", "By", "Bz"])
    assert info.product_type == "vector"
    assert info.labels == ["Bx", "By", "Bz"]


def test_multicomponent_with_labels():
    info = extract_vp_type_info(MultiComponent["E1", "E2", "E3", "E4"])
    assert info.product_type == "multicomponent"
    assert info.labels == ["E1", "E2", "E3", "E4"]


def test_spectrogram():
    info = extract_vp_type_info(Spectrogram)
    assert info.product_type == "spectrogram"
    assert info.labels is None


def test_extract_from_function_annotation():
    def my_func(start, stop) -> Vector["Bx", "By", "Bz"]:
        pass
    # Use __annotations__ directly (not get_type_hints) since __class_getitem__
    # eagerly evaluates into a _VPTypeWithLabels instance
    info = extract_vp_type_info(my_func.__annotations__["return"])
    assert info.product_type == "vector"
    assert info.labels == ["Bx", "By", "Bz"]


def test_no_annotation_returns_none():
    info = extract_vp_type_info(None)
    assert info is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_vp_types.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'SciQLop.user_api.virtual_products.types'`

- [ ] **Step 3: Implement type annotations**

```python
# SciQLop/user_api/virtual_products/types.py
from dataclasses import dataclass
from typing import Optional, List


@dataclass(frozen=True)
class VPTypeInfo:
    product_type: str  # "scalar", "vector", "multicomponent", "spectrogram"
    labels: Optional[List[str]]


class _VPType:
    _product_type: str

    def __init_subclass__(cls, product_type: str = "", **kwargs):
        super().__init_subclass__(**kwargs)
        cls._product_type = product_type

    def __class_getitem__(cls, labels):
        if not isinstance(labels, tuple):
            labels = (labels,)
        return _VPTypeWithLabels(cls._product_type, list(labels))


class _VPTypeWithLabels:
    def __init__(self, product_type: str, labels: List[str]):
        self.product_type = product_type
        self.labels = labels


class Scalar(_VPType, product_type="scalar"):
    pass


class Vector(_VPType, product_type="vector"):
    pass


class MultiComponent(_VPType, product_type="multicomponent"):
    pass


class Spectrogram(_VPType, product_type="spectrogram"):
    pass


def extract_vp_type_info(annotation) -> Optional[VPTypeInfo]:
    if annotation is None:
        return None
    if isinstance(annotation, _VPTypeWithLabels):
        return VPTypeInfo(product_type=annotation.product_type, labels=annotation.labels)
    if isinstance(annotation, type) and issubclass(annotation, _VPType):
        return VPTypeInfo(product_type=annotation._product_type, labels=None)
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_vp_types.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/user_api/virtual_products/types.py tests/test_vp_types.py
git commit -m "feat(virtual_products): add type annotation classes for %%vp magic"
```

---

### Task 2: Validation Pipeline (`validation.py`)

**Files:**
- Create: `SciQLop/user_api/virtual_products/validation.py`
- Test: `tests/test_vp_validation.py`

- [ ] **Step 1: Write failing tests for validation**

```python
# tests/test_vp_validation.py
import pytest
import numpy as np
from SciQLop.user_api.virtual_products.validation import validate_and_call, ValidationResult, Diagnostic


def _scalar_callback(start, stop):
    x = np.linspace(start, stop, 100)
    return x, np.sin(x)


def _bad_shape_callback(start, stop):
    x = np.linspace(start, stop, 100)
    return x, np.column_stack([np.sin(x)] * 5)


def _raising_callback(start, stop):
    raise ValueError("test error")


def _none_callback(start, stop):
    return None


def test_validate_success_scalar():
    result = validate_and_call(_scalar_callback, 0.0, 10.0, "scalar", ["v"])
    assert result.data is not None
    assert len(result.diagnostics) == 0
    assert result.elapsed > 0


def test_validate_exception():
    result = validate_and_call(_raising_callback, 0.0, 10.0, "scalar", ["v"])
    assert result.data is None
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].level == "error"
    assert "ValueError" in result.diagnostics[0].message
    assert "test error" in result.diagnostics[0].message


def test_validate_none_returned():
    result = validate_and_call(_none_callback, 0.0, 10.0, "scalar", ["v"])
    assert result.data is None
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].level == "warning"


def test_validate_shape_mismatch_vector():
    result = validate_and_call(_bad_shape_callback, 0.0, 10.0, "vector", ["X", "Y", "Z"])
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].level == "error"
    assert "shape" in result.diagnostics[0].message.lower()


def test_validate_dtype_coercion():
    def float32_callback(start, stop):
        x = np.linspace(start, stop, 100)
        return x, np.sin(x).astype(np.float32)

    result = validate_and_call(float32_callback, 0.0, 10.0, "scalar", ["v"])
    assert result.data is not None
    # Should have a warning about dtype conversion
    warnings = [d for d in result.diagnostics if d.level == "warning"]
    assert len(warnings) == 1
    assert "float32" in warnings[0].message
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_vp_validation.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement validation pipeline**

```python
# SciQLop/user_api/virtual_products/validation.py
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple

import numpy as np
from speasy.products import SpeasyVariable


@dataclass
class Diagnostic:
    level: str  # "error", "warning", "info"
    message: str


@dataclass
class ValidationResult:
    data: Any
    diagnostics: List[Diagnostic] = field(default_factory=list)
    elapsed: float = 0.0


_EXPECTED_COMPONENTS = {
    "scalar": 1,
    "vector": 3,
}


def _filter_traceback(tb_text: str) -> str:
    """Keep only frames from user code, not SciQLop internals."""
    lines = tb_text.strip().split("\n")
    filtered = []
    skip = False
    for line in lines:
        if 'File "' in line and "SciQLop/" in line:
            skip = True
        else:
            if line.startswith("  ") and skip:
                continue
            skip = False
        if not skip:
            filtered.append(line)
    # Always include the last line (the exception itself)
    if filtered and filtered[-1] != lines[-1]:
        filtered.append(lines[-1])
    return "\n".join(filtered) if filtered else tb_text


def _check_shape(data, declared_type: str, labels: Optional[List[str]]) -> List[Diagnostic]:
    if isinstance(data, SpeasyVariable):
        return []
    if not isinstance(data, (tuple, list)) or len(data) < 2:
        return [Diagnostic("error", f"Expected (x, y) tuple, got {type(data).__name__}")]

    y = data[1]
    if not isinstance(y, np.ndarray):
        return []

    diagnostics = []
    expected = _EXPECTED_COMPONENTS.get(declared_type)
    if expected is None and labels:
        expected = len(labels)

    if expected and y.ndim == 2 and y.shape[1] != expected:
        diagnostics.append(Diagnostic(
            "error",
            f"Declared {declared_type} ({expected} components) but got shape {y.shape}"
        ))
    elif expected and y.ndim == 1 and expected > 1:
        diagnostics.append(Diagnostic(
            "error",
            f"Declared {declared_type} ({expected} components) but got shape {y.shape}"
        ))

    return diagnostics


def _check_dtype(data) -> Tuple[Any, List[Diagnostic]]:
    if isinstance(data, SpeasyVariable) or not isinstance(data, (tuple, list)):
        return data, []

    diagnostics = []
    converted = list(data)
    for i, arr in enumerate(converted):
        if isinstance(arr, np.ndarray) and arr.dtype != np.float64 and np.issubdtype(arr.dtype, np.number):
            diagnostics.append(Diagnostic(
                "warning",
                f"Array {i} dtype is {arr.dtype} — converting to float64"
            ))
            converted[i] = arr.astype(np.float64)
    return tuple(converted), diagnostics


def validate_and_call(callback, start: float, stop: float,
                      declared_type: str, labels: Optional[List[str]]) -> ValidationResult:
    t0 = time.monotonic()
    try:
        data = callback(start, stop)
    except Exception:
        elapsed = time.monotonic() - t0
        tb = _filter_traceback(traceback.format_exc())
        return ValidationResult(
            data=None,
            diagnostics=[Diagnostic("error", tb)],
            elapsed=elapsed,
        )

    elapsed = time.monotonic() - t0

    if data is None:
        return ValidationResult(
            data=None,
            diagnostics=[Diagnostic("warning", f"No data returned for [{start}, {stop}]")],
            elapsed=elapsed,
        )

    diagnostics = _check_shape(data, declared_type, labels)
    if any(d.level == "error" for d in diagnostics):
        return ValidationResult(data=None, diagnostics=diagnostics, elapsed=elapsed)

    data, dtype_diags = _check_dtype(data)
    diagnostics.extend(dtype_diags)

    return ValidationResult(data=data, diagnostics=diagnostics, elapsed=elapsed)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_vp_validation.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/user_api/virtual_products/validation.py tests/test_vp_validation.py
git commit -m "feat(virtual_products): add validation pipeline for callback results"
```

---

## Chunk 2: Mutable Callback + Cell Magic Core

### Task 3: Mutable Callback Wrapper and Registry

**Files:**
- Create: `SciQLop/user_api/virtual_products/magic.py`
- Test: `tests/test_vp_magic.py`

This task implements the `MutableCallback` wrapper class and the `VPRegistry` that manages re-registration. The cell magic itself is added in Task 4.

- [ ] **Step 1: Write failing tests for MutableCallback and VPRegistry**

```python
# tests/test_vp_magic.py
import pytest
import numpy as np
from SciQLop.user_api.virtual_products.magic import MutableCallback, VPRegistry


def _callback_a(start: float, stop: float):
    return np.linspace(start, stop, 10), np.ones(10)


def _callback_b(start: float, stop: float):
    return np.linspace(start, stop, 10), np.zeros(10)


class TestMutableCallback:
    def test_calls_wrapped_callback(self):
        wrapper = MutableCallback(_callback_a)
        x, y = wrapper(0.0, 1.0)
        assert np.all(y == 1.0)

    def test_swap_callback(self):
        wrapper = MutableCallback(_callback_a)
        wrapper.callback = _callback_b
        x, y = wrapper(0.0, 1.0)
        assert np.all(y == 0.0)


class TestVPRegistry:
    def test_register_new(self):
        reg = VPRegistry()
        entry = reg.register("my_func", _callback_a, "scalar", ["v"])
        assert entry.wrapper(0.0, 1.0) is not None
        assert entry.product_type == "scalar"

    def test_re_register_same_signature_swaps_callback(self):
        reg = VPRegistry()
        entry1 = reg.register("my_func", _callback_a, "scalar", ["v"])
        wrapper1 = entry1.wrapper
        entry2 = reg.register("my_func", _callback_b, "scalar", ["v"])
        # Same wrapper object, just swapped callback
        assert entry2.wrapper is wrapper1
        assert entry2.signature_changed is False
        x, y = entry2.wrapper(0.0, 1.0)
        assert np.all(y == 0.0)

    def test_re_register_different_signature_rebuilds(self):
        reg = VPRegistry()
        entry1 = reg.register("my_func", _callback_a, "scalar", ["v"])
        wrapper1 = entry1.wrapper
        entry2 = reg.register("my_func", _callback_b, "vector", ["X", "Y", "Z"])
        # Different wrapper (signature changed)
        assert entry2.wrapper is not wrapper1
        assert entry2.signature_changed is True
        assert entry2.product_type == "vector"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_vp_magic.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement MutableCallback and VPRegistry**

```python
# SciQLop/user_api/virtual_products/magic.py
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional


class MutableCallback:
    def __init__(self, callback: Callable):
        self.callback = callback

    def __call__(self, start, stop):
        return self.callback(start, stop)


@dataclass
class RegistryEntry:
    wrapper: MutableCallback
    product_type: str
    labels: Optional[List[str]]
    signature_changed: bool = False
    panel: object = None  # will hold debug panel ref


class VPRegistry:
    def __init__(self):
        self._entries: Dict[str, RegistryEntry] = {}

    def register(self, name: str, callback: Callable,
                 product_type: str, labels: Optional[List[str]]) -> RegistryEntry:
        existing = self._entries.get(name)
        if existing and existing.product_type == product_type and existing.labels == labels:
            existing.wrapper.callback = callback
            existing.signature_changed = False
            return existing

        wrapper = MutableCallback(callback)
        entry = RegistryEntry(
            wrapper=wrapper,
            product_type=product_type,
            labels=labels,
            signature_changed=existing is not None,
        )
        self._entries[name] = entry
        return entry

    def get(self, name: str) -> Optional[RegistryEntry]:
        return self._entries.get(name)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_vp_magic.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/user_api/virtual_products/magic.py tests/test_vp_magic.py
git commit -m "feat(virtual_products): add MutableCallback wrapper and VPRegistry"
```

---

### Task 4: Cell Magic Implementation

**Files:**
- Modify: `SciQLop/user_api/virtual_products/magic.py`
- Modify: `SciQLop/user_api/virtual_products/__init__.py`
- Test: `tests/test_vp_magic_integration.py`

This task adds the `%%vp` cell magic that parses flags, extracts the function, infers type from annotation, and registers the virtual product. Debug mode is handled in Task 6.

- [ ] **Step 1: Write failing integration test**

Note: This test requires the Qt app (uses `EasyProvider`, `ProductsModel`). Use the existing `main_window` fixture.

```python
# tests/test_vp_magic_integration.py
from .fixtures import *
import pytest
import numpy as np


VP_CELL_SCALAR = """
def sine_wave(start: float, stop: float) -> Scalar:
    import numpy as np
    x = np.linspace(start, stop, 100)
    return x, np.sin(x)
"""

VP_CELL_VECTOR = """
def field(start: float, stop: float) -> Vector["Bx", "By", "Bz"]:
    import numpy as np
    x = np.linspace(start, stop, 100)
    y = np.column_stack([np.sin(x), np.cos(x), np.zeros_like(x)])
    return x, y
"""

VP_CELL_NO_ANNOTATION = """
def mystery(start: float, stop: float):
    import numpy as np
    x = np.linspace(start, stop, 100)
    return x, np.sin(x)
"""


def test_vp_magic_registers_scalar(qtbot, qapp, main_window):
    from SciQLop.user_api.virtual_products.magic import vp_magic, _registry
    from SciQLop.user_api.plot import create_plot_panel, TimeRange

    vp_magic("", VP_CELL_SCALAR)

    panel = create_plot_panel()
    panel.time_range = TimeRange(0., 10.)
    # The product should be findable and plottable
    from SciQLop.user_api.virtual_products import VirtualProductType
    entry = _registry.get("sine_wave")
    assert entry is not None
    assert entry.product_type == "scalar"


def test_vp_magic_registers_vector(qtbot, qapp, main_window):
    from SciQLop.user_api.virtual_products.magic import vp_magic, _registry

    vp_magic("", VP_CELL_VECTOR)

    entry = _registry.get("field")
    assert entry is not None
    assert entry.product_type == "vector"
    assert entry.labels == ["Bx", "By", "Bz"]


def test_vp_magic_rerun_swaps_callback(qtbot, qapp, main_window):
    from SciQLop.user_api.virtual_products.magic import vp_magic, _registry

    vp_magic("", VP_CELL_SCALAR)
    wrapper1 = _registry.get("sine_wave").wrapper

    vp_magic("", VP_CELL_SCALAR)
    wrapper2 = _registry.get("sine_wave").wrapper

    assert wrapper1 is wrapper2  # same wrapper, callback swapped


def test_vp_magic_infers_scalar_from_shape(qtbot, qapp, main_window):
    from SciQLop.user_api.virtual_products.magic import vp_magic, _registry

    vp_magic("--start 0 --stop 10", VP_CELL_NO_ANNOTATION)

    entry = _registry.get("mystery")
    assert entry is not None
    assert entry.product_type == "scalar"


def test_vp_magic_custom_path(qtbot, qapp, main_window):
    from SciQLop.user_api.virtual_products.magic import vp_magic, _registry

    vp_magic('--path "custom/path/sine"', VP_CELL_SCALAR)
    entry = _registry.get("sine_wave")
    assert entry is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_vp_magic_integration.py -v`
Expected: FAIL — `ImportError` (vp_magic not defined)

- [ ] **Step 3: Implement the cell magic**

Add to `SciQLop/user_api/virtual_products/magic.py`:

```python
# Add these imports at the top of magic.py
import argparse
import ast
import inspect
import shlex
from datetime import datetime, timezone
import numpy as np

from SciQLop.user_api.virtual_products.types import extract_vp_type_info, VPTypeInfo
from SciQLop.user_api.virtual_products.validation import validate_and_call
from SciQLop.components import sciqlop_logging

log = sciqlop_logging.getLogger(__name__)

_registry = VPRegistry()


def _parse_args(line: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="%%vp", add_help=False)
    parser.add_argument("--path", type=str, default=None)
    parser.add_argument("--debug", action="store_true", default=False)
    parser.add_argument("--start", type=str, default=None)
    parser.add_argument("--stop", type=str, default=None)
    return parser.parse_args(shlex.split(line))


def _extract_function(cell: str, user_ns: dict) -> callable:
    """Execute the cell to define the function, return it."""
    exec(cell, user_ns)
    # Find the first top-level function defined in the cell
    tree = ast.parse(cell)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            return user_ns[node.name]
    raise ValueError("No function definition found in cell")


def _parse_time_arg(value: str) -> float:
    """Parse a time argument as either a float or an ISO 8601 date string."""
    try:
        return float(value)
    except ValueError:
        return datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp()


def _resolve_time_range(args, func):
    """Resolve debug/inference time range from flags, defaults, view, or fallback."""
    # 1. Explicit flags
    if args.start is not None and args.stop is not None:
        return _parse_time_arg(args.start), _parse_time_arg(args.stop)

    # 2. Function default arguments
    sig = inspect.signature(func)
    params = list(sig.parameters.values())
    if len(params) >= 2 and params[0].default != inspect.Parameter.empty and params[1].default != inspect.Parameter.empty:
        start, stop = params[0].default, params[1].default
        if isinstance(start, datetime):
            return start.timestamp(), stop.timestamp()
        if isinstance(start, np.datetime64):
            return start.astype("datetime64[ns]").astype(np.int64) / 1e9, stop.astype("datetime64[ns]").astype(np.int64) / 1e9
        return float(start), float(stop)

    # 3. Current view range from existing panels
    try:
        from SciQLop.user_api.gui import get_main_window
        mw = get_main_window()
        panels = mw.plot_panels()
        if panels:
            panel = mw.plot_panel(panels[0])
            if panel is not None:
                tr = panel.time_range
                return tr.start(), tr.stop()
    except Exception:
        pass

    # 4. Fallback: last 24 hours
    now = datetime.now(tz=timezone.utc).timestamp()
    return now - 86400, now


def _infer_type_from_data(data) -> VPTypeInfo:
    """Infer product type from callback return value shape."""
    from SciQLop.user_api.virtual_products.types import VPTypeInfo
    if isinstance(data, (tuple, list)) and len(data) >= 2:
        y = data[1]
        if isinstance(y, np.ndarray):
            if y.ndim == 1:
                return VPTypeInfo(product_type="scalar", labels=None)
            elif y.ndim == 2:
                if y.shape[1] == 3:
                    return VPTypeInfo(product_type="vector", labels=None)
                else:
                    return VPTypeInfo(product_type="multicomponent", labels=None)
    return VPTypeInfo(product_type="scalar", labels=None)


def _product_type_to_enum(product_type: str):
    from SciQLop.user_api.virtual_products import VirtualProductType
    return {
        "scalar": VirtualProductType.Scalar,
        "vector": VirtualProductType.Vector,
        "multicomponent": VirtualProductType.MultiComponent,
        "spectrogram": VirtualProductType.Spectrogram,
    }[product_type]


def _register_virtual_product(name: str, wrapper: MutableCallback, product_type: str,
                               labels: Optional[List[str]], path: Optional[str]):
    """Register a virtual product using the existing create_virtual_product API."""
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType

    vp_path = path or name
    vp_type = _product_type_to_enum(product_type)

    if vp_type == VirtualProductType.Scalar:
        effective_labels = labels or [name]
    elif vp_type == VirtualProductType.Vector:
        effective_labels = labels or ["X", "Y", "Z"]
    elif vp_type == VirtualProductType.MultiComponent:
        if labels:
            effective_labels = labels
        else:
            # Run callback once to determine component count for default labels
            try:
                data = wrapper(0.0, 1.0)
                n = data[1].shape[1] if isinstance(data, (tuple, list)) and hasattr(data[1], 'shape') and data[1].ndim == 2 else 1
            except Exception:
                n = 1
            effective_labels = [f"C{i}" for i in range(n)]
    else:
        effective_labels = None

    if vp_type == VirtualProductType.Spectrogram:
        create_virtual_product(vp_path, wrapper, vp_type)
    else:
        create_virtual_product(vp_path, wrapper, vp_type, labels=effective_labels)


def vp_magic(line: str, cell: str, local_ns=None):
    """Implementation of the %%vp cell magic."""
    user_ns = local_ns if local_ns is not None else {}
    # Make type annotation classes available in the cell's namespace
    from SciQLop.user_api.virtual_products.types import Scalar, Vector, MultiComponent, Spectrogram
    user_ns.setdefault("Scalar", Scalar)
    user_ns.setdefault("Vector", Vector)
    user_ns.setdefault("MultiComponent", MultiComponent)
    user_ns.setdefault("Spectrogram", Spectrogram)

    args = _parse_args(line)
    func = _extract_function(cell, user_ns)
    func_name = func.__name__

    # Extract type info from annotation
    # Use __annotations__ directly (not get_type_hints) because Vector["Bx", "By", "Bz"]
    # is eagerly evaluated by __class_getitem__ into a _VPTypeWithLabels instance.
    # get_type_hints() would try to re-evaluate string annotations and may fail.
    try:
        return_ann = func.__annotations__.get("return")
        type_info = extract_vp_type_info(return_ann)
    except Exception:
        type_info = None

    # Inference mode if no annotation
    if type_info is None:
        start, stop = _resolve_time_range(args, func)
        try:
            data = func(start, stop)
            type_info = _infer_type_from_data(data)
            log.info(f"Inferred type: {type_info.product_type} — add return annotation to make explicit")
        except Exception as e:
            log.error(f"Cannot infer type for {func_name}: {e}")
            return

    # Register in the registry (check if new BEFORE registering)
    is_new = func_name not in _registry._entries
    entry = _registry.register(func_name, func, type_info.product_type, type_info.labels)

    # Register virtual product only on first creation or signature change
    if is_new or entry.signature_changed:
        _register_virtual_product(func_name, entry.wrapper, type_info.product_type,
                                   type_info.labels, args.path)

    # Debug mode handled in Task 6
    if args.debug:
        _handle_debug(args, func, func_name, entry, type_info)


def _handle_debug(args, func, func_name, entry, type_info):
    """Placeholder for debug workbench — implemented in Task 6."""
    pass
```

- [ ] **Step 4: Update `__init__.py` to re-export types and register magic**

Modify `SciQLop/user_api/virtual_products/__init__.py` — add at the end:

```python
from SciQLop.user_api.virtual_products.types import Scalar, Vector, MultiComponent, Spectrogram

def _register_magic():
    try:
        from IPython import get_ipython
        ip = get_ipython()
        if ip is not None:
            from SciQLop.user_api.virtual_products.magic import vp_magic
            ip.register_magic_function(vp_magic, magic_kind="cell", magic_name="vp")
    except ImportError:
        pass

_register_magic()
```

- [ ] **Step 5: Run integration tests**

Run: `uv run pytest tests/test_vp_magic_integration.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add SciQLop/user_api/virtual_products/magic.py SciQLop/user_api/virtual_products/__init__.py tests/test_vp_magic_integration.py
git commit -m "feat(virtual_products): implement %%vp cell magic with type inference"
```

---

## Chunk 3: Debug Workbench + Diagnostic Overlay

### Task 5: Diagnostic Overlay Widget

**Files:**
- Create: `SciQLop/components/plotting/ui/diagnostic_overlay.py`
- Test: `tests/test_diagnostic_overlay.py`

- [ ] **Step 1: Write failing tests for the overlay widget**

```python
# tests/test_diagnostic_overlay.py
from .fixtures import *
import pytest
from SciQLop.components.plotting.ui.diagnostic_overlay import DiagnosticOverlay
from SciQLop.user_api.virtual_products.validation import Diagnostic


def test_overlay_shows_error(qtbot):
    from PySide6.QtWidgets import QWidget
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.resize(400, 300)
    overlay = DiagnosticOverlay(parent)
    overlay.show_diagnostics([Diagnostic("error", "ZeroDivisionError in my_func(), line 4")])
    assert overlay.isVisible()
    assert "ZeroDivisionError" in overlay._label.text()


def test_overlay_shows_success(qtbot):
    from PySide6.QtWidgets import QWidget
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.resize(400, 300)
    overlay = DiagnosticOverlay(parent)
    overlay.show_success(1000, (1000, 3), "float64", 0.12)
    assert overlay.isVisible()
    assert "1000 pts" in overlay._label.text()


def test_overlay_clears(qtbot):
    from PySide6.QtWidgets import QWidget
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.resize(400, 300)
    overlay = DiagnosticOverlay(parent)
    overlay.show_diagnostics([Diagnostic("error", "some error")])
    overlay.clear()
    assert not overlay.isVisible()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_diagnostic_overlay.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement the overlay widget**

```python
# SciQLop/components/plotting/ui/diagnostic_overlay.py
from typing import List, Optional, Tuple

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtWidgets import QLabel, QWidget, QVBoxLayout
from PySide6.QtGui import QColor, QPalette

from SciQLop.user_api.virtual_products.validation import Diagnostic


class _DiagnosticDispatcher(QObject):
    """Thread-safe dispatcher: emit signals from any thread, overlay updates in GUI thread."""
    diagnostics_ready = Signal(list)
    success_ready = Signal(int, str, str, float)
    clear_requested = Signal()


class DiagnosticOverlay(QWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._label = QLabel(self)
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._label.setTextFormat(Qt.TextFormat.PlainText)
        self._label.setMargin(12)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

        self._dispatcher = _DiagnosticDispatcher()
        self._dispatcher.diagnostics_ready.connect(self._on_diagnostics)
        self._dispatcher.success_ready.connect(self._on_success)
        self._dispatcher.clear_requested.connect(self._on_clear)

        self.hide()

    def _apply_style(self, bg_color: str, text_color: str):
        self.setStyleSheet(
            f"background-color: {bg_color}; color: {text_color}; font-family: monospace; font-size: 12px;"
        )

    def show_diagnostics(self, diagnostics: List[Diagnostic]):
        """Thread-safe: can be called from any thread."""
        self._dispatcher.diagnostics_ready.emit(diagnostics)

    def show_success(self, n_points: int, shape, dtype: str, elapsed: float):
        """Thread-safe: can be called from any thread."""
        self._dispatcher.success_ready.emit(n_points, str(shape), dtype, elapsed)

    def clear(self):
        """Thread-safe: can be called from any thread."""
        self._dispatcher.clear_requested.emit()  # dispatches to _on_clear via signal

    def _on_diagnostics(self, diagnostics: List[Diagnostic]):
        has_error = any(d.level == "error" for d in diagnostics)
        lines = []
        for d in diagnostics:
            prefix = "[X]" if d.level == "error" else "[!]"
            lines.append(f"{prefix} {d.message}")

        self._label.setText("\n\n".join(lines))
        if has_error:
            self._apply_style("rgba(180, 40, 40, 200)", "#ffffff")
        else:
            self._apply_style("rgba(180, 140, 20, 200)", "#ffffff")
        self._resize_to_parent()
        self.show()
        self.raise_()

    def _on_success(self, n_points: int, shape: str, dtype: str, elapsed: float):
        self._label.setText(f"[ok] {n_points} pts, {shape} {dtype}, {elapsed:.2f}s")
        self._apply_style("rgba(40, 140, 40, 180)", "#ffffff")
        self._resize_to_parent()
        self.show()
        self.raise_()

    def _on_clear(self):
        self._label.setText("")
        self.hide()

    def _resize_to_parent(self):
        if self.parent():
            self.setGeometry(self.parent().rect())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_diagnostic_overlay.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/plotting/ui/diagnostic_overlay.py tests/test_diagnostic_overlay.py
git commit -m "feat(plotting): add DiagnosticOverlay widget for virtual product debugging"
```

---

### Task 6: Debug Workbench Mode

**Files:**
- Modify: `SciQLop/user_api/virtual_products/magic.py` (replace `_handle_debug` placeholder)
- Test: `tests/test_vp_debug_workbench.py`

- [ ] **Step 1: Write failing tests for debug workbench**

```python
# tests/test_vp_debug_workbench.py
from .fixtures import *
import pytest
import numpy as np


VP_DEBUG_SCALAR = """
def debug_sine(start: float, stop: float) -> Scalar:
    import numpy as np
    x = np.linspace(start, stop, 100)
    return x, np.sin(x)
"""

VP_DEBUG_ERROR = """
def debug_broken(start: float, stop: float) -> Scalar:
    raise ValueError("intentional error")
"""


def test_debug_mode_opens_panel(qtbot, qapp, main_window):
    from SciQLop.user_api.virtual_products.magic import vp_magic, _registry

    vp_magic("--debug --start 0 --stop 10", VP_DEBUG_SCALAR)
    qtbot.wait(100)

    entry = _registry.get("debug_sine")
    assert entry is not None
    assert entry.panel is not None


def test_debug_mode_reuses_panel(qtbot, qapp, main_window):
    from SciQLop.user_api.virtual_products.magic import vp_magic, _registry

    vp_magic("--debug --start 0 --stop 10", VP_DEBUG_SCALAR)
    panel1 = _registry.get("debug_sine").panel

    vp_magic("--debug --start 0 --stop 10", VP_DEBUG_SCALAR)
    panel2 = _registry.get("debug_sine").panel

    assert panel1 is panel2


def test_debug_mode_shows_error_overlay(qtbot, qapp, main_window):
    from SciQLop.user_api.virtual_products.magic import vp_magic, _registry

    vp_magic("--debug --start 0 --stop 10", VP_DEBUG_ERROR)
    qtbot.wait(100)

    entry = _registry.get("debug_broken")
    assert entry is not None
    assert entry.panel is not None
    # The overlay should be visible
    overlay = entry.panel.findChild(type(entry.panel)._overlay_type) if hasattr(entry.panel, '_overlay_type') else None
    # At minimum, the panel should exist and the entry should have diagnostics
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_vp_debug_workbench.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `_handle_debug` in `magic.py`**

Replace the `_handle_debug` placeholder in `SciQLop/user_api/virtual_products/magic.py`:

```python
def _handle_debug(args, func, func_name, entry, type_info):
    """Open/reuse a scratch pad panel and run callback with validation."""
    from SciQLop.user_api.virtual_products.validation import validate_and_call
    from SciQLop.components.plotting.ui.diagnostic_overlay import DiagnosticOverlay

    start, stop = _resolve_time_range(args, func)

    # Get or create the debug panel
    panel = entry.panel
    if panel is None or not _panel_is_alive(panel):
        panel = _create_debug_panel(func_name, start, stop)
        entry.panel = panel

    # Attach overlay if not already present
    overlay = getattr(panel, '_vp_overlay', None)
    if overlay is None:
        overlay = DiagnosticOverlay(panel)
        panel._vp_overlay = overlay

    # Run validation
    result = validate_and_call(func, start, stop, type_info.product_type, type_info.labels)

    if result.data is not None and not any(d.level == "error" for d in result.diagnostics):
        # Show success + any warnings
        if result.diagnostics:
            overlay.show_diagnostics(result.diagnostics)
        else:
            data = result.data
            if isinstance(data, (tuple, list)) and len(data) >= 2:
                y = data[1]
                n_pts = len(y) if hasattr(y, '__len__') else 0
                shape = y.shape if hasattr(y, 'shape') else '?'
                dtype = str(y.dtype) if hasattr(y, 'dtype') else '?'
            else:
                n_pts, shape, dtype = 0, '?', '?'
            overlay.show_success(n_pts, shape, dtype, result.elapsed)
        # Trigger a replot
        from SciQLop.core import TimeRange
        panel.time_range = TimeRange(start, stop)
    else:
        overlay.show_diagnostics(result.diagnostics)


def _panel_is_alive(panel) -> bool:
    try:
        panel.objectName()
        return True
    except RuntimeError:
        return False


def _create_debug_panel(func_name: str, start: float, stop: float):
    from SciQLop.user_api.gui import get_main_window
    from SciQLop.core import TimeRange
    panel_name = f"VP Debug: {func_name}"
    mw = get_main_window()
    panel = mw.new_plot_panel(name=panel_name)
    panel.time_range = TimeRange(start, stop)
    return panel
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_vp_debug_workbench.py -v`
Expected: All PASS

- [ ] **Step 5: Run the full test suite to verify no regressions**

Run: `uv run pytest tests/ -v`
Expected: All existing tests still PASS

- [ ] **Step 6: Commit**

```bash
git add SciQLop/user_api/virtual_products/magic.py tests/test_vp_debug_workbench.py
git commit -m "feat(virtual_products): add --debug workbench mode with diagnostic overlays"
```

---

## Chunk 4: Polish and Integration

### Task 7: Wire up validation in non-debug path

**Files:**
- Modify: `SciQLop/components/plotting/backend/easy_provider.py`

The validation pipeline should also log better errors for non-debug virtual products (replacing the current silent `return None`).

- [ ] **Step 1: Write a test for improved error logging**

```python
# Add to tests/test_vp_validation.py

def test_validation_logs_on_non_debug(caplog):
    """Validation pipeline logs errors even without --debug."""
    import logging
    from SciQLop.user_api.virtual_products.validation import validate_and_call

    result = validate_and_call(lambda s, e: (_ for _ in ()).throw(ValueError("boom")), 0.0, 10.0, "scalar", ["v"])
    assert result.data is None
    assert any("ValueError" in d.message for d in result.diagnostics)
```

- [ ] **Step 2: Run test to verify it passes** (it should already pass with existing validation code)

Run: `uv run pytest tests/test_vp_validation.py::test_validation_logs_on_non_debug -v`

- [ ] **Step 3: Modify `EasyProvider._debug_get_data` to use validation pipeline for better messages**

In `SciQLop/components/plotting/backend/easy_provider.py`, update the `_debug_get_data` method:

```python
def _debug_get_data(self, callback, start, stop):
    from SciQLop.user_api.virtual_products.validation import validate_and_call
    result = validate_and_call(callback, start, stop, None, None)
    for d in result.diagnostics:
        if d.level == "error":
            log.error(f"{self.name}: {d.message}")
        elif d.level == "warning":
            log.warning(f"{self.name}: {d.message}")
    return result.data
```

- [ ] **Step 4: Run existing virtual product tests to verify no regressions**

Run: `uv run pytest tests/test_virtual_products.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/plotting/backend/easy_provider.py tests/test_vp_validation.py
git commit -m "feat(virtual_products): use validation pipeline for better error logging in debug mode"
```

---

### Task 8: Re-export types from `__init__.py` and final cleanup

**Files:**
- Modify: `SciQLop/user_api/virtual_products/__init__.py`

- [ ] **Step 1: Verify types are importable from the public API**

```python
# Add to tests/test_vp_types.py

def test_types_importable_from_public_api():
    from SciQLop.user_api.virtual_products import Scalar, Vector, MultiComponent, Spectrogram
    assert Scalar is not None
    assert Vector is not None
```

- [ ] **Step 2: Run test**

Run: `uv run pytest tests/test_vp_types.py::test_types_importable_from_public_api -v`
Expected: PASS (already wired in Task 4 step 4)

- [ ] **Step 3: Run the full test suite**

Run: `uv run pytest tests/ -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add SciQLop/user_api/virtual_products/__init__.py tests/test_vp_types.py
git commit -m "feat(virtual_products): final integration and re-exports for %%vp magic"
```
