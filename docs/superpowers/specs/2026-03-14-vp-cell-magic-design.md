# Virtual Product Cell Magic (`%%vp`)

## Summary

A Jupyter cell magic that replaces `create_virtual_product()` as the primary way to declare virtual products, with an integrated debug workbench mode for iterative development.

## Motivation

Scientists writing virtual products face multiple pain points:
- Many ways for a callback to silently fail (blank plot, no feedback)
- No quick iteration loop — must re-register products, create new panels
- The `create_virtual_product()` API requires knowledge of `VirtualProductType`, labels, and other boilerplate

## Design

### The `%%vp` Cell Magic

The minimal way to declare a virtual product:

```python
%%vp

def magnetic_field(start, stop) -> Vector["Bx", "By", "Bz"]:
    data = speasy.get_data(...)
    return data
```

Running the cell registers `magnetic_field` in the product tree. Re-running updates the callback in-place via a mutable wrapper (see Architecture).

#### Type Annotations

The return annotation determines product type and labels. Provided types (importable from `SciQLop.user_api.virtual_products`):

```python
Scalar                                      # single value per timestamp
Scalar["Temperature"]                       # with explicit label
Vector["Bx", "By", "Bz"]                   # exactly 3 components, with labels
Vector                                      # 3 components, default labels
MultiComponent["E1", "E2", "E3", "E4"]     # N components, with labels
Spectrogram                                 # 2D time-frequency
```

Implementation: lightweight types using `__class_getitem__` to store labels as metadata. No runtime cost. When no label is provided for `Scalar`, the function name is used.

#### Inference Mode

If no return annotation is present, `%%vp` runs the callback once (using the same time range resolution as debug mode — see below), inspects the return value shape, and infers the type:

- `(N,)` -> Scalar
- `(N, 3)` -> Vector
- `(N, M)` where M != 3 -> MultiComponent
- Spectrogram is **never inferred** — it must be declared explicitly (the heuristic would be ambiguous)

An info message is shown: `"Inferred type: Vector (3 components) — add -> Vector to make explicit"`.

#### Optional Flags

- `--path "space/physics/B_field"` — control the product tree location (default: function name)
- `--debug` — open a debug workbench panel (see below)
- `--start 2020-01-01` — debug/inference time range start (ISO 8601, UTC assumed)
- `--stop 2020-01-02` — debug/inference time range stop

### Debug Workbench (`%%vp --debug`)

```python
%%vp --debug --start 2020-01-01 --stop 2020-01-02

def magnetic_field(start, stop) -> Vector["Bx", "By", "Bz"]:
    data = speasy.get_data(...)
    return data
```

Running this cell:
1. Registers the virtual product (same as `%%vp`)
2. Opens (or reuses) a scratch pad panel pinned to the specified time range
3. Runs the callback immediately and shows data or diagnostic overlay
4. Re-running the cell updates the callback and refreshes the debug panel

#### Debug Time Range Resolution

The time range is resolved in priority order (also used for inference mode):

1. Explicit flags: `--start` and `--stop`
2. Function default arguments: `def f(start=datetime(2020,1,1), stop=datetime(2020,1,2))`
3. Current view range from an existing panel (if any is open)
4. Fallback: last 24 hours from now

Using function defaults doubles as documentation — anyone reading the function sees a recommended test range.

#### Scratch Pad Panel Lifecycle

- The panel is identified by function name — one panel per virtual product being debugged.
- If the user manually closes the panel and re-runs with `--debug`, a new panel is created.
- Removing `--debug` from the cell and re-running does **not** close the panel — it just stops updating it. The user closes it manually when done.

#### Typical Workflow

1. Start with `%%vp --debug` while developing
2. Edit the function, re-run the cell, see results immediately
3. When happy, remove `--debug`, re-run — product stays registered, debug panel stops updating

### Diagnostic Overlays

When `--debug` is active, the scratch pad panel always shows feedback — never a blank plot.

#### Exception in callback

```
[X] ZeroDivisionError in magnetic_field(), line 4
  -> return x, y / 0
```

Traceback is filtered to show only the user's code, not SciQLop internals.

#### None returned

```
[!] No data returned for [2020-01-01, 2020-01-02]
```

#### Shape mismatch

```
[X] Declared Vector (3 components) but got shape (1000, 5)
```

#### Auto-fixable issue (dtype coercion, etc.)

```
[!] X-axis float32 -> converted to float64
```

Data still plots, warning shown.

#### Success

Thin status bar at the bottom of the panel:

```
[ok] 1000 pts, (1000,3) float64, 0.12s
```

The overlay is a semi-transparent widget over the plot area. Clears on next successful run. The success bar persists.

#### Without `--debug`

The validation pipeline still runs (same code path), but errors go to the standard log instead of an overlay. All virtual products benefit from better error messages than today's silent blank plot.

## Architecture

### Mutable Callback Wrapper and Re-run Strategy

The magic maintains a registry keyed by function name:

```python
registry[func_name] = {
    "wrapper": MutableCallback(...),
    "product_type": Vector,
    "labels": ["Bx", "By", "Bz"],
    "panel": <debug_panel_ref or None>,
}
```

```python
class MutableCallback:
    def __init__(self, callback):
        self.callback = callback

    def __call__(self, start, stop):
        return self.callback(start, stop)
```

On re-run, the magic compares the new signature (product type + labels) against the stored one:

- **Same signature:** just swap `wrapper.callback = new_function` — cheap, no teardown. Existing panels pick up the new code on the next data request or refresh.
- **Signature changed** (e.g., `Scalar` → `Vector`, or labels changed): tear down old provider + product tree node, create new `MutableCallback` + `EasyProvider`, re-register in the product tree. If `--debug` is active, recreate the plot on the scratch pad panel with the new configuration.

### Thread Safety

The validation pipeline runs in whatever thread the C++ plot engine calls the callback from (potentially non-GUI). Diagnostic results must be dispatched to the GUI thread via Qt signal/slot to update the overlay widget.

### Magic Registration

The `%%vp` magic is registered with IPython via `@register_cell_magic` when `SciQLop.user_api.virtual_products` is imported. Since the embedded kernel is already running when the user types in the console, the magic is available immediately.

### New/Modified Files

- `SciQLop/user_api/virtual_products/types.py` — `Scalar`, `Vector`, `MultiComponent`, `Spectrogram` annotation types
- `SciQLop/user_api/virtual_products/magic.py` — `%%vp` cell magic implementation (parsing, registration, debug panel wiring, mutable callback registry)
- `SciQLop/user_api/virtual_products/validation.py` — validation pipeline (shape/dtype checks, exception filtering, diagnostic message generation)
- `SciQLop/components/plotting/ui/diagnostic_overlay.py` — semi-transparent overlay widget + success status bar
- `SciQLop/user_api/virtual_products/__init__.py` — re-export new types, register magic on import

### Data Flow

```
%%vp cell execution
  -> parse flags (--debug, --start, --stop, --path)
  -> extract function definition + return annotation
  -> infer product type + labels from annotation (or run callback once to infer from shape)
  -> first run: create MutableCallback wrapper + EasyProvider, register in product tree
     re-run: swap wrapper.callback to new function
  -> if --debug:
       -> resolve time range (flags > defaults > view > fallback)
       -> open/reuse scratch pad panel (keyed by function name)
       -> run callback through validation pipeline
       -> dispatch diagnostics to GUI thread
       -> show data on panel OR diagnostic overlay
```

### Validation Pipeline

A function `validate_and_call(callback, start, stop, declared_type, labels)` that:

1. Calls the callback inside try/except
2. On exception: returns a `Diagnostic` with filtered traceback
3. On None: returns a `Diagnostic` with "no data" message
4. On success: checks shape/dtype against declared type, returns data + optional warnings
5. Returns `ValidationResult(data=..., diagnostics=[...], elapsed=...)`

This pipeline is used by both debug overlays and standard logging.
