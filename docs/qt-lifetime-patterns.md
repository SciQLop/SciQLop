# Qt/PySide6 lifetime patterns

How to wire signals and clean up in SciQLop without segfaulting during
panel/plot destruction.

## The hazard

PySide6 (Shiboken) wraps every C++ `QObject` in a Python proxy. When the
C++ object is mid-destruction, calling a method through that proxy is
**undefined behaviour** — the C++ subobject's vtable has demoted to the
base class, and the wrapper may end up calling unrelated virtual slots
on the dying widget. Observed symptom: SIGSEGV inside
`QWidget::sharedPainter()`, called from a Shiboken-generated wrapper
like `Sbk_SciQLopPlotFunc_x_axis`.

This is not specific to SciQLopPlots — it's a property of how Qt and
Shiboken cooperate around destruction. **It is not, and cannot be,
fixed inside SciQLopPlots.** It has to be avoided at the call site.

The destruction sequence that triggers it:

```
1. user closes the dock that owns a panel
2. ~SciQLopTimeSeriesPlot runs  (derived dtor body completes)
3. ~SciQLopPlot runs            (vtable demotes step by step)
4. ~QWidget runs                (widget-state torn down)
5. ~QObject runs deleteChildren() → child InspectorExtensions deleted
6. each child emits destroyed   ← Python slots run here
7. ~QObject finishes, the plot itself emits its own destroyed
```

A Python slot wired to a **child's** `destroyed` (step 6) that reaches
back into the **parent** plot through the Shiboken wrapper is calling
methods on a half-destructed C++ object. That's the crash class.

## The rule

> **Never call methods on a parent object from a slot wired to one of
> its children's `destroyed` signals.**

`destroyed` is a notification ("the pointer is now gone, drop your
reference"), not a hook for cleanup logic that touches the dying parent.

This rule generalises beyond plots — it applies to any QObject parent
exposed to Python, not just `SciQLopPlot`.

## Safe patterns, in order of preference

### 1. Use Qt's receiver-context `connect()` overload

The 5-argument form: `signal.connect(context, slot)`. Qt disconnects the
slot when **either** endpoint dies, before either reaches an invalid
state. No `destroyed` handler, no manual disconnect, no cached
references, no cleanup logic.

```python
# Bad — connection has no lifetime owner; you must remember to disconnect
axis.range_changed.connect(lambda r: self._on_range(r))

# Good — Qt auto-disconnects when self dies
axis.range_changed.connect(self, lambda r: self._on_range(r))
```

This is the idiomatic Qt answer for "this connection should live as long
as both endpoints" and works in PySide6 the same way it does in C++.

### 2. Cache the reference at connect time, not at disconnect time

If you can't use pattern 1 (e.g. the receiver is a plain Python object,
not a QObject), grab the reference you'll need for `disconnect()` the
moment you `connect()` — never re-fetch it from a parent during
teardown.

```python
# Bad — reaches through the wrapper at teardown
def dispose(self):
    self._plot.x_axis().range_changed.disconnect(self._slot)
    #    ^^^^^^^^^^^^^^^ wrapper call during ~QWidget → segfault

# Good — cached when the plot was fully alive
def __init__(self, plot):
    self._x_axis = plot.x_axis()
    self._x_axis.range_changed.connect(self._slot)

def dispose(self):
    if self._slot is not None:
        self._x_axis.range_changed.disconnect(self._slot)
        self._slot = None
```

This is what `LayerRenderer.dispose()` does
(`SciQLop/user_api/layers/_renderer.py`) after a SIGSEGV in production.
See commit `293a7afa` for the worked example.

### 3. Explicit `dispose()` / `unbind()` instead of relying on `destroyed`

When teardown is structured (multiple connections, file handles, async
tasks), give the object a `dispose()` method that the **owner** calls
**before** delete, while everything is still fully alive. Use
`destroyed` only as the last-ditch backstop ("owner forgot to call
dispose"), and at that point limit yourself to dropping local
references — never call into other QObjects.

### 4. If you must reach into another object during destruction, use `shiboken6.isValid`

```python
import shiboken6
if shiboken6.isValid(obj):
    obj.something()
```

`isValid` is cheap and safe. It does **not** rescue you from the
half-destructed-parent crash class — by the time the wrapper enters
the method, validity has already been checked and the prologue may
still touch widget state — so prefer patterns 1–3. Use `isValid` for
cross-thread or workspace-reload cases where the wrapper might just be
stale, not mid-destruction.

## Anti-patterns to grep for

- `obj.destroyed.connect(...)` where the slot body calls methods on
  `obj`'s **parent**, or fetches sibling references via the parent.
- `self._plot.x_axis()` (or `.y_axis()`, `.legend()`, `.color_scale()`,
  …) inside a `dispose()`, `__del__`, or destruction-time callback.
- A `disconnect()` call that re-traverses the QObject tree to find its
  own counterpart — connect-time caching is always safer.

## What this means for plugin and layer authors

Layers, extensions, and plugins that observe a plot's axes or sub-objects
should:

1. **Connect** through the receiver-context form when both ends are
   QObjects, OR cache the signal source at connect time.
2. **Provide an explicit `dispose()`** for structured teardown. The
   plot/panel calls it deterministically; don't rely on Python GC or
   `destroyed`.
3. **Never call back into the owning plot during `destroyed`.** If you
   need to know "the plot is going away", connect to a structured event
   from the panel that fires *before* destruction, not after it starts.

If a future SciQLopPlots release exposes a pre-destruction signal on
plots, layers can migrate to it. Until then, the rules above are the
contract.

## See also

- `SciQLopPlots/docs/backlog-2026-05-16.md` — original incident report
  with full gdb trace
- Commit `293a7afa` — `LayerRenderer.dispose` cache-at-connect fix
- Commit `eb87dc34` — initial hardening of user_api plot wrappers
