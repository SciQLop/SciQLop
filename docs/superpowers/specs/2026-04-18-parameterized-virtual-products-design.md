# Parameterized Virtual Products ("Knobs") — Design

**Status**: Spec, pending implementation plan.
**Author**: Alexis Jeandet (with Claude).
**Date**: 2026-04-18.

## Goal

Give any data product — Python-defined virtual products (VPs) and provider-sourced products (Speasy/AMDA templated parameters) — a declarative set of runtime-tunable parameters ("knobs") that users can edit per-graph from the UI and from the notebook, with live re-fetch.

## Motivating use cases

- `%%vp` spectrogram callback exposes `fft_size`, `window`, `threshold`; user drops it on a panel and live-tunes from the inspector.
- AMDA `jedi_i90_flux` exposes its `lookdir` choice; user drops it twice on overlapping graphs with different values to compare.
- A Python VP uses a Pydantic `BaseModel` for its knob schema so it can reuse validation/constraints already expressed there.

## Scope (v1)

In:

- Provider-agnostic `DataProvider` extension: `get_knobs(product)` + optional `knobs=` on `get_data(...)`.
- Public knob API in `SciQLop/user_api/knobs/` (spec dataclasses + `Knob` metadata marker + introspection).
- Two declaration paths for Python VPs: `Annotated[T, Knob(...)]` kwargs and Pydantic model (`knobs_model=`).
- Speasy plugin translation: generic walk of `SpeasyIndex` for `ArgumentListIndex`/`ArgumentIndex` children → `ChoiceKnob` list (no AMDA-specific code).
- Per-graph `knob_values: dict[str, Any]` initialized from provider defaults at drop time.
- Inspector section with per-spec delegate widgets; info-badge overlay on the graph; defaults-first drop.
- Debounced re-fetch (~400 ms); optional per-knob `apply="manual"` opt-out.
- Knob values in the data-request cache key.
- `%%vp --debug` preserves graph knob_values across cell re-runs; uses them in pre-eval.
- ipywidgets binding for `%%vp --debug` cells (best-effort; graceful fallback to inspector when ipywidgets or the frontend is unavailable).

Out:

- Persistence of knob values across sessions / in the workspace manifest (SciQLop does not persist graph state today; knob values inherit that limitation).
- Named presets per VP.
- Global per-VP "last used values."
- Range/interval knobs, file-path knobs, color knobs.
- Dependent knobs (knob B's choices depend on knob A's value).
- Group/section headers inside the inspector's Parameters section.

## Architecture

### Provider contract

`DataProvider` (in `SciQLop/components/plotting/backend/data_provider.py`) gains:

```python
class DataProvider:
    def get_knobs(self, product: str) -> list[KnobSpec]:
        """Return knob declarations for this product (empty = not parameterized)."""
        return []

    def get_data(self, product, start, stop, knobs: dict | None = None):
        ...
```

Changes are additive. Providers that don't override `get_knobs` return `[]` and behave exactly like today; `knobs=None` callers and providers stay on the pre-knobs code path (byte-identical regression guard).

### Public API — `SciQLop/user_api/knobs/`

```
SciQLop/user_api/knobs/
├── __init__.py          # re-exports Knob, KnobSpec, IntKnob, FloatKnob, BoolKnob, ChoiceKnob, StringKnob
├── specs.py             # spec dataclasses
├── introspection.py     # callback → list[KnobSpec] (Annotated kwargs + Pydantic)
└── values.py            # validate / coerce / canonical_hash
```

`specs.py` — frozen dataclasses, `KnobSpec` base + one subclass per type:

```python
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
    choices: tuple[tuple[str, Any], ...] = ()  # (display_name, value) pairs

@dataclass(frozen=True, slots=True)
class StringKnob(KnobSpec):
    default: str = ""
    pattern: str = ""  # optional regex validation
```

`Knob(...)` is a lightweight marker/metadata class used inside `Annotated[T, Knob(...)]`. It carries `min`, `max`, `step`, `label`, `unit`, `description`, `apply`, `choices`, `pattern` — all optional — and is resolved into the correct `*Knob` subclass by `introspection.py` based on the annotated type `T`.

### Knob declaration — notebook / `%%vp` path

Knob kwargs on the callback, with defaults:

```python
from typing import Annotated, Literal
from SciQLop.user_api.knobs import Knob

def my_fft(start: float, stop: float,
           fft_size: Annotated[int, Knob(min=64, max=4096, step=64, label="FFT size")] = 256,
           window: Literal["hann", "hamming", "blackman"] = "hann",
           threshold: Annotated[float, Knob(min=0.0, max=1.0, step=0.01)] = 0.5) -> Spectrogram:
    ...
```

Rules:

- A kwarg becomes a knob iff it has a default and is not one of the reserved params (`start`, `stop`).
- `Annotated[T, Knob(...)]` supplies metadata; bare `T` uses defaults-only.
- `Literal[...]` auto-becomes a `ChoiceKnob` with `(value, value)` pairs.
- If name/key differ, use `Annotated[str, Knob(choices=[("Hann", "hann"), ...])]`.
- `bool`, `int`, `float`, `str` map to the obvious spec types.

### Knob declaration — programmatic / Pydantic path

Single model-typed kwarg:

```python
class FFTKnobs(BaseModel):
    fft_size: int = Field(256, ge=64, le=4096, multiple_of=64)
    window: Literal["hann", "hamming"] = "hann"
    threshold: float = Field(0.5, ge=0.0, le=1.0)

def my_fft(start, stop, knobs: FFTKnobs) -> Spectrogram:
    ...

create_virtual_product(path, my_fft, product_type=..., knobs_model=FFTKnobs)
```

Field constraints (`ge`, `le`, `multiple_of`, `pattern`) map directly to spec fields. `Field(..., json_schema_extra={"knob": {...}})` supplies UI-only metadata Pydantic doesn't natively express (label, unit, description, apply).

`introspection.py` returns `list[KnobSpec]` from either path; downstream code never branches on declaration style.

### Speasy provider translation (provider-agnostic)

The Speasy plugin implements `get_knobs` as a generic walk:

```python
def get_knobs(self, product: str) -> list[KnobSpec]:
    index = self._resolve_index(product)
    args_node = _find_child_of_type(index, ArgumentListIndex)
    if args_node is None:
        return []
    return [_argument_index_to_knob(arg) for arg in args_node]
```

`_argument_index_to_knob` reads generic attributes (`name`, `type`, `choices`, `default`) straight from the Speasy node. **No AMDA-specific code** — AMDA today, any future provider that populates `ArgumentIndex` tomorrow.

Knob schemas are pulled fresh each time they're needed (graph creation, inspector open). Inventory reloads surface automatically; no startup-time freeze.

`get_data` forwards: `spz.get_data(product, start, stop, product_inputs=knobs or {})`.

For v1, Speasy arguments are all `type="list"` / `"generated-list"` → `ChoiceKnob`. Future numeric/bool argument types extend `_argument_index_to_knob` with a new branch; the spec taxonomy is already in place.

### Data flow — knob change to rendered data

```
Inspector widget change
  → debouncer (per-graph QTimer, ~400 ms, single-shot)
  → graph.set_knob_value(name, value)
      - validate against KnobSpec (coerce, clamp, choice-membership)
      - store in graph.knob_values
      - emit graph.knobs_changed(dict)
  → request pipeline
      - cancel in-flight fetch for this graph (existing behavior)
      - new request (product, start, stop, knob_values)
      - cache lookup keyed by (product, start, stop, canonical_hash(knob_values))
  → DataProvider.get_data(product, start, stop, knobs=knob_values)
  → graph receives SpeasyVariable, re-renders
  → info-badge overlay updates summary
```

- Debounce lives in the inspector widget (UI concern, not pipeline concern).
- Manual-apply knobs (`apply="manual"`) bypass the debouncer and push on "Apply" click.
- Cache key: `canonical_hash` sorts keys and normalizes values (floats to fixed precision); `knobs=None` hashes to a fixed sentinel, identical to today's key.

### Graph state

New field: `knob_values: dict[str, Any]`.

New signal: `knobs_changed(dict)`.

Lifecycle:

- **Drop time**: `knob_values = {k.name: k.default for k in provider.get_knobs(product)}`.
- **Setter**: `graph.set_knob_value(name, value)` validates against spec. Invalid → reject with log warning; inspector widget resets to stored value.
- **Bulk set**: `graph.knob_values = new_dict` validates each, applies the load-rules (known keys kept if valid, unknown dropped, missing → default).
- **Programmatic**: `panel.plot_product(product, knob_values={...})` optional kwarg on the user API.

Unparameterized graphs: `knob_values` stays empty (or absent), `knobs=None` flows through, zero overhead.

### EasyProvider dispatch

```python
def get_knobs(self, product):
    return self._knob_specs  # cached once at VP registration

def get_data(self, product, start, stop, knobs=None):
    if self._knobs_model is not None:
        model = self._knobs_model(**(knobs or {}))
        return self._user_get_data(start, stop, knobs=model)
    return self._user_get_data(start, stop, **(knobs or {}))
```

Backward compat: if `knobs` is falsy and the callback has no knob kwargs, the call is identical to today's behavior.

### UI

**Inspector section** (inside the existing graph inspector panel):

- Collapsible "Parameters" group, visible only when `provider.get_knobs(product)` returns non-empty.
- Per-spec delegate widgets, reusing the pattern from `components/settings/ui/settings_delegates/`. Factored shared factory between settings and knob UIs (reuse-not-copy).
- `QFormLayout` with `label: widget [unit]` rows; description in widget tooltip.
- One `QTimer` debouncer per knob widget (single-shot, `~400 ms`), coalescing rapid changes on that widget only — changes on different widgets don't starve each other.
- "⟳" button resets all knobs to declared defaults.

**Delegates (v1)**:

- `IntKnob` → `QSpinBox`; if both bounds set and range ≤ 100, render `QSlider + QSpinBox`.
- `FloatKnob` → `QDoubleSpinBox`; same slider promotion rule.
- `BoolKnob` → `QCheckBox`.
- `ChoiceKnob` → `QComboBox` (display name shown, value stored).
- `StringKnob` → `QLineEdit` with optional `QRegularExpressionValidator` from `pattern`.

**Info-badge overlay** on the graph:

- Collapsible overlay (existing SciQLopPlots overlay API).
- Collapsed: icon. Expanded: single-line summary like `fft=256 | hann | thr=0.50`.
- Click: raises inspector, scrolls to Parameters for this graph.
- Not created on unparameterized graphs.

**Drop flow**:

- Parameterized product drop → immediate graph with default knob values. No modal.
- One-time discoverability hint on first parameterized drop ("This product has parameters — open the inspector to tune them"). Dismissable. Dismissal persisted via a new `ConfigEntry` (see `settings-system.md`) so the hint doesn't reappear across sessions.

**Ancillary**:

- Right-click on parameterized graph → "Reset parameters to defaults".

### Debug plots (`%%vp --debug`)

- **Pre-evaluation uses persisted knob values**: cell-level `func(start, stop)` becomes `func(start, stop, **knob_snapshot)` where `knob_snapshot` is empty on first run, or the existing debug-panel graph's `knob_values` validated against the new spec on subsequent runs (load-rules: known-and-valid kept, unknown dropped, missing → default).
- **Debug panel re-plot preserves knob_values**: `debug.py` snapshots the old graph's knob_values before `panel.clear()`, then pushes the snapshot onto the new graph (bulk-set path applies load-rules).
- **Diagnostic overlay already covers knob-triggered fetches**: `MutableCallback.after_call` fires on every data fetch, including knob-driven ones; `DiagnosticOverlay` updates. No new plumbing.
- **Spec-valid-but-logic-broken knob combinations**: callback exceptions are caught by `EasyProvider._debug_get_data` → `validate_and_call` → `Diagnostic("error", ...)` → overlay. Unchanged.

### ipywidgets binding for `%%vp --debug` (best-effort)

When ipywidgets and the frontend support it:

- `%%vp --debug` emits a widget strip under the cell: one widget per knob, bound bidirectionally to the debug-panel graph's `knob_values`.
- Widget change → `graph.set_knob_value(name, value)` (same debounce as inspector).
- `graph.knobs_changed` → `widget.value = ...`, with a reentrancy guard to prevent echo loops.
- Widgets per spec type: `IntKnob` → `IntSlider` or `BoundedIntText` (huge ranges); `FloatKnob` → `FloatSlider`; `BoolKnob` → `Checkbox`; `ChoiceKnob` → `Dropdown`; `StringKnob` → `Text`.

Frontend detection: guarded import of `ipywidgets`; check the active shell has a widget-compatible comm manager. If not, silently skip — the inspector dock is the fallback everywhere.

### Hot-reload (schema changes)

`%%vp` cell edits that change kwargs (add / rename / retype / remove a knob) flip `RegistryEntry.signature_changed` (already tracked in `registry.py`). New behavior on that branch:

- Extract new spec via `introspection.py`.
- Per-graph migration: knobs removed → drop from `knob_values`; added → default; retyped/re-constrained → re-validate; clamp or reset if invalid (log warning).
- Re-push spec to any subscribed inspector panel; emit `knobs_changed` so UI resyncs.

Body-only edits (same kwargs): `MutableCallback.callback = new_callback`; knob spec unchanged; in-flight values stay valid. Already works today, unchanged.

### Edge cases

- **Reserved kwarg names**: `start`, `stop`, and (when `knobs_model=` is used) the model kwarg name. Rejected at registration.
- **Namespace isolation**: Python VP knob names (callback kwargs) and Speasy knob names (inventory argument names) live on separate providers; no collision.
- **Varargs / varkwargs on callback** (`*args`/`**kwargs`): treat as "no knobs," warn once at registration.
- **`cachable=True` with knobs**: cachability remains the user's responsibility; cache key now includes knobs, so stale-hit risk goes down.
- **Debug panel orphaning**: `entry.panel` dead `QObject` — `_panel_is_alive` already handles. Unchanged.

## Modules touched

**New**:

- `SciQLop/user_api/knobs/__init__.py`, `specs.py`, `introspection.py`, `values.py`.
- `SciQLop/components/plotting/ui/knob_inspector/` (inspector section + info-badge overlay + delegate widgets).
- `SciQLop/user_api/virtual_products/ipywidgets_binding.py` (best-effort).
- `tests/test_knobs/`, `tests/test_virtual_products/test_knobs_easy_provider.py`, `tests/test_virtual_products/test_vp_magic_knobs.py`, `tests/test_virtual_products/test_debug_knobs.py`, `tests/test_speasy_provider/test_knobs_argument_index.py`, `tests/test_plotting/test_request_knobs.py`, `tests/test_plotting/test_knob_inspector.py`.

**Modified**:

- `SciQLop/components/plotting/backend/data_provider.py` — `get_knobs`, `knobs=` on `get_data`.
- `SciQLop/components/plotting/backend/easy_provider.py` — implement `get_knobs`; dispatch `knobs` to user callback (kwargs or Pydantic model).
- `SciQLop/user_api/virtual_products/registry.py` — knob migration on schema change; forward knob kwargs through `MutableCallback`.
- `SciQLop/user_api/virtual_products/magic.py` — `%%vp` introspection picks up knob kwargs; optional ipywidgets strip on `--debug`.
- `SciQLop/user_api/virtual_products/debug.py` — preserve knob_values across re-plot; pre-eval uses persisted values.
- Speasy plugin provider — `get_knobs` generic `ArgumentIndex` walk; `get_data` forwards `product_inputs`. (Exact file pinned down in the implementation plan — see Open questions.)
- Request pipeline — `knob_values` threaded through the data-request object; cache key includes canonical hash. (Exact files pinned down in the implementation plan.)
- Graph object — `knob_values` field + `knobs_changed` signal + setter. (Python-side wrapper by default; C++ side only if binding requires it.)
- `panel.plot_product(...)` user API — optional `knob_values=` kwarg.

## Testing

Mirrors code layout. Key regression guards:

- `knobs=None` / unparameterized VPs are byte-identical in cache-key and provider-call behavior.
- `%%vp` magic preserves knob_values on body-only reload; migrates correctly on schema change.
- Debug panel re-plot preserves knob_values.
- Speasy `get_knobs` works for synthetic `SpeasyIndex` without touching the real network.

UI tests via `pytest-qt` + `pytest-xvfb` (existing conftest setup, 2560x1440).

Not tested: overlay visual polish (manual check), specific QSS values, AMDA live inventory.

## Open questions for implementation-plan phase

- Exact location of the Speasy data provider in the plugins tree, and the `SpeasyIndex` resolver's current API (some of this is known from `jupyqt-integration.md`-adjacent code but not confirmed for knobs).
- Exact request-object layout (the pipeline between graph and provider) — needs a short exploration to pin down where `knob_values` threads through.
- Graph object — whether `knob_values` lives on the Python-side wrapper or on the SciQLopPlots C++ graph. Python-side is default; C++ only if there's a binding reason.
- Whether the inspector delegate factory should be extracted before or during this work (minor refactor of `components/settings/ui/settings_delegates/` to share with knob_inspector).
