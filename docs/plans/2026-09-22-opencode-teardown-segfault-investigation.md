# Full-suite teardown segfault — investigation and proposed fix

Date: 2026-09-22
Branch: `main` @ `89f765c9f` (nothing committed by this investigation)
Scope: the SIGSEGV that happens **after** `pytest` prints its `N passed` summary, at
interpreter finalization.

## Verdict

The crash is real and the mechanism is confirmed from PySide6 source, from the CI
backtrace in the handover doc, and from cores captured in this environment. It is
**not** a SciQLopPlots/NeoQCP bug and cannot be fixed there.

A genuinely safe mitigation exists and is implemented in the working tree
(`tests/conftest.py`, uncommitted): **do not destroy the leftover widgets at all.**
Instead, at `pytest_sessionfinish`, detach Python's ownership of every still-alive
widget so Shiboken's interpreter-exit sweep skips them. Nothing is destroyed, so none
of the destructive teardown paths that crashed in four previous attempts are reached.

Full suite with the fix: **3117 passed, 17 skipped, 1 xfailed, exit 0** (was 3113
passed before the 4 new tests; no crash, no new failure).

## Root cause

At interpreter exit, Python runs PySide's registered cleanup, which ends in
`PySide::destroyQCoreApplication()`. That function (PySide
`libpyside/pyside.cpp`) does, in order:

1. `BindingManager::visitAllPyObjects(&destructionVisitor, ...)` — for **every**
   wrapped `QObject` where `Shiboken::Object::hasOwnership()` is true, it calls
   `Shiboken::Object::setValidCpp(pyObj, false)` then
   `Shiboken::callCppDestructor<QObject>(...)`.
2. `delete app`.

So the sweep force-destroys every Python-owned `QObject` **before** the
`QApplication` is deleted, i.e. outside Qt's normal teardown order. For a widget this
recurses through its whole Qt child tree (`QWidget::~QWidget` -> `deleteChildren`).

`hasOwnership()` is true for:

- objects created in Python with no C++ parent — e.g. the bare
  `TimeSyncPanel(parent=None)` panels many tests build and never dock; and
- **widgets of a Python subclass even when they have a C++ parent** — a
  `TimeSyncPanel(parent=container)` is still Python-owned (measured, see below).

Destroying those at interpreter exit is fatal for two widget kinds in this app:

- `QRhiWidget` subclasses (`SciQLopPlot`): `~QRhiWidget()` calls
  `QRhi::removeCleanupCallback()` on an RHI that is already gone -> SIGSEGV. This is
  the CI crash, and it started when SciQLopPlots 0.37.0 moved the plots onto
  `QRhiWidget`.
- QtAds dock trees: `ads::CDockWidgetTab::setVisible` -> `CDockWidget::features()`
  reads a dangling `QWeakPointer` -> SIGSEGV.

Fix direction: **nothing that owns an RHI or a QtAds dock tree may still be
force-destroyed when the interpreter finalizes.** Either it is destroyed safely
before then (hard, see below) or it is not destroyed at all.

## Evidence

### Cores in this environment (5 SIGSEGV + 1 SIGABRT, all today)

All five SIGSEGV cores from the previous session were **self-inflicted by that
session's own force-destroy sweeps**, not the finalize path:

| pid | time | top of stack | what it is |
|-----|------|--------------|------------|
| 1795921 | 10:14 | `QToolBar::actionEvent` -> `QWidget::removeAction` via `shiboken6.delete` | sweep attempt |
| 1810006 | 10:44 | same as above | sweep attempt |
| 1826251 | 11:14 | Python script -> `CDockWidgetTab::setVisible` | sweep attempt |
| 1856486 | 11:38 | `CDockAreaWidget::~` -> `QToolBar::actionEvent` | sweep attempt |
| 1860438 | 12:03 | `CDockWidgetTab::setVisible` -> `QWeakPointer::isNull` | sweep attempt |

None of them show `PySide::runCleanupFunctions` / `_Py_Finalize`. So every crash the
previous session observed was caused by trying to destroy the widgets, which is
exactly the operation this fix removes.

### No local reproduction of the original crash

The original finalize crash did **not** reproduce locally, in either the committed
baseline or the fix (consistent with the handover's "Linux flaky"; macOS is
deterministic-ish). A full-suite baseline run of the unmodified tree was green
(3113 passed, exit 0). Minimal standalone reproducers (N bare
`SciQLopMultiPlotPanel` / N bare `SciQLopPlot`, with and without an event loop,
`close`/`delete`/`quit` variants) all exited 0. The crash needs full-suite accumulated
state; it is not cheaply reproducible. Validation of the fix therefore rests on the
mechanism plus the CI backtrace, not on a local red->green.

### Ownership semantics (measured)

`hasOwnership` is readable via the exported C++ symbol
`_ZN8Shiboken6Object12hasOwnershipEP9SbkObject`:

| object | `hasOwnership` |
|--------|----------------|
| top-level `QWidget()` | True |
| `QWidget(parent)` (plain child) | False |
| `TimeSyncPanel(parent=container)` | **True** |
| after `releaseOwnership` | False, and `shiboken6.isValid` stays True |

This is why releasing only `topLevelWidgets()` was incomplete and the final version
uses `allWidgets()`. (`shiboken6.ownedByPython()` is unreliable for Python
subclasses and should not be used as the test oracle; the tests assert on the
`hasOwnership` symbol instead.)

### Finalize path with the fix

A run under `QT_FATAL_WARNINGS=1` turns the exit-time warning into a SIGABRT core.
Its backtrace shows the finalize path:

```
#14 QtWidgets.abi3.so
#15 PySide::destroyQCoreApplication() + 116
#16 PySide::runCleanupFunctions()
#17 QtCore.abi3.so
#18 atexit_callfuncs
#19 _Py_Finalize
#20 Py_RunMain
```

There is **no `visitAllPyObjects` / `destructionVisitor` / `QRhiWidget` frame**: with
the fix, the sweep destroyed no widgets. The remaining destructor chain is the
`QApplication` deletion, which resets SciQLopPlots' global static
`QtGlobalStatic::ApplicationHolder<Q_QAS__plots_model>` — see residual issues.

## The change (working tree, uncommitted)

`tests/conftest.py`, after `_standalone_panels()`:

```python
def _release_leftover_widget_ownership(widgets=None):
    """Hand Python's ownership of still-alive widgets to C++ so Shiboken's
    interpreter-shutdown sweep (`PySide::destroyQCoreApplication` ->
    `BindingManager::visitAllPyObjects` -> `destructionVisitor`) skips them.
    ...
    Shiboken exposes `releaseOwnership` in C++ but not in its Python module, so call
    the exported symbol directly. `SbkObject*` is the Python object itself, i.e.
    `id(w)`; the symbol is Itanium-ABI, so this is a no-op on platforms without it
    (Linux/macOS CI both have it)."""
    import ctypes
    import glob
    import os

    import shiboken6
    from PySide6.QtWidgets import QApplication

    libs = glob.glob(os.path.join(os.path.dirname(shiboken6.__file__),
                                  "libshiboken6*.so*"))
    if not libs:
        return
    release = getattr(ctypes.CDLL(libs[0]),
                      "_ZN8Shiboken6Object16releaseOwnershipEP9SbkObject", None)
    if release is None:
        return
    release.argtypes = [ctypes.c_void_p]
    release.restype = None
    if widgets is None:
        app = QApplication.instance()
        if app is None:
            return
        widgets = app.allWidgets()
    for w in widgets:
        if shiboken6.isValid(w):
            release(ctypes.c_void_p(id(w)))
```

and `pytest_sessionfinish` now ends with:

```python
    _release_leftover_widget_ownership()
```

instead of the previous force-destroy sweep. The old
`_destroy_leaked_top_level_widgets` helper is removed.

`tests/test_gui_leftover_sweep.py` (untracked) covers the helper with 4 tests:
detach ownership from a leftover widget; harmless with an empty list; skip an
already-destroyed widget; and cover a **parented Python-subclass** widget
(`TimeSyncPanel(parent=container)`) — the case `topLevelWidgets()` missed.

`tests/test_sciqlopplots_thread_guards.py` also carries a small independent fix
(join the background thread before teardown); keep it.

### Why this is safe

- `releaseOwnership` is pure bookkeeping: it flips an ownership flag. No Qt
  destructor, no event, no reparent, no signal runs. It cannot hit the QtAds /
  QToolBar reentrancy or the RHI use-after-free, because those only happen during
  destruction.
- It runs last, at `pytest_sessionfinish`, after every test; nothing observes the
  ownership state afterwards.
- The only cost is that the leftover C++ widgets are never freed. The process is
  about to exit, so the OS reclaims them (peak RSS is unchanged: 4307 MB with the
  fix vs 4308 MB baseline).
- If the mangled symbol is ever absent (different ABI/toolchain), the helper is a
  silent no-op and the suite behaves exactly like the committed baseline.

## Validation

Command:
`uv run python scripts/test_memguard.py 7000 <log> -- uv run pytest -n0 -p no:cacheprovider -q --timeout=120 --ignore=tests/fuzzing`

| run | result | time | peak | exit | `QBasicTimer` warnings |
|-----|--------|------|------|------|------------------------|
| baseline (HEAD, diff stashed) | 3113 passed, 17 skipped, 1 xfailed | 285 s | 4308 MB | 0 | 0 |
| fix, `topLevelWidgets()` (superseded) | 3116 passed, 17 skipped, 1 xfailed | 286 s | 4340 MB | 0 | 2 |
| **fix, `allWidgets()` (final)** | **3117 passed, 17 skipped, 1 xfailed** | 306 s | 4307 MB | **0** | 2 |

Subset checks: panel-heavy files 53-60 passed, exit 0; the 4 new tests pass on their
own. `tests/conftest.py` diff is minimal (69 insertions, 7 deletions) — the earlier
324-line version was churn from the editor's auto-formatter and was discarded
(`/tmp/opencode/experimental.diff`).

At `pytest_sessionfinish` the fix run still sees a large pile of leftovers that the
old sweep would have force-destroyed (497 `QWidget`, 274 `QScrollBar`, 9
`CDockWidget`, 8 `CDockAreaTitleBar`, 8 `CDockAreaTabBar`, 10 `CDockWidgetTab`, 14
`QToolBar`, ...). All of those are now left alone.

## Residual issues (documented, not blockers)

1. **Two `QBasicTimer::start: current thread's event dispatcher has already been
   destroyed` warnings at exit.** Baseline 0, fix 2 (deterministic, both full-suite
   and subset scale). The `QT_FATAL_WARNINGS` core shows the cause: with widgets left
   alive, SciQLopPlots' global static
   `QtGlobalStatic::ApplicationHolder<Q_QAS__plots_model>::reset()` runs during
   `delete app` (after the dispatcher is gone) and starts a timer that is simply
   dropped. Exit code stays 0; nothing is corrupted. If the noise is unwanted, the
   clean option is a targeted `qInstallMessageHandler` filter for that exact string
   at session end — deliberately not added, to avoid masking real occurrences.

2. **No local red->green.** The original crash could not be reproduced locally in
   either tree, so this fix is validated by the mechanism, the CI backtrace, and the
   absence of any regression — not by a locally-fixed segfault. If a deterministic
   reproducer is ever found, it should be added to the suite.

3. **`_TscatDriverWorker already deleted` atexit error is pre-existing** (present in
   the baseline run too) and unrelated to this change.

4. **ctypes on a mangled symbol** is the only way to reach `releaseOwnership`:
   `shiboken6.Shiboken.invalidate()` is a no-op for this purpose and
   `shiboken6.Shiboken.Object` exposes no ownership setter. The lookup is guarded and
   degrades to a no-op.

## Rejected alternatives

- **Force-destroy the leftovers** (the previous session's four attempts:
  `shiboken6.delete`, `hide`+`deleteLater`+flush, with/without the shared main
  window). Each crashed in a different piece of Qt/QtAds this project does not own
  (`QToolBar::actionEvent`, `ads::CDockWidgetTab::setVisible`). Destroying these
  widgets at interpreter exit is fundamentally unsafe, not just badly ordered.
- **Revert everything and accept the crash** (handover option 2). This leaves the CI
  red. It is the fallback only if the ownership release is judged too clever; the
  committed baseline does nothing at session end and would keep crashing on macOS.
- **Only make `_release_gui_leftovers` flush unconditional** (handover option 3).
  Does not help the widgets that escape per-test detection (e.g. panels inside a
  top-level container) and does nothing for whatever is still alive at session end.

## Recommendation

Adopt the `_release_leftover_widget_ownership` session-finish step, keep the
thread-guard fix, and drop the force-destroy sweep. It removes the interpreter-exit
destruction of RHI/QtAds widgets without ever running a destructor, so it cannot
re-enter the crash paths. The 2 benign `QBasicTimer` warnings and the inability to
reproduce locally are the honest caveats.

**Production follow-up (separate decision):** `SciQLop/sciqlop_app.py` (`main()`)
does `loop.exec()` then `sys.exit(exit_code)` with no explicit teardown, so the same
sweep runs at app exit there too — production is exposed to the same class of crash
whenever more than one `QRhiWidget` survives to finalization. The same
ownership-release (or an explicit, ordered teardown) before `sys.exit` would harden
it. Not changed here to keep this investigation test-scoped.

## Working-tree state (uncommitted, by design)

- `M tests/conftest.py` — the fix above.
- `M tests/test_sciqlopplots_thread_guards.py` — +6 lines, background-thread join.
- `?? tests/test_gui_leftover_sweep.py` — 4 tests for the new helper.
- `?? docs/plans/2026-09-22-opencode-teardown-segfault-investigation.md` — this file.

Nothing was committed or pushed. Unrelated pre-existing untracked artifacts remain in
the tree (`importlib.metadata`, `setWidget`, other `docs/plans/*`); left untouched.
