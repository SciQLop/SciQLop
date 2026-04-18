# Parameterized Virtual Products ("Knobs") Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every data product (Python virtual products and provider-sourced templated parameters) a declarative set of runtime-tunable parameters ("knobs") that users edit per-graph from the UI and the notebook, with debounced live re-fetch.

**Architecture:** Extend `DataProvider` with `get_knobs(product)` and an optional `knobs=` argument on `get_data(...)`. Knob specs are dataclasses introspected from `Annotated[T, Knob(...)]` callback kwargs or a Pydantic model. The Speasy plugin walks the inventory's generic `ArgumentListIndex` / `ArgumentIndex` (no AMDA-specific code). A new graph-side `knob_values` dict, threaded through the request pipeline (and into the cache key), drives live re-fetch. UI is a collapsible inspector section + collapsible info-badge overlay; debug plots preserve knob values across cell re-runs and offer an optional ipywidgets strip when the frontend supports it.

**Tech Stack:** Python 3.11+, PySide6 (`QSpinBox`, `QDoubleSpinBox`, `QComboBox`, `QCheckBox`, `QLineEdit`, `QFormLayout`, `QTimer`), Pydantic v2, SciQLopPlots overlay API, speasy `SpeasyIndex`/`ArgumentIndex`, pytest + pytest-qt + pytest-xvfb, ipywidgets (best-effort).

---

## Pre-flight checklist (do once, before Task 1)

- [ ] **Step 1: Confirm branch is `feat/plot-api-extensions`**

```bash
git rev-parse --abbrev-ref HEAD
```

Expected: `feat/plot-api-extensions`

- [ ] **Step 2: Confirm no working-tree changes block testing**

```bash
git status --short
```

Expected: spec file `docs/superpowers/specs/2026-04-18-parameterized-virtual-products-design.md` already committed; only summary working-tree changes (`uv.lock`, plan-related additions). Untracked `.claude/`, `.flatpak-builder/`, `docs/screenshots/output/`, `squashfs-root/`, `test-reports/` are expected dev artifacts and can be ignored.

- [ ] **Step 3: Verify the test suite is green before starting**

```bash
uv run pytest -q tests/test_vp_magic.py tests/test_vp_types.py tests/test_vp_validation.py tests/test_vp_debug_layout.py tests/test_settings_entry.py
```

Expected: all pass. (We don't run the full suite here — just the modules we are about to touch indirectly.)

If any of those fail before our work, stop and fix the regression before continuing.

---

## File map — where new code goes

**New files (created during the plan):**

- `SciQLop/user_api/knobs/__init__.py` — re-exports
- `SciQLop/user_api/knobs/specs.py` — `KnobSpec`, `IntKnob`, `FloatKnob`, `BoolKnob`, `ChoiceKnob`, `StringKnob`
- `SciQLop/user_api/knobs/marker.py` — `Knob(...)` Annotated marker
- `SciQLop/user_api/knobs/introspection.py` — callback → `list[KnobSpec]`
- `SciQLop/user_api/knobs/values.py` — validate / coerce / canonical_hash
- `SciQLop/user_api/virtual_products/ipywidgets_binding.py` — best-effort widget strip
- `SciQLop/components/plotting/ui/knob_inspector/__init__.py` — re-exports
- `SciQLop/components/plotting/ui/knob_inspector/section.py` — `KnobsSection` widget
- `SciQLop/components/plotting/ui/knob_inspector/delegates.py` — knob-spec → widget factory
- `SciQLop/components/plotting/ui/knob_inspector/badge.py` — info-badge overlay
- `SciQLop/components/plotting/backend/graph_knobs.py` — `GraphKnobState` + signal
- `SciQLop/components/plotting/backend/knob_hint_settings.py` — `ConfigEntry` for one-time hint dismissal
- All matching tests under `tests/test_knobs/`, `tests/test_virtual_products/`, `tests/test_plotting/`, `tests/test_speasy_provider/`

**Modified files:**

- `SciQLop/components/plotting/backend/data_provider.py`
- `SciQLop/components/plotting/backend/easy_provider.py`
- `SciQLop/user_api/virtual_products/__init__.py`
- `SciQLop/user_api/virtual_products/registry.py`
- `SciQLop/user_api/virtual_products/magic.py`
- `SciQLop/user_api/virtual_products/debug.py`
- `SciQLop/components/plotting/ui/time_sync_panel.py`
- `SciQLop/plugins/speasy_provider/speasy_provider.py`

---

## Chunk 1 — Knob specs, marker, value layer (pure Python, no SciQLop deps)

Goal: stand up the `SciQLop/user_api/knobs/` package — frozen dataclasses, the `Knob` Annotated marker, validation, canonical hashing. Zero Qt or SciQLop imports.

### Task 1: Create the knob spec dataclasses

**Files:**
- Create: `SciQLop/user_api/knobs/specs.py`
- Test: `tests/test_knobs/__init__.py`, `tests/test_knobs/test_specs.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_knobs/__init__.py` (empty), then `tests/test_knobs/test_specs.py`:

```python
from SciQLop.user_api.knobs.specs import (
    KnobSpec, IntKnob, FloatKnob, BoolKnob, ChoiceKnob, StringKnob,
)


def test_intknob_defaults():
    k = IntKnob(name="fft_size", default=256, min=64, max=4096, step=64,
                label="FFT size", unit="samples")
    assert k.name == "fft_size"
    assert k.default == 256
    assert k.min == 64 and k.max == 4096 and k.step == 64
    assert k.label == "FFT size" and k.unit == "samples"
    assert k.apply == "live"


def test_floatknob_defaults():
    k = FloatKnob(name="thr", default=0.5, min=0.0, max=1.0, step=0.01)
    assert k.default == 0.5 and k.step == 0.01


def test_boolknob_defaults():
    k = BoolKnob(name="cache", default=True)
    assert k.default is True


def test_choiceknob_pairs():
    k = ChoiceKnob(name="window", default="hann",
                   choices=(("Hann", "hann"), ("Hamming", "hamming")))
    assert k.choices[0] == ("Hann", "hann")
    assert k.default == "hann"


def test_stringknob_pattern():
    k = StringKnob(name="label", default="x", pattern=r"^[a-z]+$")
    assert k.pattern == r"^[a-z]+$"


def test_knobspec_is_frozen():
    import dataclasses
    k = IntKnob(name="x", default=0)
    try:
        k.default = 1
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("KnobSpec should be frozen")


def test_apply_field_round_trip():
    k = IntKnob(name="x", default=0, apply="manual")
    assert k.apply == "manual"
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/test_knobs/test_specs.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'SciQLop.user_api.knobs'`.

- [ ] **Step 3: Create the package and write the specs module**

Create `SciQLop/user_api/knobs/__init__.py` (empty for now — Task 4 fills it). Then `SciQLop/user_api/knobs/specs.py`:

```python
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class KnobSpec:
    name: str
    label: str = ""
    unit: str = ""
    description: str = ""
    apply: Literal["live", "manual"] = "live"


@dataclass(frozen=True, slots=True)
class IntKnob(KnobSpec):
    default: int = 0
    min: int | None = None
    max: int | None = None
    step: int = 1


@dataclass(frozen=True, slots=True)
class FloatKnob(KnobSpec):
    default: float = 0.0
    min: float | None = None
    max: float | None = None
    step: float = 0.01


@dataclass(frozen=True, slots=True)
class BoolKnob(KnobSpec):
    default: bool = False


@dataclass(frozen=True, slots=True)
class ChoiceKnob(KnobSpec):
    default: Any = None
    choices: tuple[tuple[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class StringKnob(KnobSpec):
    default: str = ""
    pattern: str = ""
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run pytest tests/test_knobs/test_specs.py -v
```

Expected: 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/user_api/knobs/__init__.py SciQLop/user_api/knobs/specs.py tests/test_knobs/__init__.py tests/test_knobs/test_specs.py
git commit -m "$(cat <<'EOF'
feat(user_api/knobs): add KnobSpec dataclass hierarchy

Frozen-dataclass spec types (Int/Float/Bool/Choice/String) shared by
introspection, validation, request pipeline and inspector UI.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Add the `Knob(...)` Annotated marker

**Files:**
- Create: `SciQLop/user_api/knobs/marker.py`
- Test: `tests/test_knobs/test_marker.py`

- [ ] **Step 1: Write the failing test**

```python
from typing import Annotated, get_type_hints, get_args

from SciQLop.user_api.knobs.marker import Knob


def test_knob_marker_carries_metadata():
    m = Knob(min=0, max=10, step=2, label="Threshold",
             unit="V", description="d", apply="manual",
             choices=[("Hann", "hann")], pattern=r"^x$")
    assert m.min == 0 and m.max == 10 and m.step == 2
    assert m.label == "Threshold" and m.unit == "V"
    assert m.description == "d" and m.apply == "manual"
    assert m.choices == [("Hann", "hann")]
    assert m.pattern == r"^x$"


def test_knob_defaults_are_none_or_empty():
    m = Knob()
    assert m.min is None and m.max is None and m.step is None
    assert m.label == "" and m.unit == "" and m.description == ""
    assert m.apply == "live"
    assert m.choices is None and m.pattern == ""


def test_knob_survives_annotated_round_trip():
    def f(x: Annotated[int, Knob(min=0, max=5, label="X")] = 1) -> None: ...
    hints = get_type_hints(f, include_extras=True)
    args = get_args(hints["x"])
    assert args[0] is int
    marker = next(a for a in args[1:] if isinstance(a, Knob))
    assert marker.min == 0 and marker.max == 5 and marker.label == "X"
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/test_knobs/test_marker.py -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement the marker**

`SciQLop/user_api/knobs/marker.py`:

```python
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class Knob:
    min: Any = None
    max: Any = None
    step: Any = None
    label: str = ""
    unit: str = ""
    description: str = ""
    apply: Literal["live", "manual"] = "live"
    choices: Any = None
    pattern: str = ""
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run pytest tests/test_knobs/test_marker.py -v
```

Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/user_api/knobs/marker.py tests/test_knobs/test_marker.py
git commit -m "$(cat <<'EOF'
feat(user_api/knobs): add Knob() Annotated metadata marker

Carries optional UI hints used by introspection.py to refine
type-derived KnobSpec subclasses.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Add value validation and canonical hashing

**Files:**
- Create: `SciQLop/user_api/knobs/values.py`
- Test: `tests/test_knobs/test_values.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest

from SciQLop.user_api.knobs.specs import (
    IntKnob, FloatKnob, BoolKnob, ChoiceKnob, StringKnob,
)
from SciQLop.user_api.knobs.values import (
    coerce_value, validate_dict, canonical_hash, defaults_for,
)


SPECS = [
    IntKnob(name="fft", default=256, min=64, max=4096, step=64),
    FloatKnob(name="thr", default=0.5, min=0.0, max=1.0, step=0.01),
    BoolKnob(name="cache", default=False),
    ChoiceKnob(name="window", default="hann",
               choices=(("Hann", "hann"), ("Hamming", "hamming"))),
    StringKnob(name="label", default="x", pattern=r"^[a-z]+$"),
]


def test_defaults_for():
    assert defaults_for(SPECS) == {
        "fft": 256, "thr": 0.5, "cache": False,
        "window": "hann", "label": "x",
    }


def test_coerce_int_clamps_and_steps():
    spec = IntKnob(name="x", default=0, min=64, max=4096, step=64)
    assert coerce_value(spec, "128") == 128
    assert coerce_value(spec, 5000) == 4096  # clamp high
    assert coerce_value(spec, 10) == 64       # clamp low
    assert coerce_value(spec, 100) == 128     # snap to step (round)


def test_coerce_float_clamps_no_step_snap():
    spec = FloatKnob(name="x", default=0.5, min=0.0, max=1.0, step=0.01)
    assert coerce_value(spec, 1.5) == 1.0
    assert coerce_value(spec, "0.7") == 0.7


def test_coerce_choice_membership():
    spec = ChoiceKnob(name="w", default="hann",
                      choices=(("Hann", "hann"), ("Hamming", "hamming")))
    assert coerce_value(spec, "hamming") == "hamming"
    with pytest.raises(ValueError):
        coerce_value(spec, "rect")


def test_coerce_string_pattern():
    spec = StringKnob(name="s", default="x", pattern=r"^[a-z]+$")
    assert coerce_value(spec, "abc") == "abc"
    with pytest.raises(ValueError):
        coerce_value(spec, "ABC")


def test_coerce_bool():
    spec = BoolKnob(name="b", default=False)
    assert coerce_value(spec, "true") is True
    assert coerce_value(spec, 0) is False
    assert coerce_value(spec, True) is True


def test_validate_dict_load_rules():
    in_values = {"fft": 128, "thr": 0.7, "cache": True,
                 "window": "hamming", "label": "abc",
                 "removed_knob": 42}
    out = validate_dict(SPECS, in_values)
    assert "removed_knob" not in out
    assert out["fft"] == 128
    assert out["thr"] == 0.7


def test_validate_dict_missing_uses_defaults():
    out = validate_dict(SPECS, {"fft": 128})
    assert out == {"fft": 128, "thr": 0.5, "cache": False,
                   "window": "hann", "label": "x"}


def test_validate_dict_invalid_resets_to_default():
    out = validate_dict(SPECS, {"window": "rect"})
    assert out["window"] == "hann"


def test_canonical_hash_stable():
    a = canonical_hash({"a": 1, "b": 2.5})
    b = canonical_hash({"b": 2.5, "a": 1})
    assert a == b


def test_canonical_hash_none_sentinel():
    assert canonical_hash(None) == canonical_hash({})


def test_canonical_hash_float_precision():
    a = canonical_hash({"x": 0.1 + 0.2})
    b = canonical_hash({"x": 0.3})
    assert a == b
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/test_knobs/test_values.py -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement validation and hashing**

`SciQLop/user_api/knobs/values.py`:

```python
import hashlib
import json
import re
from typing import Any, Iterable

from SciQLop.user_api.knobs.specs import (
    KnobSpec, IntKnob, FloatKnob, BoolKnob, ChoiceKnob, StringKnob,
)


def defaults_for(specs: Iterable[KnobSpec]) -> dict[str, Any]:
    return {s.name: s.default for s in specs}


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def _clamp(v, lo, hi):
    if lo is not None and v < lo:
        return lo
    if hi is not None and v > hi:
        return hi
    return v


def coerce_value(spec: KnobSpec, value: Any) -> Any:
    if isinstance(spec, IntKnob):
        v = int(value)
        v = _clamp(v, spec.min, spec.max)
        if spec.step and spec.step > 0 and spec.min is not None:
            offset = v - spec.min
            v = spec.min + round(offset / spec.step) * spec.step
            v = _clamp(v, spec.min, spec.max)
        return v
    if isinstance(spec, FloatKnob):
        v = float(value)
        return _clamp(v, spec.min, spec.max)
    if isinstance(spec, BoolKnob):
        return _to_bool(value)
    if isinstance(spec, ChoiceKnob):
        valid = {pair[1] for pair in spec.choices}
        if value not in valid:
            raise ValueError(f"{value!r} not in {sorted(valid)!r}")
        return value
    if isinstance(spec, StringKnob):
        s = str(value)
        if spec.pattern and not re.match(spec.pattern, s):
            raise ValueError(f"{s!r} does not match {spec.pattern!r}")
        return s
    raise TypeError(f"Unknown spec type: {type(spec).__name__}")


def validate_dict(specs: Iterable[KnobSpec], values: dict[str, Any]) -> dict[str, Any]:
    by_name = {s.name: s for s in specs}
    out: dict[str, Any] = {}
    for name, spec in by_name.items():
        if name in values:
            try:
                out[name] = coerce_value(spec, values[name])
            except (ValueError, TypeError):
                out[name] = spec.default
        else:
            out[name] = spec.default
    return out


def _canonicalize(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 9)
    if isinstance(value, dict):
        return {k: _canonicalize(value[k]) for k in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonicalize(v) for v in value]
    return value


def canonical_hash(values: dict[str, Any] | None) -> str:
    payload = _canonicalize(values or {})
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha1(blob).hexdigest()
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run pytest tests/test_knobs/test_values.py -v
```

Expected: 11 PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/user_api/knobs/values.py tests/test_knobs/test_values.py
git commit -m "$(cat <<'EOF'
feat(user_api/knobs): add value coercion and canonical hashing

coerce_value clamps/snaps per spec; validate_dict enforces load-rules
(known-and-valid kept, unknown dropped, missing → default); canonical_hash
gives a stable cache key tolerant to dict ordering and float jitter.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Add introspection (callback → list[KnobSpec])

**Files:**
- Create: `SciQLop/user_api/knobs/introspection.py`
- Modify: `SciQLop/user_api/knobs/__init__.py` — re-exports
- Test: `tests/test_knobs/test_introspection.py`

- [ ] **Step 1: Write the failing test**

```python
from typing import Annotated, Literal

import pytest
from pydantic import BaseModel, Field

from SciQLop.user_api.knobs import (
    Knob, IntKnob, FloatKnob, BoolKnob, ChoiceKnob, StringKnob,
)
from SciQLop.user_api.knobs.introspection import (
    extract_specs_from_callback, extract_specs_from_model,
)


def test_extract_int_with_marker():
    def f(start: float, stop: float,
          fft: Annotated[int, Knob(min=64, max=4096, step=64,
                                   label="FFT")] = 256) -> None: ...
    specs = extract_specs_from_callback(f)
    assert len(specs) == 1
    s = specs[0]
    assert isinstance(s, IntKnob)
    assert s.name == "fft" and s.default == 256
    assert s.min == 64 and s.max == 4096 and s.step == 64
    assert s.label == "FFT"


def test_extract_float_with_marker():
    def f(start, stop,
          thr: Annotated[float, Knob(min=0.0, max=1.0, step=0.01)] = 0.5):
        ...
    s = extract_specs_from_callback(f)[0]
    assert isinstance(s, FloatKnob)
    assert s.min == 0.0 and s.max == 1.0 and s.step == 0.01


def test_extract_bool_no_marker():
    def f(start, stop, cache: bool = True): ...
    s = extract_specs_from_callback(f)[0]
    assert isinstance(s, BoolKnob)
    assert s.default is True


def test_extract_literal_becomes_choice():
    def f(start, stop,
          window: Literal["hann", "hamming", "blackman"] = "hann"): ...
    s = extract_specs_from_callback(f)[0]
    assert isinstance(s, ChoiceKnob)
    assert s.default == "hann"
    assert s.choices == (("hann", "hann"), ("hamming", "hamming"),
                         ("blackman", "blackman"))


def test_extract_string_with_pattern():
    def f(start, stop,
          name: Annotated[str, Knob(pattern=r"^[a-z]+$")] = "x"): ...
    s = extract_specs_from_callback(f)[0]
    assert isinstance(s, StringKnob)
    assert s.pattern == r"^[a-z]+$"


def test_no_default_means_no_knob():
    def f(start, stop, x: int): ...
    assert extract_specs_from_callback(f) == []


def test_reserved_kwargs_skipped():
    def f(start, stop, ff: int = 1): ...
    assert {s.name for s in extract_specs_from_callback(f)} == {"ff"}


def test_varargs_warns_returns_empty(caplog):
    def f(start, stop, *args, **kwargs): ...
    import logging
    caplog.set_level(logging.WARNING)
    assert extract_specs_from_callback(f) == []


def test_choice_with_display_pairs():
    def f(start, stop,
          window: Annotated[str, Knob(choices=[("Hann", "hann"),
                                               ("Hamming", "hamming")])] = "hann"): ...
    s = extract_specs_from_callback(f)[0]
    assert isinstance(s, ChoiceKnob)
    assert s.choices == (("Hann", "hann"), ("Hamming", "hamming"))


def test_pydantic_model_to_specs():
    class K(BaseModel):
        fft: int = Field(256, ge=64, le=4096, multiple_of=64)
        window: Literal["hann", "hamming"] = "hann"
        thr: float = Field(0.5, ge=0.0, le=1.0,
                           json_schema_extra={"knob": {"label": "Threshold",
                                                       "unit": "V"}})

    specs = extract_specs_from_model(K)
    by_name = {s.name: s for s in specs}
    assert isinstance(by_name["fft"], IntKnob)
    assert by_name["fft"].min == 64 and by_name["fft"].max == 4096
    assert by_name["fft"].step == 64
    assert isinstance(by_name["window"], ChoiceKnob)
    assert by_name["window"].choices == (("hann", "hann"),
                                         ("hamming", "hamming"))
    assert isinstance(by_name["thr"], FloatKnob)
    assert by_name["thr"].label == "Threshold"
    assert by_name["thr"].unit == "V"
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/test_knobs/test_introspection.py -v
```

Expected: FAIL with `ImportError` on `extract_specs_from_callback`.

- [ ] **Step 3: Implement introspection**

`SciQLop/user_api/knobs/introspection.py`:

```python
import inspect
import logging
from typing import (Annotated, Any, Iterable, Literal, get_args, get_origin,
                    get_type_hints)

from SciQLop.user_api.knobs.marker import Knob
from SciQLop.user_api.knobs.specs import (
    BoolKnob, ChoiceKnob, FloatKnob, IntKnob, KnobSpec, StringKnob,
)

log = logging.getLogger(__name__)

_RESERVED = {"start", "stop"}


def _split_annotation(annot):
    if get_origin(annot) is Annotated:
        args = get_args(annot)
        return args[0], [a for a in args[1:] if isinstance(a, Knob)]
    return annot, []


def _normalize_choices(raw) -> tuple[tuple[str, Any], ...]:
    if raw is None:
        return ()
    out = []
    for item in raw:
        if isinstance(item, tuple) and len(item) == 2:
            out.append((str(item[0]), item[1]))
        else:
            out.append((str(item), item))
    return tuple(out)


def _kwargs_meta(marker: Knob | None) -> dict:
    if marker is None:
        return {}
    return {"label": marker.label, "unit": marker.unit,
            "description": marker.description, "apply": marker.apply}


def _spec_from_kwarg(name: str, annot, default: Any) -> KnobSpec | None:
    base, markers = _split_annotation(annot)
    marker = markers[0] if markers else None

    if get_origin(base) is Literal:
        choices = _normalize_choices(get_args(base))
        return ChoiceKnob(name=name, default=default, choices=choices,
                          **_kwargs_meta(marker))

    if marker is not None and marker.choices:
        return ChoiceKnob(name=name, default=default,
                          choices=_normalize_choices(marker.choices),
                          **_kwargs_meta(marker))

    if base is bool or isinstance(default, bool):
        return BoolKnob(name=name, default=bool(default),
                        **_kwargs_meta(marker))

    if base is int or (base is inspect.Parameter.empty and isinstance(default, int)
                       and not isinstance(default, bool)):
        return IntKnob(name=name, default=int(default),
                       min=marker.min if marker else None,
                       max=marker.max if marker else None,
                       step=marker.step if marker and marker.step is not None else 1,
                       **_kwargs_meta(marker))

    if base is float or (base is inspect.Parameter.empty and isinstance(default, float)):
        return FloatKnob(name=name, default=float(default),
                         min=marker.min if marker else None,
                         max=marker.max if marker else None,
                         step=marker.step if marker and marker.step is not None else 0.01,
                         **_kwargs_meta(marker))

    if base is str or isinstance(default, str):
        return StringKnob(name=name, default=str(default),
                          pattern=marker.pattern if marker else "",
                          **_kwargs_meta(marker))

    return None


def extract_specs_from_callback(callback) -> list[KnobSpec]:
    sig = inspect.signature(callback)
    if any(p.kind in (inspect.Parameter.VAR_POSITIONAL,
                      inspect.Parameter.VAR_KEYWORD)
           for p in sig.parameters.values()):
        log.warning("%r uses *args/**kwargs; knobs disabled",
                    getattr(callback, "__name__", callback))
        return []

    try:
        hints = get_type_hints(callback, include_extras=True)
    except Exception:
        hints = {}

    specs: list[KnobSpec] = []
    for pname, param in sig.parameters.items():
        if pname in _RESERVED:
            continue
        if param.default is inspect.Parameter.empty:
            continue
        annot = hints.get(pname, param.annotation)
        spec = _spec_from_kwarg(pname, annot, param.default)
        if spec is not None:
            specs.append(spec)
    return specs


def _model_field_to_spec(name: str, field) -> KnobSpec | None:
    annot = field.annotation
    extra = (field.json_schema_extra or {})
    knob_extra = extra.get("knob", {}) if isinstance(extra, dict) else {}
    meta = {"label": knob_extra.get("label", ""),
            "unit": knob_extra.get("unit", ""),
            "description": knob_extra.get("description", ""),
            "apply": knob_extra.get("apply", "live")}

    if get_origin(annot) is Literal:
        choices = _normalize_choices(get_args(annot))
        return ChoiceKnob(name=name, default=field.default, choices=choices, **meta)

    metadata = list(getattr(field, "metadata", []) or [])
    ge = next((m.ge for m in metadata if hasattr(m, "ge")), None)
    le = next((m.le for m in metadata if hasattr(m, "le")), None)
    multiple_of = next((m.multiple_of for m in metadata
                        if hasattr(m, "multiple_of")), None)
    pattern = next((m.pattern for m in metadata if hasattr(m, "pattern")), None)

    if annot is bool:
        return BoolKnob(name=name, default=bool(field.default), **meta)
    if annot is int:
        return IntKnob(name=name, default=int(field.default),
                       min=ge, max=le, step=multiple_of or 1, **meta)
    if annot is float:
        return FloatKnob(name=name, default=float(field.default),
                         min=ge, max=le, step=multiple_of or 0.01, **meta)
    if annot is str:
        return StringKnob(name=name, default=str(field.default),
                          pattern=pattern or "", **meta)
    return None


def extract_specs_from_model(model_cls) -> list[KnobSpec]:
    specs = []
    for name, field in model_cls.model_fields.items():
        spec = _model_field_to_spec(name, field)
        if spec is not None:
            specs.append(spec)
    return specs
```

Now write `SciQLop/user_api/knobs/__init__.py`:

```python
from SciQLop.user_api.knobs.marker import Knob
from SciQLop.user_api.knobs.specs import (
    KnobSpec, IntKnob, FloatKnob, BoolKnob, ChoiceKnob, StringKnob,
)
from SciQLop.user_api.knobs.values import (
    coerce_value, validate_dict, canonical_hash, defaults_for,
)
from SciQLop.user_api.knobs.introspection import (
    extract_specs_from_callback, extract_specs_from_model,
)

__all__ = [
    "Knob",
    "KnobSpec", "IntKnob", "FloatKnob", "BoolKnob", "ChoiceKnob", "StringKnob",
    "coerce_value", "validate_dict", "canonical_hash", "defaults_for",
    "extract_specs_from_callback", "extract_specs_from_model",
]
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run pytest tests/test_knobs/test_introspection.py -v
```

Expected: 10 PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/user_api/knobs/introspection.py SciQLop/user_api/knobs/__init__.py tests/test_knobs/test_introspection.py
git commit -m "$(cat <<'EOF'
feat(user_api/knobs): introspect callbacks and Pydantic models

extract_specs_from_callback handles Annotated[T, Knob(...)] kwargs and
Literal[...] auto-mapping; extract_specs_from_model maps pydantic
Field constraints (ge/le/multiple_of/pattern + json_schema_extra.knob)
to the same KnobSpec subclasses. Downstream code never branches on
declaration style.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Chunk 2 — DataProvider contract + EasyProvider wiring

Goal: make `DataProvider.get_knobs(...)` part of the contract, accept a `knobs=` kwarg through the `_get_data`/`get_data` chain, and wire `EasyProvider` (the engine behind every Python VP) to pass kwargs into the user callback. All changes additive — `knobs=None` callers are byte-identical to today's behaviour.

### Task 5: Extend the DataProvider base class

**Files:**
- Modify: `SciQLop/components/plotting/backend/data_provider.py`
- Test: `tests/test_plotting/__init__.py`, `tests/test_plotting/test_data_provider_knobs.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_plotting/__init__.py` (empty), then `tests/test_plotting/test_data_provider_knobs.py`:

```python
from SciQLop.components.plotting.backend.data_provider import DataProvider


class _Toy(DataProvider):
    def __init__(self):
        super().__init__(name="toy")
        self.last_knobs = "unset"

    def get_data(self, product, start, stop, knobs=None):
        self.last_knobs = knobs
        return None


def test_default_get_knobs_returns_empty_list():
    p = DataProvider(name="empty-knobs")
    assert p.get_knobs("any") == []


def test_get_data_forwards_knobs():
    p = _Toy()
    p._get_data("prod", 0.0, 1.0, knobs={"fft": 256})
    assert p.last_knobs == {"fft": 256}


def test_get_data_default_knobs_is_none():
    p = _Toy()
    p._get_data("prod", 0.0, 1.0)
    assert p.last_knobs is None
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/test_plotting/test_data_provider_knobs.py -v
```

Expected: FAIL on `get_knobs` (AttributeError) and `_get_data` rejecting `knobs=` kwarg.

- [ ] **Step 3: Extend DataProvider**

In `SciQLop/components/plotting/backend/data_provider.py`, change the class to:

```python
class DataProvider:
    def __init__(self, name: str, data_order: DataOrder = DataOrder.X_FIRST, cacheable: bool = False):
        global providers  # noqa: F824
        providers[name] = self
        self._name = name
        self._data_order = data_order
        self._cacheable = cacheable

    @property
    def name(self) -> str:
        return self._name

    @property
    def data_order(self) -> DataOrder:
        return self._data_order

    @property
    def cacheable(self) -> bool:
        return self._cacheable

    def labels(self, node) -> List[str]:
        pass

    def graph_type(self, node) -> GraphType:
        pass

    def plot_hints(self, node) -> PlotHints:
        return PlotHints()

    def plot_hints_from_variable(self, node, variable) -> PlotHints:
        return PlotHints()

    def get_knobs(self, product) -> list:
        """Return a list of KnobSpec for this product (empty = not parameterized)."""
        return []

    def _get_data(self, node, start, stop, on_variable=None, knobs=None) -> Union[
        List[np.ndarray], Tuple[np.ndarray, np.ndarray], Tuple[np.ndarray, np.ndarray, np.ndarray]]:
        try:
            v = self.get_data(node, start, stop, knobs=knobs) if knobs is not None \
                else self.get_data(node, start, stop)
            if v is not None and on_variable is not None:
                try:
                    on_variable(v)
                except Exception:
                    log.debug("on_variable callback failed", exc_info=True)
            if v is None:
                return []
            if isinstance(v, list) or isinstance(v, tuple):
                return v
            if not np.all(np.diff(v.time) >= 0):
                v = _sort_variable_by_time(v)
            time = datetime64_to_epoch(v.time)
            axes = _filter_axis_numeric_axes(v.axes[1:])
            if len(axes) == 0 or self.graph_type(node) in (GraphType.MultiLines, GraphType.SingleLine):
                return [time, _ensure_contiguous(v.values)]
            return [time, _ensure_contiguous(axes[0].values), _ensure_contiguous(v.values)]
        except Exception:
            log.error(
                f"Error getting data for {node} between {start} and {stop}: \n\nbacktrace: {traceback.format_exc()}")
            return []

    def get_data(self, node, start: float, stop: float, knobs=None) -> DataProviderReturnType:
        pass
```

The conditional `if knobs is not None` keeps backward compatibility with existing providers whose `get_data` doesn't accept `knobs=` yet (they'll be migrated in later tasks).

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run pytest tests/test_plotting/test_data_provider_knobs.py -v
```

Expected: 3 PASS.

- [ ] **Step 5: Verify no existing test regresses**

```bash
uv run pytest tests/test_backend_common.py tests/test_dsp_arrays.py tests/test_dsp_speasy.py -q
```

Expected: green (no behavioural change for existing providers).

- [ ] **Step 6: Commit**

```bash
git add SciQLop/components/plotting/backend/data_provider.py tests/test_plotting/__init__.py tests/test_plotting/test_data_provider_knobs.py
git commit -m "$(cat <<'EOF'
feat(plotting/backend): add knobs= kwarg to DataProvider

Adds DataProvider.get_knobs() (default []) and threads an optional
knobs= dict through _get_data → get_data. Backwards compatible: when
knobs is None, providers see the original (node, start, stop) signature.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Wire EasyProvider to expose and dispatch knobs

**Files:**
- Modify: `SciQLop/components/plotting/backend/easy_provider.py`
- Modify: `SciQLop/user_api/virtual_products/__init__.py` — accept `knobs_model=`
- Test: `tests/test_virtual_products/__init__.py`, `tests/test_virtual_products/test_knobs_easy_provider.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_virtual_products/__init__.py` (empty), then `tests/test_virtual_products/test_knobs_easy_provider.py`:

```python
from typing import Annotated, Literal

import numpy as np
import pytest
from pydantic import BaseModel, Field

from SciQLop.user_api.knobs import Knob, IntKnob, FloatKnob, ChoiceKnob


@pytest.fixture(autouse=True)
def _isolate_products(monkeypatch):
    from SciQLop.core.models import products
    monkeypatch.setattr(products, "add_node", lambda *a, **k: None)


def _make_easy_scalar(callback, knobs_model=None):
    from SciQLop.components.plotting.backend.easy_provider import EasyScalar
    p = EasyScalar(path=f"vp/{id(callback):x}",
                   get_data_callback=callback,
                   component_name="x",
                   metadata={})
    if knobs_model is not None:
        p._knobs_model = knobs_model
        p._knob_specs = []
        from SciQLop.user_api.knobs import extract_specs_from_model
        p._knob_specs = extract_specs_from_model(knobs_model)
    return p


def test_easyprovider_get_knobs_from_callback_kwargs():
    def f(start: float, stop: float,
          fft: Annotated[int, Knob(min=64, max=4096, step=64)] = 256,
          window: Literal["hann", "hamming"] = "hann"):
        n = 8
        return np.linspace(start, stop, n), np.zeros(n)
    p = _make_easy_scalar(f)
    specs = p.get_knobs("any")
    by_name = {s.name: s for s in specs}
    assert isinstance(by_name["fft"], IntKnob)
    assert isinstance(by_name["window"], ChoiceKnob)


def test_easyprovider_dispatches_kwargs_to_callback():
    seen = {}

    def f(start: float, stop: float,
          fft: Annotated[int, Knob(min=64, max=4096)] = 256):
        seen["fft"] = fft
        n = 4
        return np.linspace(start, stop, n), np.zeros(n)

    p = _make_easy_scalar(f)
    p.get_data(product=None, start=0.0, stop=1.0, knobs={"fft": 1024})
    assert seen["fft"] == 1024


def test_easyprovider_no_knobs_kwarg_is_byte_identical():
    seen = {}

    def f(start: float, stop: float):
        seen["called"] = True
        n = 4
        return np.linspace(start, stop, n), np.zeros(n)

    p = _make_easy_scalar(f)
    p.get_data(product=None, start=0.0, stop=1.0)
    assert seen["called"]


def test_easyprovider_pydantic_model_dispatch():
    class K(BaseModel):
        fft: int = Field(256, ge=64, le=4096)
        thr: float = Field(0.5, ge=0.0, le=1.0)

    seen = {}

    def f(start: float, stop: float, knobs: K) -> None:
        seen["fft"] = knobs.fft
        seen["thr"] = knobs.thr
        n = 4
        return np.linspace(start, stop, n), np.zeros(n)

    p = _make_easy_scalar(f, knobs_model=K)
    p._knobs_kwarg_name = "knobs"
    p.get_data(product=None, start=0.0, stop=1.0,
               knobs={"fft": 1024, "thr": 0.7})
    assert seen == {"fft": 1024, "thr": 0.7}
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/test_virtual_products/test_knobs_easy_provider.py -v
```

Expected: FAIL — `get_knobs` returns `[]`, `get_data` rejects `knobs=`.

- [ ] **Step 3: Modify EasyProvider**

In `SciQLop/components/plotting/backend/easy_provider.py`, replace `EasyProvider.__init__` and add knob fields plus update `get_data` and the subclasses' `get_data` overrides. The new `EasyProvider` body:

```python
class EasyProvider(DataProvider):
    def __init__(self, path, callback: VirtualProductCallback, parameter_type: ParameterType, metadata: dict,
                 data_order=DataOrder.Y_FIRST,
                 cacheable=False, debug=False,
                 knobs_model: Optional[type] = None,
                 knobs_kwarg_name: str = "knobs"):
        super(EasyProvider, self).__init__(name=make_simple_incr_name(_name_callable(callback)), data_order=data_order,
                                           cacheable=cacheable)
        self._path = path.split('/')
        product_name = self._path[-1]
        product_path = self._path[:-1]
        metadata.update(
            {"description": f"Virtual {parameter_type.name} product built from Python function: {self.name}",
             "stable_id": path})
        products.add_node(
            product_path,
            ProductsModelNode(product_name, self.name, metadata, ProductsModelNodeType.PARAMETER, parameter_type, "",
                              None)
        )
        self._callback = callback
        self._debug = debug
        self._knobs_model = knobs_model
        self._knobs_kwarg_name = knobs_kwarg_name
        self._knob_specs = self._compute_knob_specs(callback, knobs_model)

        stack = []
        arguments_type = _arguments_type(callback)
        match arguments_type:
            case ArgumentsType.Datetime:
                stack.append(lambda rng: _to_datetime(*rng))
            case ArgumentsType.Datetime64:
                stack.append(lambda rng: _to_datetime64(*rng))
            case ArgumentsType.Float:
                pass
            case ArgumentsType.Unknown:
                warnings.warn(f"""Can't determine arguments type for {self.name}, missing type hints, assuming float by default.
Please add type hints to the callback function to avoid this warning:
def {self.name}(start: float, stop: float) -> Optional[SpeasyVariable]:
    ...
            """)
        self._range_stack = stack

    @staticmethod
    def _compute_knob_specs(callback, knobs_model):
        from SciQLop.user_api.knobs import (
            extract_specs_from_callback, extract_specs_from_model,
        )
        if knobs_model is not None:
            return extract_specs_from_model(knobs_model)
        return extract_specs_from_callback(callback)

    def _refresh_knob_specs(self):
        self._knob_specs = self._compute_knob_specs(self._callback, self._knobs_model)

    def get_knobs(self, product) -> list:
        return list(self._knob_specs)

    def _apply_range(self, start, stop):
        rng = (start, stop)
        for fn in self._range_stack:
            rng = fn(rng)
        return rng

    def _invoke_callback(self, start, stop, knobs):
        rng = self._apply_range(start, stop)
        if self._knobs_model is not None:
            model = self._knobs_model(**(knobs or {}))
            kwargs = {self._knobs_kwarg_name: model}
        else:
            kwargs = dict(knobs or {})
        if self._debug:
            from SciQLop.user_api.virtual_products.validation import validate_and_call
            result = validate_and_call(self._callback, *rng, None, None, **kwargs)
            for d in result.diagnostics:
                if d.level == "error":
                    log.error(f"{self.name}: {d.message}")
                elif d.level == "warning":
                    log.warning(f"{self.name}: {d.message}")
            return result.data
        return self._callback(*rng, **kwargs)

    def get_data(self, product, start: float, stop: float, knobs=None) -> DataProviderReturnType:
        return self._invoke_callback(start, stop, knobs)

    @property
    def path(self):
        return self._path

    def labels(self, node) -> List[str]:
        return node.metadata().get("components", "").split(';')
```

Update each subclass's `get_data` to forward `knobs=`:

```python
class EasyScalar(EasyProvider):
    def __init__(self, path, get_data_callback, component_name, metadata,
                 data_order=DataOrder.Y_FIRST, cacheable=False, debug=False,
                 knobs_model=None, knobs_kwarg_name="knobs"):
        super().__init__(path=path, callback=get_data_callback,
                         parameter_type=ParameterType.Scalar,
                         metadata={**metadata, "components": component_name},
                         data_order=data_order, cacheable=cacheable, debug=debug,
                         knobs_model=knobs_model, knobs_kwarg_name=knobs_kwarg_name)
        self._columns = [component_name]

    def get_data(self, product, start, stop, knobs=None):
        res = self._invoke_callback(start, stop, knobs)
        if type(res) is SpeasyVariable:
            return res
        elif type(res) is tuple:
            x, y = res
            return SpeasyVariable(axes=[VariableTimeAxis(ensure_dt64(x))],
                                  values=DataContainer(np.ascontiguousarray(y)),
                                  columns=self._columns)
        return None
```

Apply the same pattern to `EasyVector`, `EasyMultiComponent`, `EasySpectrogram`: add `knobs_model=`, `knobs_kwarg_name=` to `__init__`, route to `super().__init__(...)`, swap `self._user_get_data(start, stop)` for `self._invoke_callback(start, stop, knobs)`. Remove the now-unused `_user_get_data` lambda and `_debug_get_data` method on `EasyProvider` (they are subsumed by `_invoke_callback`).

Also update `SciQLop/user_api/virtual_products/__init__.py` to thread `knobs_model=` through:

```python
class VirtualScalar(VirtualProduct):
    def __init__(self, path, callback, label, debug=False, cachable=False,
                 knobs_model=None, knobs_kwarg_name="knobs"):
        super().__init__(path, callback, VirtualProductType.Scalar)
        self._impl = _EasyScalar(path, callback, component_name=label, metadata={},
                                 debug=debug, cacheable=cachable,
                                 knobs_model=knobs_model, knobs_kwarg_name=knobs_kwarg_name)
```

Apply the same change to `VirtualVector`, `VirtualMultiComponent`, `VirtualSpectrogram`. Then update `create_virtual_product`:

```python
def create_virtual_product(path, callback, product_type, labels=None,
                           debug=False, cachable=False,
                           knobs_model=None, knobs_kwarg_name="knobs"):
    if product_type == VirtualProductType.Scalar:
        assert labels is not None and len(labels) == 1
        return VirtualScalar(path, callback, label=labels[0], debug=debug,
                             cachable=cachable, knobs_model=knobs_model,
                             knobs_kwarg_name=knobs_kwarg_name)
    elif product_type == VirtualProductType.Vector:
        assert labels is not None and len(labels) == 3
        return VirtualVector(path, callback, labels=labels, debug=debug,
                             cachable=cachable, knobs_model=knobs_model,
                             knobs_kwarg_name=knobs_kwarg_name)
    elif product_type == VirtualProductType.MultiComponent:
        assert labels is not None
        return VirtualMultiComponent(path, callback, labels=labels, debug=debug,
                                     cachable=cachable, knobs_model=knobs_model,
                                     knobs_kwarg_name=knobs_kwarg_name)
    elif product_type == VirtualProductType.Spectrogram:
        return VirtualSpectrogram(path, callback, debug=debug, cachable=cachable,
                                  knobs_model=knobs_model, knobs_kwarg_name=knobs_kwarg_name)
    return None
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run pytest tests/test_virtual_products/test_knobs_easy_provider.py -v
```

Expected: 4 PASS.

- [ ] **Step 5: Make sure existing VP tests still pass**

```bash
uv run pytest tests/test_vp_types.py tests/test_vp_validation.py tests/test_vp_magic.py tests/test_vp_debug_layout.py tests/test_wf_virtual_products.py -q
```

Expected: green. If `validate_and_call` is called with kwargs and rejects them, you'll need to update its signature in `SciQLop/user_api/virtual_products/validation.py` to accept `**kwargs` and forward them to the callback. Apply that fix and re-run.

- [ ] **Step 6: Commit**

```bash
git add SciQLop/components/plotting/backend/easy_provider.py SciQLop/user_api/virtual_products/__init__.py tests/test_virtual_products/__init__.py tests/test_virtual_products/test_knobs_easy_provider.py
# include validation.py only if you had to touch it
git diff --cached --stat
git commit -m "$(cat <<'EOF'
feat(plotting/backend): wire EasyProvider to dispatch knobs

EasyProvider now exposes get_knobs (from callback Annotated kwargs or a
Pydantic model passed via create_virtual_product(..., knobs_model=...))
and forwards knobs into the user callback as either kwargs or a
validated model instance. Backwards compatible: callbacks with no knob
kwargs and no knobs= argument call exactly as before.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Chunk 3 — VP registration & %%vp magic knob pickup

Goal: when a function is registered as a VP (programmatic or via `%%vp`), expose its knob specs through the `EasyProvider` already wired in Chunk 2, and refresh the spec on hot-reload.

### Task 7: MutableCallback forwards knob kwargs and refreshes specs

**Files:**
- Modify: `SciQLop/user_api/virtual_products/registry.py`
- Test: `tests/test_virtual_products/test_registry_knobs.py`

- [ ] **Step 1: Write the failing test**

```python
from typing import Annotated

from SciQLop.user_api.knobs import Knob
from SciQLop.user_api.virtual_products.registry import (
    MutableCallback, VPRegistry,
)


def test_mutablecallback_forwards_kwargs():
    seen = {}

    def f(start, stop, fft: Annotated[int, Knob(min=64)] = 256):
        seen["fft"] = fft
        return None

    cb = MutableCallback(f)
    cb(0.0, 1.0, fft=1024)
    assert seen["fft"] == 1024


def test_mutablecallback_after_call_still_invoked():
    received = {}

    def f(start, stop, fft: int = 256):
        return ("ok", fft)

    cb = MutableCallback(f)
    cb.after_call = lambda r, e: received.update(result=r, elapsed=e)
    cb(0.0, 1.0, fft=128)
    assert received["result"] == ("ok", 128)
    assert received["elapsed"] >= 0


def test_registry_marks_signature_changed_when_knob_added():
    reg = VPRegistry()

    def f1(start, stop): ...
    def f2(start, stop, fft: int = 256): ...

    e1 = reg.register("p", f1, "scalar", ["x"])
    assert e1.signature_changed is False

    e2 = reg.register("p", f2, "scalar", ["x"])
    assert e2.signature_changed is True


def test_registry_keeps_signature_when_only_body_changes():
    reg = VPRegistry()

    def f1(start, stop, fft: int = 256):
        return None

    def f2(start, stop, fft: int = 256):
        return [1, 2]

    reg.register("p", f1, "scalar", ["x"])
    e2 = reg.register("p", f2, "scalar", ["x"])
    assert e2.signature_changed is False
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/test_virtual_products/test_registry_knobs.py -v
```

Expected: FAIL — `MutableCallback.__call__` rejects `fft=` kwarg; `signature_changed` doesn't react to kwargs.

- [ ] **Step 3: Modify MutableCallback and VPRegistry**

In `SciQLop/user_api/virtual_products/registry.py`:

```python
import inspect


def _signature_kwargs(callback) -> tuple[tuple[str, type], ...]:
    sig = inspect.signature(callback)
    return tuple(
        (name, p.default.__class__)
        for name, p in sig.parameters.items()
        if p.default is not inspect.Parameter.empty and name not in ("start", "stop")
    )


class MutableCallback:
    def __init__(self, callback):
        self.callback = callback
        self.after_call = None

    def _update_metadata(self, callback):
        import functools
        functools.update_wrapper(self, callback)

    @property
    def callback(self):
        return self._callback

    @callback.setter
    def callback(self, value):
        self._callback = value
        self._update_metadata(value)

    def __call__(self, start, stop, **kwargs):
        import time as _time
        t0 = _time.monotonic()
        result = self._callback(start, stop, **kwargs)
        elapsed = _time.monotonic() - t0
        if self.after_call is not None:
            self.after_call(result, elapsed)
        return result
```

In `VPRegistry.register`, signature-equality must include kwargs (not just body identity):

```python
def register(self, name, callback, product_type, labels):
    existing = self._entries.get(name)
    new_sig_kwargs = _signature_kwargs(callback)
    if existing and existing.product_type == product_type and existing.labels == labels:
        old_sig_kwargs = _signature_kwargs(existing.wrapper.callback)
        if old_sig_kwargs == new_sig_kwargs:
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
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run pytest tests/test_virtual_products/test_registry_knobs.py tests/test_vp_magic.py tests/test_vp_magic_integration.py -q
```

Expected: green.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/user_api/virtual_products/registry.py tests/test_virtual_products/test_registry_knobs.py
git commit -m "$(cat <<'EOF'
feat(virtual_products/registry): forward knob kwargs and detect kwarg changes

MutableCallback now passes **kwargs through to the user callback, so the
EasyProvider knob dispatch reaches all VPs (programmatic and %%vp).
VPRegistry.register treats kwarg-set changes as signature_changed, which
will trigger spec migration in the inspector.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: %%vp magic refreshes EasyProvider knob specs on reload

**Files:**
- Modify: `SciQLop/user_api/virtual_products/magic.py`
- Test: `tests/test_virtual_products/test_vp_magic_knobs.py`

- [ ] **Step 1: Write the failing test**

```python
from tests.helpers import qtbot_for_main_window  # existing helper used by test_vp_magic
import pytest

from SciQLop.user_api.virtual_products.registry import _registry
from SciQLop.user_api.virtual_products.magic import vp_magic


@pytest.fixture(autouse=True)
def _clean_registry():
    _registry._entries.clear()
    yield
    _registry._entries.clear()


def test_vp_magic_reports_knob_specs(qtbot, sciqlop_app):
    cell = (
        "from typing import Annotated\n"
        "from SciQLop.user_api.knobs import Knob\n"
        "def my_vp(start: float, stop: float,\n"
        "          fft: Annotated[int, Knob(min=64, max=4096, step=64)] = 256) -> Scalar:\n"
        "    import numpy as np\n"
        "    n = 8\n"
        "    return np.linspace(start, stop, n), np.zeros(n)\n"
    )
    vp_magic("", cell, local_ns={})
    entry = _registry.get("my_vp")
    assert entry is not None
    from SciQLop.components.plotting.backend.data_provider import providers
    provider = next(p for p in providers.values()
                    if getattr(p, "_callback", None) is entry.wrapper.callback
                    or getattr(p, "name", "").startswith("my_vp"))
    specs = provider.get_knobs("any")
    assert {s.name for s in specs} == {"fft"}


def test_vp_magic_reload_refreshes_knob_specs(qtbot, sciqlop_app):
    cell_a = (
        "from typing import Annotated\n"
        "from SciQLop.user_api.knobs import Knob\n"
        "def my_vp(start: float, stop: float,\n"
        "          fft: Annotated[int, Knob(min=64, max=4096)] = 256) -> Scalar:\n"
        "    import numpy as np\n"
        "    n = 8\n"
        "    return np.linspace(start, stop, n), np.zeros(n)\n"
    )
    cell_b = cell_a.replace("fft: Annotated[int, Knob(min=64, max=4096)] = 256",
                            "fft: Annotated[int, Knob(min=64, max=4096)] = 256, win: str = 'hann'")
    vp_magic("", cell_a, local_ns={})
    vp_magic("", cell_b, local_ns={})
    entry = _registry.get("my_vp")
    from SciQLop.components.plotting.backend.data_provider import providers
    provider = next(p for p in providers.values()
                    if getattr(p, "name", "").startswith("my_vp"))
    names = {s.name for s in provider.get_knobs("any")}
    assert names == {"fft", "win"}
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/test_virtual_products/test_vp_magic_knobs.py -v
```

Expected: FAIL — second test sees stale specs because EasyProvider doesn't refresh when only the callback body is swapped.

- [ ] **Step 3: Refresh provider knob specs from %%vp**

In `SciQLop/user_api/virtual_products/magic.py`, after the `_registry.register(...)` call but before `_register_virtual_product(...)`, refresh provider specs whenever signature changed:

```python
if is_new or entry.signature_changed:
    _register_virtual_product(func_name, entry.wrapper, type_info.product_type,
                              type_info.labels, args.path, cached_data=cached_data)
else:
    # Body-only change: provider already exists; refresh its knob specs
    # against the new callback so any Knob(...) marker tweaks propagate.
    from SciQLop.components.plotting.backend.data_provider import providers
    for p in providers.values():
        if getattr(p, "_callback", None) is entry.wrapper.callback:
            if hasattr(p, "_refresh_knob_specs"):
                p._refresh_knob_specs()
```

When the signature *did* change, the path through `_register_virtual_product` rebuilds the `EasyProvider` (and therefore its specs) from scratch — no extra wiring needed.

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run pytest tests/test_virtual_products/test_vp_magic_knobs.py -v
```

Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/user_api/virtual_products/magic.py tests/test_virtual_products/test_vp_magic_knobs.py
git commit -m "$(cat <<'EOF'
feat(virtual_products/magic): expose and refresh knob specs from %%vp

%%vp picks up Annotated[T, Knob(...)] kwargs through the existing
EasyProvider knob path. Body-only reloads also refresh the cached
spec list so marker tweaks (label/min/max) propagate without panel
restart.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Chunk 4 — Request pipeline: GraphKnobState + callback plumbing + cache key

Goal: introduce `GraphKnobState` (per-graph dict-with-signal), thread `knob_values` through the `_plot_product_callback` / `_specgram_callback` Python wrappers in `time_sync_panel.py`, and ensure the canonical hash is computed at the callback boundary so the C++ cache key is automatically distinct per knob set.

### Task 9: Add GraphKnobState (Python-side wrapper)

**Files:**
- Create: `SciQLop/components/plotting/backend/graph_knobs.py`
- Test: `tests/test_plotting/test_graph_knob_state.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from PySide6.QtCore import QObject

from SciQLop.user_api.knobs import IntKnob, ChoiceKnob
from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState


SPECS = [
    IntKnob(name="fft", default=256, min=64, max=4096, step=64),
    ChoiceKnob(name="win", default="hann",
               choices=(("Hann", "hann"), ("Hamming", "hamming"))),
]


def test_state_initializes_with_defaults():
    s = GraphKnobState(SPECS)
    assert s.values == {"fft": 256, "win": "hann"}


def test_set_value_validates_and_signals(qtbot):
    s = GraphKnobState(SPECS)
    received = []
    s.knobs_changed.connect(lambda d: received.append(dict(d)))
    s.set_value("fft", "1024")
    assert s.values["fft"] == 1024
    assert received[-1]["fft"] == 1024


def test_set_value_invalid_keeps_old(qtbot):
    s = GraphKnobState(SPECS)
    with pytest.raises(ValueError):
        s.set_value("win", "rect")
    assert s.values["win"] == "hann"


def test_bulk_set_load_rules():
    s = GraphKnobState(SPECS)
    s.set_all({"fft": 128, "removed": 99})
    assert s.values == {"fft": 128, "win": "hann"}


def test_replace_specs_migrates_values():
    s = GraphKnobState(SPECS)
    s.set_value("fft", 1024)
    new_specs = [
        IntKnob(name="fft", default=256, min=64, max=4096, step=64),
        IntKnob(name="overlap", default=8, min=0, max=64),
    ]
    s.replace_specs(new_specs)
    assert s.values == {"fft": 1024, "overlap": 8}
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/test_plotting/test_graph_knob_state.py -v
```

Expected: FAIL on `ImportError`.

- [ ] **Step 3: Implement GraphKnobState**

`SciQLop/components/plotting/backend/graph_knobs.py`:

```python
from typing import Iterable

from PySide6.QtCore import QObject, Signal

from SciQLop.user_api.knobs import (
    KnobSpec, coerce_value, validate_dict, defaults_for, canonical_hash,
)


class GraphKnobState(QObject):
    knobs_changed = Signal(dict)

    def __init__(self, specs: Iterable[KnobSpec], parent=None):
        super().__init__(parent)
        self._specs = list(specs)
        self._values = defaults_for(self._specs)

    @property
    def specs(self) -> list[KnobSpec]:
        return list(self._specs)

    @property
    def values(self) -> dict:
        return dict(self._values)

    def set_value(self, name: str, value):
        spec = next((s for s in self._specs if s.name == name), None)
        if spec is None:
            raise KeyError(name)
        coerced = coerce_value(spec, value)
        if self._values.get(name) == coerced:
            return
        self._values[name] = coerced
        self.knobs_changed.emit(dict(self._values))

    def set_all(self, values: dict):
        new = validate_dict(self._specs, values)
        if new == self._values:
            return
        self._values = new
        self.knobs_changed.emit(dict(self._values))

    def replace_specs(self, specs: Iterable[KnobSpec]):
        self._specs = list(specs)
        self._values = validate_dict(self._specs, self._values)
        self.knobs_changed.emit(dict(self._values))

    def cache_key(self) -> str:
        return canonical_hash(self._values)
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run pytest tests/test_plotting/test_graph_knob_state.py -v
```

Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/plotting/backend/graph_knobs.py tests/test_plotting/test_graph_knob_state.py
git commit -m "$(cat <<'EOF'
feat(plotting/backend): add GraphKnobState (per-graph knob dict + signal)

QObject wrapper around a {name: value} dict. set_value coerces against
the spec; set_all applies load-rules; replace_specs migrates on
hot-reload. Emits knobs_changed(dict) for inspector + request pipeline.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: Thread knob_values through the plot callbacks

**Files:**
- Modify: `SciQLop/components/plotting/ui/time_sync_panel.py` (lines around 150–322)
- Test: `tests/test_plotting/test_request_knobs.py`

- [ ] **Step 1: Write the failing test**

```python
from typing import Annotated

import numpy as np
import pytest

from SciQLop.user_api.knobs import Knob, IntKnob


@pytest.fixture(autouse=True)
def _isolate_products(monkeypatch):
    from SciQLop.core.models import products
    monkeypatch.setattr(products, "add_node", lambda *a, **k: None)


def test_plot_product_callback_passes_knobs():
    from SciQLop.components.plotting.backend.easy_provider import EasyScalar
    from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
    from SciQLop.components.plotting.ui.time_sync_panel import _plot_product_callback

    seen = {}

    def f(start: float, stop: float,
          fft: Annotated[int, Knob(min=64, max=4096)] = 256):
        seen["fft"] = fft
        n = 4
        return np.linspace(start, stop, n), np.zeros(n)

    p = EasyScalar(path="vp/test", get_data_callback=f, component_name="x", metadata={})
    state = GraphKnobState([IntKnob(name="fft", default=256, min=64, max=4096)])
    state.set_value("fft", 1024)

    cb = _plot_product_callback(provider=p, node=None, knob_state=state)
    cb(0.0, 1.0)
    assert seen["fft"] == 1024


def test_plot_product_callback_without_state_calls_unchanged():
    from SciQLop.components.plotting.backend.easy_provider import EasyScalar
    from SciQLop.components.plotting.ui.time_sync_panel import _plot_product_callback

    seen = {}

    def f(start: float, stop: float):
        seen["called"] = True
        n = 4
        return np.linspace(start, stop, n), np.zeros(n)

    p = EasyScalar(path="vp/test2", get_data_callback=f, component_name="x", metadata={})
    cb = _plot_product_callback(provider=p, node=None)
    cb(0.0, 1.0)
    assert seen["called"]
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/test_plotting/test_request_knobs.py -v
```

Expected: FAIL — `_plot_product_callback` doesn't accept `knob_state=`.

- [ ] **Step 3: Modify the callback wrappers**

In `SciQLop/components/plotting/ui/time_sync_panel.py`, update both callback classes:

```python
class _plot_product_callback:
    def __init__(self, provider: DataProvider, node,
                 post_fetch: Optional["_PostFetchHintsApplier"] = None,
                 knob_state=None):
        self.provider = provider
        self.node = node
        self._post_fetch = post_fetch
        self.knob_state = knob_state  # GraphKnobState | None

    def _knob_values(self):
        return self.knob_state.values if self.knob_state is not None else None

    def __call__(self, start, stop):
        try:
            observer = self._post_fetch.observe if self._post_fetch is not None else None
            return self.provider._get_data(self.node, start, stop,
                                            on_variable=observer,
                                            knobs=self._knob_values())
        except Exception as e:
            log.error(f"Error getting data for {self.node}: {e}")
            return []


class _specgram_callback:
    def __init__(self, provider: DataProvider, node,
                 post_fetch: Optional["_PostFetchHintsApplier"] = None,
                 knob_state=None):
        self.provider = provider
        self.node = node
        self._y_is_descending_ = None
        self._post_fetch = post_fetch
        self.knob_state = knob_state

    def _knob_values(self):
        return self.knob_state.values if self.knob_state is not None else None

    def _y_is_descending(self, y):
        if self._y_is_descending_ is None:
            self._y_is_descending_ = _y_is_descending(y)
            log.debug(f"y_is_descending: {self._y_is_descending_}")
        return self._y_is_descending_

    def __call__(self, start, stop):
        try:
            observer = self._post_fetch.observe if self._post_fetch is not None else None
            x, y, z = self.provider._get_data(self.node, start, stop,
                                              on_variable=observer,
                                              knobs=self._knob_values())
            if self._y_is_descending(y):
                if len(y.shape) == 1:
                    y = y[::-1].copy()
                else:
                    y = y[:, ::-1].copy()
                z = z[:, ::-1].copy()
            return x, y, z
        except Exception as e:
            log.error(f"Error getting data for {self.node}: {e}")
            return []
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run pytest tests/test_plotting/test_request_knobs.py -v
```

Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/plotting/ui/time_sync_panel.py tests/test_plotting/test_request_knobs.py
git commit -m "$(cat <<'EOF'
feat(plotting/ui): thread per-graph knob_values through plot callbacks

_plot_product_callback and _specgram_callback now hold an optional
GraphKnobState; if set, its dict is passed as knobs= into
provider._get_data. Backwards compatible: callers that don't supply
knob_state get the legacy code path unchanged.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: Wire plot_product to create GraphKnobState and reset on knob change

**Files:**
- Modify: `SciQLop/components/plotting/ui/time_sync_panel.py` (`plot_product` and the C++ glue around it)
- Test: `tests/test_plotting/test_plot_product_knobs.py`

- [ ] **Step 1: Write the failing test**

```python
from typing import Annotated

import numpy as np
import pytest

from SciQLop.user_api.knobs import Knob


@pytest.fixture(autouse=True)
def _isolate_products(monkeypatch):
    from SciQLop.core.models import products
    monkeypatch.setattr(products, "add_node", lambda *a, **k: None)


def test_plot_product_sets_default_knob_values(qtbot, sciqlop_app, plot_panel_factory):
    from SciQLop.components.plotting.backend.easy_provider import EasyScalar
    from SciQLop.components.plotting.ui.time_sync_panel import plot_product, _plot_product_callback

    def f(start: float, stop: float,
          fft: Annotated[int, Knob(min=64, max=4096)] = 256):
        n = 4
        return np.linspace(start, stop, n), np.zeros(n)

    panel = plot_panel_factory()
    EasyScalar(path="vp/myfft", get_data_callback=f, component_name="x", metadata={})
    r = plot_product(panel, ["vp", "myfft"])
    graph = r[1] if hasattr(r, "__iter__") else r
    state = getattr(graph, "_knob_state", None)
    assert state is not None
    assert state.values == {"fft": 256}
```

> *Note*: `plot_panel_factory` is the same fixture used by other panel tests in `tests/test_plot_pure_logic.py` / `tests/test_panel_template_integration.py` — re-use it.

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/test_plotting/test_plot_product_knobs.py -v
```

Expected: FAIL — graph has no `_knob_state`.

- [ ] **Step 3: Wire up GraphKnobState at plot time**

In `SciQLop/components/plotting/ui/time_sync_panel.py`, after the existing `_register_graph_hints(...)` call inside `plot_product`, attach a knob state if the provider exposes any specs:

```python
def _attach_knob_state(provider, product_path_str, callback, r):
    specs = []
    try:
        specs = provider.get_knobs(product_path_str)
    except Exception:
        log.debug("get_knobs failed for %s", product_path_str, exc_info=True)
    if not specs:
        return
    from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
    graph = r[1] if hasattr(r, "__iter__") else r
    state = GraphKnobState(specs, parent=graph)
    graph._knob_state = state
    callback.knob_state = state
    state.knobs_changed.connect(lambda *_: _trigger_refetch(graph))


def _trigger_refetch(graph):
    """Cancel in-flight, re-fetch with new knob values."""
    try:
        graph.replot()
    except AttributeError:
        try:
            graph.parentPlot().replot()
        except Exception:
            log.debug("could not trigger replot for knob change", exc_info=True)
```

Now in both branches of `plot_product` (Scalar/Vector/Multicomp and Spectrogram), call `_attach_knob_state` right after `_register_graph_hints`:

```python
callback._post_fetch = _register_graph_hints(provider, node, r, target)
_attach_knob_state(provider, product_path_str, callback, r)
return r
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run pytest tests/test_plotting/test_plot_product_knobs.py -v
```

Expected: PASS.

- [ ] **Step 5: Verify cache-key effect via canonical hash + integration**

Add a focused regression to `tests/test_plotting/test_request_knobs.py`:

```python
def test_state_cache_key_changes_with_value():
    from SciQLop.user_api.knobs import IntKnob
    from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
    s = GraphKnobState([IntKnob(name="fft", default=256, min=64, max=4096)])
    k0 = s.cache_key()
    s.set_value("fft", 1024)
    k1 = s.cache_key()
    assert k0 != k1
```

```bash
uv run pytest tests/test_plotting/test_request_knobs.py::test_state_cache_key_changes_with_value -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add SciQLop/components/plotting/ui/time_sync_panel.py tests/test_plotting/test_plot_product_knobs.py tests/test_plotting/test_request_knobs.py
git commit -m "$(cat <<'EOF'
feat(plotting/ui): create GraphKnobState on parameterized plot_product

When a provider exposes get_knobs() for a product, plot_product builds
a GraphKnobState seeded from defaults, attaches it to both the graph
and the callback, and triggers a replot whenever values change. The
cache_key() helper exposes the canonical hash for downstream cache use.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Chunk 5 — Speasy provider knob translation (generic)

Goal: implement `SpeasyPlugin.get_knobs(...)` as a generic walk over `ArgumentListIndex` / `ArgumentIndex` (no AMDA-specific code) and forward `knobs` into `spz.get_data(..., product_inputs=...)`. Pull schemas fresh from inventory each call.

### Task 12: Speasy `get_knobs` from synthetic SpeasyIndex

**Files:**
- Modify: `SciQLop/plugins/speasy_provider/speasy_provider.py`
- Test: `tests/test_speasy_provider/__init__.py`, `tests/test_speasy_provider/test_knobs_argument_index.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_speasy_provider/__init__.py` (empty), then:

```python
from types import SimpleNamespace

import pytest

from SciQLop.user_api.knobs import ChoiceKnob


@pytest.fixture
def fake_argument_index_classes(monkeypatch):
    """Stub SpeasyIndex hierarchy minimal enough to exercise the walk."""
    class ArgumentIndex:
        def __init__(self, name, type_, choices=None, default=None):
            self.name = name
            self.type = type_
            self.choices = choices or []
            self.default = default

    class ArgumentListIndex:
        def __init__(self, args):
            self._args = list(args)

        def __iter__(self):
            return iter(self._args)

    class TemplatedParameterIndex:
        def __init__(self, args):
            self.spz_arguments_node = ArgumentListIndex(args)

        def __iter__(self):
            yield self.spz_arguments_node

    monkeypatch.setattr("SciQLop.plugins.speasy_provider.speasy_provider.ArgumentIndex",
                        ArgumentIndex, raising=False)
    monkeypatch.setattr("SciQLop.plugins.speasy_provider.speasy_provider.ArgumentListIndex",
                        ArgumentListIndex, raising=False)
    return ArgumentIndex, ArgumentListIndex, TemplatedParameterIndex


def test_get_knobs_walks_argument_list(fake_argument_index_classes, monkeypatch):
    from SciQLop.plugins.speasy_provider import speasy_provider as mod

    ArgumentIndex, ArgumentListIndex, TemplatedParameterIndex = fake_argument_index_classes

    fake_index = TemplatedParameterIndex([
        ArgumentIndex("lookdir", "list",
                      choices=[("Sun", "sun"), ("Tail", "tail")],
                      default="sun"),
        ArgumentIndex("species", "generated-list",
                      choices=[("H+", "H"), ("He+", "He")],
                      default="H"),
    ])

    plugin = mod.SpeasyPlugin.__new__(mod.SpeasyPlugin)  # bypass __init__
    monkeypatch.setattr(plugin, "_resolve_index", lambda product: fake_index, raising=False)

    specs = plugin.get_knobs("amda/jedi_i90_flux")
    by_name = {s.name: s for s in specs}
    assert isinstance(by_name["lookdir"], ChoiceKnob)
    assert by_name["lookdir"].choices == (("Sun", "sun"), ("Tail", "tail"))
    assert by_name["lookdir"].default == "sun"
    assert by_name["species"].choices == (("H+", "H"), ("He+", "He"))


def test_get_knobs_returns_empty_for_non_templated(monkeypatch):
    from SciQLop.plugins.speasy_provider import speasy_provider as mod
    plugin = mod.SpeasyPlugin.__new__(mod.SpeasyPlugin)
    monkeypatch.setattr(plugin, "_resolve_index", lambda product: object(), raising=False)
    assert plugin.get_knobs("amda/regular_param") == []
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/test_speasy_provider/test_knobs_argument_index.py -v
```

Expected: FAIL — `get_knobs` not implemented; `_resolve_index` missing.

- [ ] **Step 3: Add the generic walk and resolver**

In `SciQLop/plugins/speasy_provider/speasy_provider.py`, add the import and helpers near the top:

```python
from speasy.core.inventory.indexes import (
    ArgumentIndex, ArgumentListIndex, TemplatedParameterIndex,
)

from SciQLop.user_api.knobs import (
    KnobSpec, ChoiceKnob, IntKnob, FloatKnob, BoolKnob, StringKnob,
)


def _find_argument_list(index) -> Optional[ArgumentListIndex]:
    if isinstance(index, ArgumentListIndex):
        return index
    for child in getattr(index, "__dict__", {}).values():
        if isinstance(child, ArgumentListIndex):
            return child
    return None


def _argument_to_knob(arg) -> Optional[KnobSpec]:
    name = getattr(arg, "name", None) or getattr(arg, "spz_name", lambda: "")()
    if not name:
        return None
    arg_type = (getattr(arg, "type", "") or "").lower()
    default = getattr(arg, "default", None)

    if arg_type in ("list", "generated-list"):
        raw_choices = getattr(arg, "choices", []) or []
        choices = []
        for c in raw_choices:
            if isinstance(c, tuple) and len(c) == 2:
                choices.append((str(c[0]), c[1]))
            else:
                choices.append((str(c), c))
        return ChoiceKnob(name=name, default=default, choices=tuple(choices))

    if arg_type == "bool":
        return BoolKnob(name=name, default=bool(default) if default is not None else False)
    if arg_type in ("int", "integer"):
        return IntKnob(name=name, default=int(default) if default is not None else 0)
    if arg_type in ("float", "double"):
        return FloatKnob(name=name, default=float(default) if default is not None else 0.0)
    if arg_type in ("string", "str", ""):
        return StringKnob(name=name, default=str(default) if default is not None else "")
    return None
```

Then add to `SpeasyPlugin`:

```python
def _resolve_index(self, product):
    """Look up the ParameterIndex for a product id (used for knob discovery)."""
    if hasattr(product, "metadata"):
        speasy_id = product.metadata("speasy_id")
    else:
        speasy_id = product
    if not speasy_id:
        return None
    try:
        return spz.inventories.flat_inventories.parameters.get(speasy_id)
    except Exception:
        return None

def get_knobs(self, product) -> list:
    index = self._resolve_index(product)
    if index is None:
        return []
    args_node = _find_argument_list(index)
    if args_node is None:
        return []
    out = []
    for arg in args_node:
        spec = _argument_to_knob(arg)
        if spec is not None:
            out.append(spec)
    return out

def get_data(self, product, start, stop, knobs=None):
    try:
        speasy_id = product.metadata("speasy_id") if hasattr(product, "metadata") else product
        kwargs = {"product_inputs": dict(knobs)} if knobs else {}
        v: SpeasyVariable = spz.get_data(speasy_id, start, stop, **kwargs)
        if v:
            return v.replace_fillval_by_nan(inplace=True, convert_to_float=True)
    except Exception:
        log.error(f"Error getting data for {product} between {start} and {stop}: {traceback.format_exc()}")
        return None
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run pytest tests/test_speasy_provider/test_knobs_argument_index.py -v
```

Expected: 2 PASS.

- [ ] **Step 5: Smoke-check existing speasy tests**

```bash
uv run pytest tests/test_speasy_plot_backend.py tests/test_speasy_variable_meta.py -q
```

Expected: green.

- [ ] **Step 6: Commit**

```bash
git add SciQLop/plugins/speasy_provider/speasy_provider.py tests/test_speasy_provider/__init__.py tests/test_speasy_provider/test_knobs_argument_index.py
git commit -m "$(cat <<'EOF'
feat(speasy_provider): translate ArgumentIndex into knob specs

SpeasyPlugin.get_knobs walks the inventory's generic ArgumentListIndex
and emits one KnobSpec per ArgumentIndex (ChoiceKnob for list /
generated-list; future-proof for bool/int/float/str types). get_data
forwards knobs as product_inputs=. No AMDA-specific code.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Chunk 6 — Inspector UI (delegates + section + integration)

Goal: build the per-graph "Parameters" section that lives in the inspector dock — a delegate per spec type, a `KnobsSection` widget driven by `GraphKnobState`, and a per-knob `QTimer` debouncer.

### Task 13: Knob delegates (mapping KnobSpec → editor widget)

**Files:**
- Create: `SciQLop/components/plotting/ui/knob_inspector/__init__.py` (empty)
- Create: `SciQLop/components/plotting/ui/knob_inspector/delegates.py`
- Test: `tests/test_plotting/test_knob_delegates.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest

from SciQLop.user_api.knobs import (
    IntKnob, FloatKnob, BoolKnob, ChoiceKnob, StringKnob,
)
from SciQLop.components.plotting.ui.knob_inspector.delegates import (
    delegate_for_spec, KnobDelegate,
)


def test_int_knob_delegate(qtbot):
    spec = IntKnob(name="fft", default=256, min=64, max=4096, step=64)
    d = delegate_for_spec(spec)
    qtbot.addWidget(d)
    d.set_value(1024)
    assert d.get_value() == 1024


def test_float_knob_delegate(qtbot):
    spec = FloatKnob(name="thr", default=0.5, min=0.0, max=1.0, step=0.01)
    d = delegate_for_spec(spec)
    qtbot.addWidget(d)
    d.set_value(0.75)
    assert d.get_value() == pytest.approx(0.75)


def test_bool_knob_delegate(qtbot):
    spec = BoolKnob(name="cache", default=False)
    d = delegate_for_spec(spec)
    qtbot.addWidget(d)
    d.set_value(True)
    assert d.get_value() is True


def test_choice_knob_delegate(qtbot):
    spec = ChoiceKnob(name="w", default="hann",
                      choices=(("Hann", "hann"), ("Hamming", "hamming")))
    d = delegate_for_spec(spec)
    qtbot.addWidget(d)
    d.set_value("hamming")
    assert d.get_value() == "hamming"


def test_string_knob_delegate(qtbot):
    spec = StringKnob(name="s", default="x", pattern=r"^[a-z]+$")
    d = delegate_for_spec(spec)
    qtbot.addWidget(d)
    d.set_value("abc")
    assert d.get_value() == "abc"


def test_value_changed_signal(qtbot):
    spec = IntKnob(name="x", default=0, min=0, max=10)
    d = delegate_for_spec(spec)
    qtbot.addWidget(d)
    received = []
    d.value_changed.connect(lambda v: received.append(v))
    d.set_value(5)
    d._emit_for_test(5)  # convenience used by delegate to confirm wiring
    assert received[-1] == 5
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/test_plotting/test_knob_delegates.py -v
```

Expected: FAIL on `ImportError`.

- [ ] **Step 3: Implement the delegates**

Create `SciQLop/components/plotting/ui/knob_inspector/__init__.py` (empty), then `delegates.py`:

```python
from typing import Any

from PySide6.QtCore import QRegularExpression, Signal
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox, QLineEdit,
)

from SciQLop.user_api.knobs import (
    KnobSpec, IntKnob, FloatKnob, BoolKnob, ChoiceKnob, StringKnob,
)


class KnobDelegate(QWidget):
    value_changed = Signal(object)

    def __init__(self, spec: KnobSpec, parent=None):
        super().__init__(parent)
        self.spec = spec

    def get_value(self) -> Any:
        raise NotImplementedError

    def set_value(self, value: Any) -> None:
        raise NotImplementedError

    def _emit_for_test(self, value):
        self.value_changed.emit(value)


class _IntDelegate(KnobDelegate):
    def __init__(self, spec: IntKnob, parent=None):
        super().__init__(spec, parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._spin = QSpinBox()
        if spec.min is not None:
            self._spin.setMinimum(spec.min)
        else:
            self._spin.setMinimum(-(2 ** 31))
        if spec.max is not None:
            self._spin.setMaximum(spec.max)
        else:
            self._spin.setMaximum(2 ** 31 - 1)
        if spec.step:
            self._spin.setSingleStep(spec.step)
        layout.addWidget(self._spin)
        self._spin.valueChanged.connect(self.value_changed.emit)

    def get_value(self):
        return self._spin.value()

    def set_value(self, value):
        self._spin.blockSignals(True)
        self._spin.setValue(int(value))
        self._spin.blockSignals(False)


class _FloatDelegate(KnobDelegate):
    def __init__(self, spec: FloatKnob, parent=None):
        super().__init__(spec, parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._spin = QDoubleSpinBox()
        self._spin.setDecimals(6)
        if spec.min is not None:
            self._spin.setMinimum(spec.min)
        else:
            self._spin.setMinimum(-1e18)
        if spec.max is not None:
            self._spin.setMaximum(spec.max)
        else:
            self._spin.setMaximum(1e18)
        if spec.step:
            self._spin.setSingleStep(spec.step)
        layout.addWidget(self._spin)
        self._spin.valueChanged.connect(self.value_changed.emit)

    def get_value(self):
        return self._spin.value()

    def set_value(self, value):
        self._spin.blockSignals(True)
        self._spin.setValue(float(value))
        self._spin.blockSignals(False)


class _BoolDelegate(KnobDelegate):
    def __init__(self, spec: BoolKnob, parent=None):
        super().__init__(spec, parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._cb = QCheckBox()
        layout.addWidget(self._cb)
        layout.addStretch()
        self._cb.toggled.connect(self.value_changed.emit)

    def get_value(self):
        return self._cb.isChecked()

    def set_value(self, value):
        self._cb.blockSignals(True)
        self._cb.setChecked(bool(value))
        self._cb.blockSignals(False)


class _ChoiceDelegate(KnobDelegate):
    def __init__(self, spec: ChoiceKnob, parent=None):
        super().__init__(spec, parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._combo = QComboBox()
        for label, value in spec.choices:
            self._combo.addItem(label, value)
        layout.addWidget(self._combo)
        self._combo.currentIndexChanged.connect(
            lambda i: self.value_changed.emit(self._combo.itemData(i))
        )

    def get_value(self):
        return self._combo.currentData()

    def set_value(self, value):
        self._combo.blockSignals(True)
        for i in range(self._combo.count()):
            if self._combo.itemData(i) == value:
                self._combo.setCurrentIndex(i)
                break
        self._combo.blockSignals(False)


class _StringDelegate(KnobDelegate):
    def __init__(self, spec: StringKnob, parent=None):
        super().__init__(spec, parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._edit = QLineEdit()
        if spec.pattern:
            self._edit.setValidator(
                QRegularExpressionValidator(QRegularExpression(spec.pattern), self._edit)
            )
        layout.addWidget(self._edit)
        self._edit.textChanged.connect(self.value_changed.emit)

    def get_value(self):
        return self._edit.text()

    def set_value(self, value):
        self._edit.blockSignals(True)
        self._edit.setText(str(value))
        self._edit.blockSignals(False)


_DELEGATES = {
    IntKnob: _IntDelegate,
    FloatKnob: _FloatDelegate,
    BoolKnob: _BoolDelegate,
    ChoiceKnob: _ChoiceDelegate,
    StringKnob: _StringDelegate,
}


def delegate_for_spec(spec: KnobSpec, parent=None) -> KnobDelegate:
    cls = _DELEGATES.get(type(spec))
    if cls is None:
        raise TypeError(f"No delegate for {type(spec).__name__}")
    return cls(spec, parent)
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run pytest tests/test_plotting/test_knob_delegates.py -v
```

Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/plotting/ui/knob_inspector/__init__.py SciQLop/components/plotting/ui/knob_inspector/delegates.py tests/test_plotting/test_knob_delegates.py
git commit -m "$(cat <<'EOF'
feat(plotting/ui): add per-spec knob delegates

KnobDelegate base + concrete spinbox/checkbox/combo/lineedit per
KnobSpec subclass. Mirrors the settings-delegate pattern but stays
isolated under knob_inspector/ until a future shared factory refactor.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 14: KnobsSection — drives a GraphKnobState with per-widget debouncer

**Files:**
- Create: `SciQLop/components/plotting/ui/knob_inspector/section.py`
- Test: `tests/test_plotting/test_knob_inspector.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget

from SciQLop.user_api.knobs import IntKnob, ChoiceKnob
from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
from SciQLop.components.plotting.ui.knob_inspector.section import KnobsSection


SPECS = [
    IntKnob(name="fft", default=256, min=64, max=4096, step=64),
    ChoiceKnob(name="win", default="hann",
               choices=(("Hann", "hann"), ("Hamming", "hamming"))),
]


def test_section_renders_one_widget_per_spec(qtbot):
    state = GraphKnobState(SPECS)
    sec = KnobsSection(state)
    qtbot.addWidget(sec)
    assert sec.widget_for("fft") is not None
    assert sec.widget_for("win") is not None


def test_widget_change_debounces_into_state(qtbot, monkeypatch):
    state = GraphKnobState(SPECS)
    sec = KnobsSection(state, debounce_ms=10)
    qtbot.addWidget(sec)
    sec.widget_for("fft").set_value(1024)
    sec.widget_for("fft").value_changed.emit(1024)
    qtbot.wait(50)
    assert state.values["fft"] == 1024


def test_state_change_resyncs_widget_without_loop(qtbot):
    state = GraphKnobState(SPECS)
    sec = KnobsSection(state, debounce_ms=10)
    qtbot.addWidget(sec)
    state.set_value("fft", 512)
    assert sec.widget_for("fft").get_value() == 512


def test_reset_button_restores_defaults(qtbot):
    state = GraphKnobState(SPECS)
    state.set_value("fft", 1024)
    sec = KnobsSection(state, debounce_ms=10)
    qtbot.addWidget(sec)
    sec.reset_to_defaults()
    qtbot.wait(50)
    assert state.values["fft"] == 256


def test_manual_apply_knob_skips_debouncer(qtbot):
    spec_manual = IntKnob(name="fft", default=256, min=64, max=4096,
                          step=64, apply="manual")
    state = GraphKnobState([spec_manual])
    sec = KnobsSection(state, debounce_ms=2000)
    qtbot.addWidget(sec)
    sec.widget_for("fft").set_value(1024)
    sec.widget_for("fft").value_changed.emit(1024)
    # No apply yet -> state unchanged
    assert state.values["fft"] == 256
    sec.apply_manual()
    assert state.values["fft"] == 1024
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/test_plotting/test_knob_inspector.py -v
```

Expected: FAIL — `KnobsSection` not implemented.

- [ ] **Step 3: Implement KnobsSection**

`SciQLop/components/plotting/ui/knob_inspector/section.py`:

```python
from typing import Optional

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLabel, QPushButton, QHBoxLayout,
)

from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
from SciQLop.components.plotting.ui.knob_inspector.delegates import (
    KnobDelegate, delegate_for_spec,
)


class KnobsSection(QWidget):
    def __init__(self, state: GraphKnobState, debounce_ms: int = 400, parent=None):
        super().__init__(parent)
        self._state = state
        self._debounce_ms = debounce_ms
        self._widgets: dict[str, KnobDelegate] = {}
        self._timers: dict[str, QTimer] = {}
        self._pending: dict[str, object] = {}
        self._suppress_state_signal = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Parameters")
        title.setObjectName("KnobsSectionTitle")
        outer.addWidget(title)

        self._form = QFormLayout()
        self._form.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(self._form)

        for spec in state.specs:
            w = delegate_for_spec(spec, parent=self)
            w.set_value(state.values[spec.name])
            label = spec.label or spec.name
            if spec.unit:
                label = f"{label} [{spec.unit}]"
            self._form.addRow(label, w)
            if spec.description:
                w.setToolTip(spec.description)
            w.value_changed.connect(lambda v, n=spec.name: self._on_widget_changed(n, v))
            self._widgets[spec.name] = w

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._apply_btn = QPushButton("Apply")
        self._apply_btn.setVisible(any(s.apply == "manual" for s in state.specs))
        self._apply_btn.clicked.connect(self.apply_manual)
        btn_row.addWidget(self._apply_btn)
        self._reset_btn = QPushButton("⟳")
        self._reset_btn.setToolTip("Reset all parameters to defaults")
        self._reset_btn.clicked.connect(self.reset_to_defaults)
        btn_row.addWidget(self._reset_btn)
        outer.addLayout(btn_row)

        state.knobs_changed.connect(self._on_state_changed)

    # ----- public API used by tests / overlay click ----------------------
    def widget_for(self, name: str) -> Optional[KnobDelegate]:
        return self._widgets.get(name)

    def reset_to_defaults(self):
        defaults = {s.name: s.default for s in self._state.specs}
        for name, value in defaults.items():
            w = self._widgets[name]
            w.set_value(value)
            w.value_changed.emit(value)

    def apply_manual(self):
        for name, value in list(self._pending.items()):
            spec = next(s for s in self._state.specs if s.name == name)
            if spec.apply == "manual":
                self._commit(name, value)

    # ----- internals -----------------------------------------------------
    def _on_widget_changed(self, name: str, value):
        spec = next(s for s in self._state.specs if s.name == name)
        if spec.apply == "manual":
            self._pending[name] = value
            return
        self._pending[name] = value
        timer = self._timers.get(name)
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda n=name: self._commit_pending(n))
            self._timers[name] = timer
        timer.start(self._debounce_ms)

    def _commit_pending(self, name: str):
        if name not in self._pending:
            return
        self._commit(name, self._pending.pop(name))

    def _commit(self, name: str, value):
        try:
            self._suppress_state_signal = True
            self._state.set_value(name, value)
        except (ValueError, TypeError, KeyError):
            # Invalid value: revert widget to stored value
            w = self._widgets.get(name)
            if w is not None:
                w.set_value(self._state.values.get(name))
        finally:
            self._suppress_state_signal = False

    def _on_state_changed(self, values: dict):
        if self._suppress_state_signal:
            return
        for name, value in values.items():
            w = self._widgets.get(name)
            if w is not None and w.get_value() != value:
                w.set_value(value)
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run pytest tests/test_plotting/test_knob_inspector.py -v
```

Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/plotting/ui/knob_inspector/section.py tests/test_plotting/test_knob_inspector.py
git commit -m "$(cat <<'EOF'
feat(plotting/ui): add KnobsSection — per-graph parameters editor

QFormLayout of delegates driven by a GraphKnobState. One QTimer
debouncer per knob (single-shot, 400ms by default); manual-apply knobs
queue until the Apply button is clicked. Reset button restores
declared defaults.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 15: Mount KnobsSection in the existing graph inspector dock

**Files:**
- Modify: the existing graph-inspector entrypoint (find with the grep below)
- Test: covered by Task 16's screenshot/integration test

- [ ] **Step 1: Locate the inspector dock host**

```bash
grep -rn "class.*Inspector" SciQLop/components/plotting --include="*.py"
```

If no inspector exists yet, it lives in the core panel/inspector layer. Run:

```bash
grep -rn "graph.*property\|graph_properties\|inspector" SciQLop/components/plotting --include="*.py" | head -20
```

Expected: a `GraphInspector` (or similar) widget that already shows axis settings per selected graph.

- [ ] **Step 2: Read the inspector module**

Read whichever module came up. Note where it is given a graph reference (likely a `set_graph(graph)` method or signal-driven setter).

- [ ] **Step 3: Add a "Parameters" group to the inspector**

In that module, when `set_graph(graph)` runs, look up `graph._knob_state` (set in Task 11) and mount a `KnobsSection`:

```python
from SciQLop.components.plotting.ui.knob_inspector.section import KnobsSection

def set_graph(self, graph):
    # ... existing code ...
    self._clear_knobs_section()
    state = getattr(graph, "_knob_state", None)
    if state is not None and state.specs:
        self._knobs_section = KnobsSection(state, parent=self)
        self.layout().addWidget(self._knobs_section)

def _clear_knobs_section(self):
    if getattr(self, "_knobs_section", None) is not None:
        self._knobs_section.setParent(None)
        self._knobs_section.deleteLater()
        self._knobs_section = None
```

The collapsibility comes from being inside the inspector's existing scroll area — no additional decoration unless the inspector already provides a `CollapsibleGroup` widget; in that case, wrap the section in it.

- [ ] **Step 4: Smoke-run inspector tests**

```bash
uv run pytest tests/test_plot_pure_logic.py tests/test_panel_template_integration.py -q
```

Expected: green (or skipped). The full UI integration is covered in Task 16.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/plotting/ui/  # whichever inspector file you modified
git commit -m "$(cat <<'EOF'
feat(plotting/ui): mount KnobsSection in the graph inspector

When the inspector switches to a graph that exposes a GraphKnobState,
a KnobsSection is appended below the existing axis settings; cleared
on every selection change to avoid stale state across graphs.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Chunk 7 — Info-badge overlay on the graph

Goal: a collapsible overlay on parameterized graphs showing a single-line summary like `fft=256 | hann | thr=0.50`. Click → focus the inspector and scroll to the Parameters section.

### Task 16: Knob info-badge overlay widget

**Files:**
- Create: `SciQLop/components/plotting/ui/knob_inspector/badge.py`
- Test: `tests/test_plotting/test_knob_badge.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest

from SciQLop.user_api.knobs import IntKnob, ChoiceKnob, FloatKnob
from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
from SciQLop.components.plotting.ui.knob_inspector.badge import (
    KnobBadge, format_summary,
)


SPECS = [
    IntKnob(name="fft", default=256),
    ChoiceKnob(name="win", default="hann",
               choices=(("Hann", "hann"), ("Hamming", "hamming"))),
    FloatKnob(name="thr", default=0.5),
]


def test_format_summary_short():
    assert format_summary({"fft": 256, "win": "hann", "thr": 0.5}) == \
        "fft=256 | win=hann | thr=0.50"


def test_format_summary_handles_missing_state():
    assert format_summary({}) == ""


def test_badge_updates_on_state_change(qtbot):
    state = GraphKnobState(SPECS)
    b = KnobBadge(state)
    qtbot.addWidget(b)
    assert b.summary_text() == format_summary(state.values)
    state.set_value("fft", 1024)
    assert b.summary_text() == format_summary(state.values)


def test_badge_clicked_emits(qtbot):
    state = GraphKnobState(SPECS)
    b = KnobBadge(state)
    qtbot.addWidget(b)
    received = []
    b.clicked.connect(lambda: received.append(True))
    b._fire_clicked_for_test()
    assert received == [True]
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/test_plotting/test_knob_badge.py -v
```

Expected: FAIL on `ImportError`.

- [ ] **Step 3: Implement KnobBadge**

```python
# SciQLop/components/plotting/ui/knob_inspector/badge.py
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton

from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState


def _format_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def format_summary(values: dict) -> str:
    if not values:
        return ""
    return " | ".join(f"{k}={_format_value(v)}" for k, v in values.items())


class KnobBadge(QFrame):
    clicked = Signal()

    def __init__(self, state: GraphKnobState, parent=None):
        super().__init__(parent)
        self.setObjectName("KnobBadge")
        self._state = state
        self._collapsed = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        self._toggle_btn = QToolButton()
        self._toggle_btn.setText("◐")
        self._toggle_btn.setAutoRaise(True)
        self._toggle_btn.clicked.connect(self.toggle)
        layout.addWidget(self._toggle_btn)

        self._label = QLabel()
        self._label.setObjectName("KnobBadgeText")
        layout.addWidget(self._label)

        self._refresh()
        state.knobs_changed.connect(lambda *_: self._refresh())

    def _refresh(self):
        self._label.setText(format_summary(self._state.values))

    def summary_text(self) -> str:
        return self._label.text()

    def toggle(self):
        self._collapsed = not self._collapsed
        self._label.setVisible(not self._collapsed)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.pos() not in self._toggle_btn.geometry():
            self.clicked.emit()
        super().mousePressEvent(event)

    def _fire_clicked_for_test(self):
        self.clicked.emit()
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run pytest tests/test_plotting/test_knob_badge.py -v
```

Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/plotting/ui/knob_inspector/badge.py tests/test_plotting/test_knob_badge.py
git commit -m "$(cat <<'EOF'
feat(plotting/ui): add KnobBadge collapsible overlay

Per-graph badge showing a one-line summary of current knob values;
clicking emits a signal the panel uses to focus the inspector.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 17: Attach the badge to parameterized graphs

**Files:**
- Modify: `SciQLop/components/plotting/ui/time_sync_panel.py` (extend `_attach_knob_state`)

- [ ] **Step 1: Identify the SciQLopPlots overlay-mount API used by the existing diagnostic overlay**

```bash
grep -rn "DiagnosticOverlay\|overlay\|set_overlay\|add_overlay" SciQLop/components/plotting/ui --include="*.py" | head -20
```

Note the exact API — the badge must mount via the same mechanism (parented to viewport, not top-level) per `sciqlopplots-overlay-viewport-parenting.md`.

- [ ] **Step 2: Extend `_attach_knob_state` to add the badge**

In `time_sync_panel.py`:

```python
def _attach_knob_state(provider, product_path_str, callback, r):
    specs = []
    try:
        specs = provider.get_knobs(product_path_str)
    except Exception:
        log.debug("get_knobs failed for %s", product_path_str, exc_info=True)
    if not specs:
        return
    from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
    from SciQLop.components.plotting.ui.knob_inspector.badge import KnobBadge

    graph = r[1] if hasattr(r, "__iter__") else r
    plot = r[0] if hasattr(r, "__iter__") else None
    state = GraphKnobState(specs, parent=graph)
    graph._knob_state = state
    callback.knob_state = state
    state.knobs_changed.connect(lambda *_: _trigger_refetch(graph))

    if plot is not None:
        viewport = getattr(plot, "viewport", lambda: None)()
        badge = KnobBadge(state, parent=viewport or plot)
        badge.clicked.connect(lambda g=graph: _focus_inspector_for(g))
        graph._knob_badge = badge
        badge.show()


def _focus_inspector_for(graph):
    """Best-effort: raise the inspector dock and select this graph."""
    try:
        from SciQLop.user_api.gui import get_main_window
        mw = get_main_window()
        for d in mw.dock_manager.dockWidgetsMap().values():
            if d.windowTitle() == "Inspector" and not d.isClosed():
                d.raise_()
                d.dockAreaWidget().setCurrentDockWidget(d)
                break
    except Exception:
        log.debug("could not focus inspector", exc_info=True)
```

- [ ] **Step 3: Run the relevant existing tests**

```bash
uv run pytest tests/test_plotting/test_plot_product_knobs.py tests/test_plot_pure_logic.py -q
```

Expected: green (no regression). The badge is mounted but not asserted by these tests; visual check is manual per the spec ("overlay visual polish: manual check").

- [ ] **Step 4: Commit**

```bash
git add SciQLop/components/plotting/ui/time_sync_panel.py
git commit -m "$(cat <<'EOF'
feat(plotting/ui): attach KnobBadge overlay to parameterized graphs

Mounts the badge on the plot viewport (not the toplevel — see
sciqlopplots-overlay-viewport-parenting memory) and wires its click
to focus the Inspector dock.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Chunk 8 — Drop-flow ancillary (discoverability hint + reset menu)

Goal: one-time hint on first parameterized drop, persisted via a `ConfigEntry`; right-click "Reset parameters to defaults" on parameterized graphs.

### Task 18: ConfigEntry for the discoverability-hint dismissal

**Files:**
- Create: `SciQLop/components/plotting/backend/knob_hint_settings.py`
- Test: `tests/test_plotting/test_knob_hint_settings.py`

- [ ] **Step 1: Inspect the ConfigEntry pattern**

Read `SciQLop/components/settings/backend/entry.py` to confirm the API expected (`category`, `subcategory`, `__enter__`/`__exit__` for save).

- [ ] **Step 2: Write the failing test**

```python
import pytest


def test_hint_default_not_dismissed(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from SciQLop.components.plotting.backend.knob_hint_settings import KnobHintSettings
    s = KnobHintSettings()
    assert s.parameterized_drop_hint_dismissed is False


def test_hint_dismissal_persists(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from SciQLop.components.plotting.backend.knob_hint_settings import KnobHintSettings
    with KnobHintSettings() as s:
        s.parameterized_drop_hint_dismissed = True
    s2 = KnobHintSettings()
    assert s2.parameterized_drop_hint_dismissed is True
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
uv run pytest tests/test_plotting/test_knob_hint_settings.py -v
```

Expected: FAIL on `ImportError`.

- [ ] **Step 4: Implement the ConfigEntry**

```python
# SciQLop/components/plotting/backend/knob_hint_settings.py
from typing import ClassVar

from SciQLop.components.settings.backend.entry import ConfigEntry, SettingsCategory


class KnobHintSettings(ConfigEntry):
    category: ClassVar[str] = SettingsCategory.PLOTTING.value
    subcategory: ClassVar[str] = "Knobs"

    parameterized_drop_hint_dismissed: bool = False
```

If `SettingsCategory.PLOTTING` doesn't exist, add the literal `category: ClassVar[str] = "Plotting"`.

- [ ] **Step 5: Run the test to verify it passes**

```bash
uv run pytest tests/test_plotting/test_knob_hint_settings.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add SciQLop/components/plotting/backend/knob_hint_settings.py tests/test_plotting/test_knob_hint_settings.py
git commit -m "$(cat <<'EOF'
feat(plotting/backend): persist parameterized-drop hint dismissal

KnobHintSettings ConfigEntry stores whether the user has dismissed the
one-shot 'this product has parameters — open the inspector' hint, so
it doesn't reappear across sessions.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 19: Show the discoverability hint on first parameterized drop

**Files:**
- Modify: `SciQLop/components/plotting/ui/time_sync_panel.py` (extend `_attach_knob_state`)
- Test: `tests/test_plotting/test_knob_hint_show.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest


def test_hint_shown_once(tmp_path, monkeypatch, qtbot, sciqlop_app):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    shown = []
    monkeypatch.setattr(
        "SciQLop.components.plotting.ui.time_sync_panel._show_knob_hint",
        lambda parent: shown.append(True),
    )
    from SciQLop.components.plotting.ui.time_sync_panel import _maybe_show_knob_hint
    parent = None
    _maybe_show_knob_hint(parent)
    _maybe_show_knob_hint(parent)
    assert shown == [True]


def test_hint_respects_dismissal(tmp_path, monkeypatch, qtbot, sciqlop_app):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from SciQLop.components.plotting.backend.knob_hint_settings import KnobHintSettings
    with KnobHintSettings() as s:
        s.parameterized_drop_hint_dismissed = True
    shown = []
    monkeypatch.setattr(
        "SciQLop.components.plotting.ui.time_sync_panel._show_knob_hint",
        lambda parent: shown.append(True),
    )
    from SciQLop.components.plotting.ui.time_sync_panel import _maybe_show_knob_hint
    _maybe_show_knob_hint(None)
    assert shown == []
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/test_plotting/test_knob_hint_show.py -v
```

Expected: FAIL — `_maybe_show_knob_hint` does not exist.

- [ ] **Step 3: Implement the hint flow**

In `time_sync_panel.py`:

```python
def _show_knob_hint(parent):
    from PySide6.QtWidgets import QMessageBox
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Information)
    box.setWindowTitle("Parameterized product")
    box.setText("This product has tunable parameters — open the Inspector to adjust them.")
    box.setStandardButtons(QMessageBox.Ok)
    box.exec()


def _maybe_show_knob_hint(parent):
    from SciQLop.components.plotting.backend.knob_hint_settings import KnobHintSettings
    s = KnobHintSettings()
    if s.parameterized_drop_hint_dismissed:
        return
    _show_knob_hint(parent)
    with KnobHintSettings() as s:
        s.parameterized_drop_hint_dismissed = True
```

Call `_maybe_show_knob_hint(plot)` from `_attach_knob_state`, after the badge is set up:

```python
if plot is not None:
    # ... badge setup ...
    _maybe_show_knob_hint(plot)
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run pytest tests/test_plotting/test_knob_hint_show.py -v
```

Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/plotting/ui/time_sync_panel.py tests/test_plotting/test_knob_hint_show.py
git commit -m "$(cat <<'EOF'
feat(plotting/ui): one-shot 'parameterized product' discoverability hint

Shown the first time a user drops a product whose provider exposes
knobs; dismissal persists via KnobHintSettings.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 20: Right-click "Reset parameters to defaults" on parameterized graphs

**Files:**
- Modify: graph context-menu builder (find via grep)
- Test: `tests/test_plotting/test_knob_reset_action.py`

- [ ] **Step 1: Locate the per-graph context menu**

```bash
grep -rn "addAction\|contextMenu\|QMenu" SciQLop/components/plotting/ui --include="*.py" | head -20
```

Identify the function that builds per-graph (or per-plot) context menus. If none exists yet, the panel-level `contextMenuEvent` is the right host (in `time_sync_panel.py`); add a graph-targeted entry there.

- [ ] **Step 2: Write the failing test**

```python
def test_reset_action_resets_state(qtbot):
    from SciQLop.user_api.knobs import IntKnob
    from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
    from SciQLop.components.plotting.ui.time_sync_panel import _build_knob_reset_action

    state = GraphKnobState([IntKnob(name="fft", default=256, min=64, max=4096)])
    state.set_value("fft", 1024)
    action = _build_knob_reset_action(state, parent=None)
    action.trigger()
    assert state.values == {"fft": 256}
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
uv run pytest tests/test_plotting/test_knob_reset_action.py -v
```

Expected: FAIL — `_build_knob_reset_action` not defined.

- [ ] **Step 4: Add the helper and wire it**

In `time_sync_panel.py`:

```python
from PySide6.QtGui import QAction


def _build_knob_reset_action(state, parent):
    action = QAction("Reset parameters to defaults", parent)

    def _do_reset():
        defaults = {s.name: s.default for s in state.specs}
        state.set_all(defaults)

    action.triggered.connect(_do_reset)
    return action
```

In the existing context-menu builder (the file located in Step 1), if `graph._knob_state` is set and has specs, append `_build_knob_reset_action(graph._knob_state, menu)` to the menu.

- [ ] **Step 5: Run the test to verify it passes**

```bash
uv run pytest tests/test_plotting/test_knob_reset_action.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add SciQLop/components/plotting/ui/time_sync_panel.py tests/test_plotting/test_knob_reset_action.py
git commit -m "$(cat <<'EOF'
feat(plotting/ui): graph context-menu 'Reset parameters to defaults'

Adds a per-graph context-menu action visible only when the graph has a
non-empty knob state.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Chunk 9 — Debug plots (`%%vp --debug`) preserve knob_values

Goal: across `%%vp --debug` cell re-runs, the existing debug-panel graph's `knob_values` is snapshotted before re-plot and re-applied after — and the cell's pre-evaluation uses those values.

### Task 21: Snapshot/restore knob_values across debug-panel re-plot

**Files:**
- Modify: `SciQLop/user_api/virtual_products/debug.py`
- Test: `tests/test_virtual_products/test_debug_knobs.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from typing import Annotated

from SciQLop.user_api.knobs import Knob


@pytest.fixture(autouse=True)
def _clean_registry():
    from SciQLop.user_api.virtual_products.registry import _registry
    _registry._entries.clear()
    yield
    _registry._entries.clear()


def test_debug_replot_preserves_knob_values(qtbot, sciqlop_app):
    from SciQLop.user_api.virtual_products.magic import vp_magic

    cell = (
        "from typing import Annotated\n"
        "from SciQLop.user_api.knobs import Knob\n"
        "def my_vp(start: float, stop: float,\n"
        "          fft: Annotated[int, Knob(min=64, max=4096)] = 256) -> Scalar:\n"
        "    import numpy as np\n"
        "    n = 8\n"
        "    return np.linspace(start, stop, n), np.zeros(n) + fft\n"
    )
    vp_magic("--debug --start 2020-01-01 --stop 2020-01-02", cell, local_ns={})
    from SciQLop.user_api.virtual_products.registry import _registry
    entry = _registry.get("my_vp")
    panel = entry.panel
    assert panel is not None
    plots = panel.plots()
    assert plots, "debug panel should have a plot"
    graph = plots[0]
    state = getattr(graph, "_knob_state", None)
    assert state is not None and state.values["fft"] == 256

    state.set_value("fft", 1024)
    qtbot.wait(50)

    # Re-run cell — knob value must persist
    vp_magic("--debug --start 2020-01-01 --stop 2020-01-02", cell, local_ns={})
    plots = panel.plots()
    new_state = getattr(plots[0], "_knob_state", None)
    assert new_state is not None
    assert new_state.values["fft"] == 1024


def test_debug_replot_drops_unknown_keeps_valid_known(qtbot, sciqlop_app):
    from SciQLop.user_api.virtual_products.magic import vp_magic

    cell_a = (
        "from typing import Annotated\n"
        "from SciQLop.user_api.knobs import Knob\n"
        "def my_vp(start: float, stop: float,\n"
        "          fft: Annotated[int, Knob(min=64, max=4096)] = 256,\n"
        "          old_knob: int = 1) -> Scalar:\n"
        "    import numpy as np\n"
        "    n = 8\n"
        "    return np.linspace(start, stop, n), np.zeros(n) + fft\n"
    )
    cell_b = (
        "from typing import Annotated\n"
        "from SciQLop.user_api.knobs import Knob\n"
        "def my_vp(start: float, stop: float,\n"
        "          fft: Annotated[int, Knob(min=64, max=4096)] = 256) -> Scalar:\n"
        "    import numpy as np\n"
        "    n = 8\n"
        "    return np.linspace(start, stop, n), np.zeros(n) + fft\n"
    )

    vp_magic("--debug --start 2020-01-01 --stop 2020-01-02", cell_a, local_ns={})
    from SciQLop.user_api.virtual_products.registry import _registry
    entry = _registry.get("my_vp")
    state = entry.panel.plots()[0]._knob_state
    state.set_value("fft", 1024)
    state.set_value("old_knob", 5)
    qtbot.wait(50)

    vp_magic("--debug --start 2020-01-01 --stop 2020-01-02", cell_b, local_ns={})
    new_state = entry.panel.plots()[0]._knob_state
    assert new_state.values == {"fft": 1024}
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/test_virtual_products/test_debug_knobs.py -v
```

Expected: FAIL — re-plot wipes the knob state.

- [ ] **Step 3: Snapshot before clear, push after re-plot**

In `SciQLop/user_api/virtual_products/debug.py`, modify `_plot_on_debug_panel` to snapshot pre-clear and re-apply post-plot:

```python
def _snapshot_knob_values(panel):
    snapshot = {}
    for plot in panel.plots():
        for child in plot.children():
            state = getattr(child, "_knob_state", None)
            if state is not None:
                snapshot.update(state.values)
    return snapshot


def _restore_knob_values(panel, snapshot):
    if not snapshot:
        return
    for plot in panel.plots():
        for child in plot.children():
            state = getattr(child, "_knob_state", None)
            if state is not None:
                state.set_all(snapshot)


def _plot_on_debug_panel(panel, func_name: str):
    snapshot = _snapshot_knob_values(panel)
    from SciQLop.components.plotting.ui.time_sync_panel import plot_product
    from SciQLopPlots import PlotType
    panel.clear()
    path = func_name.split('/')
    plot_product(panel, path, plot_type=PlotType.TimeSeries)
    _restore_knob_values(panel, snapshot)
```

The test for `test_debug_replot_drops_unknown_keeps_valid_known` is satisfied because `set_all` runs through `validate_dict` (load-rules: known kept, unknown dropped, missing → default).

- [ ] **Step 4: Use the snapshot in pre-evaluation as well**

In `SciQLop/user_api/virtual_products/magic.py`, when `args.debug` and the entry already has a `panel` with knob state, use those values for the cell-level pre-eval:

```python
def _persisted_knob_values(entry):
    panel = getattr(entry, "panel", None)
    if panel is None:
        return {}
    try:
        from SciQLop.user_api.virtual_products.debug import _snapshot_knob_values
        return _snapshot_knob_values(panel)
    except Exception:
        return {}


# inside vp_magic, replace `cached_data = func(start, stop)` with:
preserved = _persisted_knob_values(_registry.get(func_name)) if func_name in _registry._entries else {}
try:
    cached_data = func(start, stop, **preserved)
except TypeError:
    # Spec mismatch (e.g. removed kwarg) — fall back to defaults-only call.
    cached_data = func(start, stop)
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
uv run pytest tests/test_virtual_products/test_debug_knobs.py -v
```

Expected: 2 PASS.

- [ ] **Step 6: Verify existing debug tests still pass**

```bash
uv run pytest tests/test_vp_debug_layout.py tests/test_vp_debug_workbench.py -q
```

Expected: green.

- [ ] **Step 7: Commit**

```bash
git add SciQLop/user_api/virtual_products/debug.py SciQLop/user_api/virtual_products/magic.py tests/test_virtual_products/test_debug_knobs.py
git commit -m "$(cat <<'EOF'
feat(virtual_products/debug): preserve knob_values across cell re-runs

Snapshots the existing debug-panel graph's knob_values before
panel.clear() and re-applies them after the re-plot (load-rules drop
removed knobs and reset invalid ones). The cell-level pre-evaluation
also uses those values, so the diagnostic overlay reflects what the
user actually sees on the debug graph.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Chunk 10 — ipywidgets binding for `%%vp --debug` (best-effort)

Goal: when the kernel is running inside an ipywidgets-capable frontend, emit a small widget strip under `%%vp --debug` cells, bound bidirectionally to the debug-panel graph's `GraphKnobState`. Silently no-op if ipywidgets isn't present or the comm-manager check fails.

### Task 22: Frontend detection and widget factory (pure logic)

**Files:**
- Create: `SciQLop/user_api/virtual_products/ipywidgets_binding.py`
- Test: `tests/test_virtual_products/test_ipywidgets_binding.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
import sys
import types

from SciQLop.user_api.knobs import (
    IntKnob, FloatKnob, BoolKnob, ChoiceKnob, StringKnob,
)


def _install_fake_ipywidgets(monkeypatch):
    fake = types.ModuleType("ipywidgets")

    class _Widget:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
            self._observers = []

        def observe(self, fn, names="value"):
            self._observers.append((fn, names))

        def _fire(self, new):
            old = getattr(self, "value", None)
            self.value = new
            for fn, _ in self._observers:
                fn(types.SimpleNamespace(name="value", old=old, new=new))

    class IntSlider(_Widget): pass
    class FloatSlider(_Widget): pass
    class Checkbox(_Widget): pass
    class Dropdown(_Widget): pass
    class Text(_Widget): pass
    class HBox(_Widget):
        def __init__(self, children=()):
            super().__init__(children=children)

    fake.IntSlider = IntSlider
    fake.FloatSlider = FloatSlider
    fake.Checkbox = Checkbox
    fake.Dropdown = Dropdown
    fake.Text = Text
    fake.HBox = HBox
    monkeypatch.setitem(sys.modules, "ipywidgets", fake)
    return fake


def test_widget_for_int(monkeypatch):
    fake = _install_fake_ipywidgets(monkeypatch)
    from SciQLop.user_api.virtual_products.ipywidgets_binding import widget_for_spec
    w = widget_for_spec(IntKnob(name="fft", default=256, min=64, max=4096))
    assert isinstance(w, fake.IntSlider)
    assert w.min == 64 and w.max == 4096 and w.value == 256


def test_widget_for_float(monkeypatch):
    fake = _install_fake_ipywidgets(monkeypatch)
    from SciQLop.user_api.virtual_products.ipywidgets_binding import widget_for_spec
    w = widget_for_spec(FloatKnob(name="thr", default=0.5, min=0.0, max=1.0, step=0.01))
    assert isinstance(w, fake.FloatSlider)


def test_widget_for_choice(monkeypatch):
    fake = _install_fake_ipywidgets(monkeypatch)
    from SciQLop.user_api.virtual_products.ipywidgets_binding import widget_for_spec
    w = widget_for_spec(ChoiceKnob(name="win", default="hann",
                                    choices=(("Hann", "hann"), ("Hamming", "hamming"))))
    assert isinstance(w, fake.Dropdown)
    assert w.options == [("Hann", "hann"), ("Hamming", "hamming")]


def test_widget_for_bool(monkeypatch):
    fake = _install_fake_ipywidgets(monkeypatch)
    from SciQLop.user_api.virtual_products.ipywidgets_binding import widget_for_spec
    w = widget_for_spec(BoolKnob(name="cache", default=True))
    assert isinstance(w, fake.Checkbox)
    assert w.value is True


def test_widget_for_string(monkeypatch):
    fake = _install_fake_ipywidgets(monkeypatch)
    from SciQLop.user_api.virtual_products.ipywidgets_binding import widget_for_spec
    w = widget_for_spec(StringKnob(name="s", default="x"))
    assert isinstance(w, fake.Text)


def test_no_ipywidgets_returns_none(monkeypatch):
    monkeypatch.setitem(sys.modules, "ipywidgets", None)
    from SciQLop.user_api.virtual_products import ipywidgets_binding
    monkeypatch.setattr(ipywidgets_binding, "_import_ipywidgets",
                         lambda: None)
    assert ipywidgets_binding.widget_for_spec(IntKnob(name="x", default=0)) is None


def test_bidirectional_binding(qtbot, monkeypatch):
    fake = _install_fake_ipywidgets(monkeypatch)
    from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
    from SciQLop.user_api.virtual_products.ipywidgets_binding import (
        bind_state_to_widgets,
    )

    state = GraphKnobState([IntKnob(name="fft", default=256, min=64, max=4096)])
    widget = fake.IntSlider(min=64, max=4096, value=256)
    bind_state_to_widgets(state, {"fft": widget})

    # Widget → state
    widget._fire(1024)
    assert state.values["fft"] == 1024

    # State → widget (no echo loop)
    state.set_value("fft", 512)
    assert widget.value == 512
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/test_virtual_products/test_ipywidgets_binding.py -v
```

Expected: FAIL on `ImportError`.

- [ ] **Step 3: Implement the binding module**

```python
# SciQLop/user_api/virtual_products/ipywidgets_binding.py
from typing import Optional

from SciQLop.user_api.knobs import (
    KnobSpec, IntKnob, FloatKnob, BoolKnob, ChoiceKnob, StringKnob,
)


def _import_ipywidgets():
    try:
        import ipywidgets  # type: ignore
        return ipywidgets
    except Exception:
        return None


def _has_widget_comm() -> bool:
    try:
        from IPython import get_ipython
        ip = get_ipython()
        if ip is None:
            return False
        return getattr(ip, "kernel", None) is not None
    except Exception:
        return False


def widget_for_spec(spec: KnobSpec):
    w = _import_ipywidgets()
    if w is None:
        return None
    if isinstance(spec, IntKnob):
        return w.IntSlider(min=spec.min if spec.min is not None else -2**31,
                           max=spec.max if spec.max is not None else 2**31 - 1,
                           step=spec.step or 1, value=spec.default,
                           description=spec.label or spec.name)
    if isinstance(spec, FloatKnob):
        return w.FloatSlider(min=spec.min if spec.min is not None else -1e18,
                             max=spec.max if spec.max is not None else 1e18,
                             step=spec.step or 0.01, value=spec.default,
                             description=spec.label or spec.name)
    if isinstance(spec, BoolKnob):
        return w.Checkbox(value=spec.default,
                          description=spec.label or spec.name)
    if isinstance(spec, ChoiceKnob):
        return w.Dropdown(options=list(spec.choices), value=spec.default,
                          description=spec.label or spec.name)
    if isinstance(spec, StringKnob):
        return w.Text(value=spec.default,
                      description=spec.label or spec.name)
    return None


def bind_state_to_widgets(state, widgets: dict):
    suppress = {"flag": False}

    def _on_widget(name):
        def _handler(change):
            if suppress["flag"]:
                return
            try:
                state.set_value(name, change.new)
            except Exception:
                pass
        return _handler

    for name, widget in widgets.items():
        widget.observe(_on_widget(name), names="value")

    def _on_state(values):
        suppress["flag"] = True
        try:
            for name, widget in widgets.items():
                if name in values and getattr(widget, "value", None) != values[name]:
                    widget.value = values[name]
        finally:
            suppress["flag"] = False

    state.knobs_changed.connect(_on_state)


def display_widgets_for_state(state):
    """Return an HBox of widgets bound to state, or None if unsupported."""
    w = _import_ipywidgets()
    if w is None or not _has_widget_comm():
        return None
    widgets = {}
    for spec in state.specs:
        widget = widget_for_spec(spec)
        if widget is not None:
            widgets[spec.name] = widget
    if not widgets:
        return None
    bind_state_to_widgets(state, widgets)
    return w.HBox(children=tuple(widgets.values()))
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run pytest tests/test_virtual_products/test_ipywidgets_binding.py -v
```

Expected: 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/user_api/virtual_products/ipywidgets_binding.py tests/test_virtual_products/test_ipywidgets_binding.py
git commit -m "$(cat <<'EOF'
feat(virtual_products): ipywidgets binding for %%vp --debug knobs

widget_for_spec maps each KnobSpec to an ipywidget; bind_state_to_widgets
wires widgets ↔ GraphKnobState bidirectionally with a reentrancy guard.
display_widgets_for_state returns an HBox or None when ipywidgets isn't
available — pure best-effort.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 23: Surface the widget strip from `%%vp --debug`

**Files:**
- Modify: `SciQLop/user_api/virtual_products/magic.py`
- Test: covered by manual notebook check (the IPython-display side-effect is awkward to assert headlessly)

- [ ] **Step 1: Add the display call**

In `vp_magic`, after `handle_debug(...)` returns, query the freshly-(re)created debug panel's first plot's `_knob_state` and offer it to the binding module:

```python
if args.debug:
    from SciQLop.user_api.virtual_products.debug import handle_debug
    if not needs_eval:
        start, stop = _resolve_time_range(args, func)
    handle_debug(args, func, func_name, entry, type_info,
                 start, stop,
                 cached_data=cached_data, eval_error=eval_error,
                 eval_elapsed=eval_elapsed)

    try:
        from SciQLop.user_api.virtual_products.ipywidgets_binding import (
            display_widgets_for_state,
        )
        from IPython.display import display
        panel = entry.panel
        plots = panel.plots() if panel is not None else []
        if plots:
            state = getattr(plots[0], "_knob_state", None)
            if state is not None and state.specs:
                box = display_widgets_for_state(state)
                if box is not None:
                    display(box)
    except Exception:
        _get_log().debug("ipywidgets binding skipped", exc_info=True)
```

- [ ] **Step 2: Smoke-check the existing magic tests**

```bash
uv run pytest tests/test_vp_magic.py tests/test_vp_magic_integration.py tests/test_virtual_products/ -q
```

Expected: green. (The display branch is a try/except — failure modes are silent by design.)

- [ ] **Step 3: Commit**

```bash
git add SciQLop/user_api/virtual_products/magic.py
git commit -m "$(cat <<'EOF'
feat(virtual_products/magic): emit ipywidgets strip on %%vp --debug

When the debug panel has a parameterized graph and the kernel exposes
a comm manager, displays an HBox of widgets bound bidirectionally to
the GraphKnobState. Silently no-ops elsewhere — the inspector remains
the universal fallback.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Final integration checks

These are not new code — they're guard rails to run after the last task in chunk 10.

- [ ] **Step 1: Full focused test sweep**

```bash
uv run pytest -q tests/test_knobs/ tests/test_virtual_products/ tests/test_plotting/ tests/test_speasy_provider/ \
                 tests/test_vp_magic.py tests/test_vp_magic_integration.py \
                 tests/test_vp_debug_layout.py tests/test_vp_debug_workbench.py \
                 tests/test_vp_types.py tests/test_vp_validation.py
```

Expected: green.

- [ ] **Step 2: Full test suite (slower)**

```bash
uv run pytest -q
```

Expected: green. Investigate any failure before merge.

- [ ] **Step 3: Manual sanity in the running app**

Start SciQLop with `uv run sciqlop` and:

1. From a notebook cell, define a parameterized VP with a `%%vp` cell containing an `Annotated[int, Knob(min=64, max=4096)] = 256` kwarg. Drop it on a panel; check the inspector shows the parameter and that changing the value triggers a re-fetch within ~400 ms.
2. From AMDA inventory (`speasy`-aware), expand a templated parameter (e.g. `jedi_i90_flux`) and drop it. Check that its argument(s) appear in the inspector and that switching the choice re-fetches.
3. From `%%vp --debug`, run a cell with an `Annotated[int, Knob(min=...)] = ...` kwarg. Confirm the debug panel renders, the inspector shows the parameter, and the ipywidgets strip (if a JupyterLab frontend is connected) appears under the cell.
4. Re-run the cell with a different default and a renamed knob — confirm the inspector reflects the new spec and that valid known values are preserved while unknown ones are dropped (no crash).

If any of these fail, fix in a focused commit and re-run the full suite.

- [ ] **Step 4: Update CHANGELOG**

Add a "Knobs (parameterized data products)" entry to `CHANGELOG.md` under the unreleased section. Reference the spec file path and the public API surface (`SciQLop.user_api.knobs`, `create_virtual_product(..., knobs_model=...)`, `panel.plot_product(..., knob_values=...)`).

- [ ] **Step 5: Push to `jeandet` (only when the user asks)**

Per memory: never push without an explicit "push" from the user.

---

## Self-review against the spec

Spec coverage check:

| Spec section | Tasks | Notes |
|---|---|---|
| Provider contract (`get_knobs`, `knobs=`) | 5 | additive, byte-identical when `knobs=None` |
| Knob spec dataclasses | 1 | five subclasses, frozen |
| `Knob(...)` Annotated marker | 2 | optional fields, no defaults forced |
| Introspection (callback + Pydantic) | 4 | Literal → ChoiceKnob, ge/le/multiple_of/pattern |
| Speasy translation | 12 | generic ArgumentIndex walk, no AMDA-specific code |
| Per-graph state lifecycle | 9, 10, 11 | defaults at drop, validate on set, signal-driven re-fetch |
| EasyProvider dispatch | 6 | kwargs path + Pydantic-model path |
| Inspector section + delegates | 13, 14, 15 | per-knob debouncer, manual-apply, reset |
| Info-badge overlay | 16, 17 | viewport parenting, click → focus inspector |
| Drop flow & ancillary | 18, 19, 20 | hint persisted via ConfigEntry, reset menu |
| Debug plots preserve knob_values | 21 | snapshot/restore around panel.clear |
| ipywidgets binding | 22, 23 | best-effort, silent no-op |
| Hot-reload (schema changes) | 7, 8 | signature_changed kwarg-aware; refresh provider specs |
| Cache key includes knobs | 9 (`canonical_hash`), used implicitly via `knobs=` in callback closures (cache key on the C++ side keys off the unique callback identity, which now varies per (provider, knob_values) tuple by virtue of the wrapper's call signature) | If a regression test reveals over-caching, extend `_plot_product_callback` to include `state.cache_key()` in `__hash__`/`__eq__` |

Open questions resolved during planning:

- **Speasy data provider location**: `SciQLop/plugins/speasy_provider/speasy_provider.py` — confirmed.
- **Request-object layout**: knobs travel via `_plot_product_callback`/`_specgram_callback` closures, not a request object — Task 10 wires them through the existing callback API.
- **GraphKnobState location**: Python-side wrapper attached as `graph._knob_state` (Task 11). C++ binding only needed if the cache-key check above flags an issue.
- **Inspector delegate factory shared with settings**: deferred — knob_inspector ships its own delegate factory now to avoid blocking on a settings refactor; consolidation is a follow-up.

Placeholder scan: nothing left as TBD. Type/method consistency: `set_value`, `set_all`, `replace_specs`, `cache_key` used consistently across all tasks. `delegate_for_spec` returns `KnobDelegate`, the same type read by `KnobsSection.widget_for(...)`. `state.knobs_changed.emit(dict)` is the only signal payload type.
