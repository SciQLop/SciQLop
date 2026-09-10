# Speasy out-of-process fetch — design

**Date:** 2026-09-10
**Status:** proposed

## Problem

Panning over large-cadence products (MMS1 FGM survey: 16.8M points / 268MB per
12-day fetch) stalls SciQLop's render loop for 90-400ms per fetch, 25 times in
6 seconds during a fast pan. Root cause (full trail in `[[project-mms-fgm-gil-convoy]]`
memory): `speasy.core.direct_archive_downloader`'s per-fragment fetch loop
(14 sequential CDF reads + merge for that query) does many rapid GIL
acquire/release cycles in a tight loop — a classic CPython GIL convoy. Each
individual step releases the GIL fine in isolation; the *combined* sequence,
measured with a time-resolved spin-thread probe, showed the GIL held for
essentially the entire ~700ms call. This starves Qt-Main even though nothing
in the chain is doing anything wrong on its own.

Reducing the convoy's severity (fewer fragments, batched cache lookups) is
possible but doesn't remove the underlying coupling: as long as
`SpeasyPlugin.get_data()` runs in SciQLop's own process, its GIL is Qt-Main's
GIL. This design removes that coupling structurally instead.

## What already exists (verified, not assumed)

SciQLop already has a mature, production-proven out-of-process worker system
— `SciQLop/components/plotting/backend/remote/`:

- `registry.py` (`RemoteRegistry`): `register(path, callback, arity)`
  cloudpickles a callable once; `worker_for(path)` returns (spawning if
  needed) one persistent `RemoteWorker` per plugin, keyed by
  `plugin_key_for()` (the callback's top-level package name).
- `worker_handle.py` (`RemoteWorker`): spawns a real `subprocess.Popen`
  (`sys.executable -m ...remote.worker`), a `multiprocessing.connection`
  duplex socket for control messages, `QSocketNotifier`-driven async reply
  pump — no polling, no blocking the Qt event loop.
- `worker.py` / `protocol.py` / `shm_pool.py`: the worker computes and
  writes results into a `multiprocessing.shared_memory` segment; only a
  segment name + array layout (shape/dtype/offset) crosses the socket.
  Bulk array data is never serialized or copied across the process boundary.
- `channel.py` (`RemoteChannel`): per-graph main-side state machine; opens
  the named segment (zero-copy view), hands it to the C++ plottable, and
  manages the segment's lifetime against outstanding numpy/C++ references.
- `easy_provider.py`: the only current consumer. `EasyProvider(...,
  out_of_process=True)` registers a closure wrapping a user virtual-product
  callback. Used by `sciqlop_radio` (`plugins_sciqlop/sciqlop_radio`) by
  default for live continuous streams — explicitly *not* for static
  snapshots (`dock.py`'s `_PlotGroup.out_of_process`, comment: "out-of-process
  would just add pointless IPC overhead" for already-parsed in-memory data).

**Measured, not assumed** (`/tmp/.../bench_remote_worker.py`, real subprocess,
real shared memory, 200 sequential round trips against a small payload):
warm steady-state round trip is median 0.156ms, p95 0.196ms — negligible
against a typical speasy fetch (tens to hundreds of ms even cache-warm).
Cold start (worker spawn + subprocess import of SciQLop/speasy + connect)
measured 1.85s once and 32s once on the same machine — highly load-sensitive,
and a real, user-visible one-time cost if left to happen on the first fetch.

**What's missing:** `SpeasyPlugin` (`SciQLop/plugins/speasy_provider/speasy_provider.py`),
the built-in "Speasy" catalog provider MMS1 FGM and everything else in the
product tree goes through, has no `out_of_process` option. Only
`EasyProvider`-based virtual products can go remote today. The remote
reduction path (`reduction.py`) also has two gaps that block re-adding
Speasy's own post-processing.

## Goals

- Every fetch through the built-in Speasy provider runs in the existing
  remote worker, unconditionally — not opt-in, not size-gated.
- The worker is warm before the user can trigger a fetch that needs it.
- No behavior change versus today's in-process `SpeasyPlugin.get_data()`:
  same FILLVAL handling, same (now-fixed) sortedness guarantee, same values.

## Non-goals

- Building new IPC/subprocess/shared-memory infrastructure — none needed.
- Size-adaptive or opt-in-per-product routing — ruled out: no reliable
  pre-fetch size signal exists (checked: CDAWeb parameter metadata has no
  structured cadence field; sample rate appears only as free text inside
  `CATDESC`, e.g. "(8 or 16 S/s)", ambiguous and not a sound basis for a
  threshold), and steady-state overhead is too small to be worth gating.
- True dynamic runtime migration (measure an actual fetch, then move a
  *live* graph from in-process to remote). Would need swapping a graph's
  underlying C++ provider pipeline at runtime — real new scope, not
  justified once "always remote" carries near-zero steady-state cost.
- Extending this to other built-in (non-Speasy) providers. The registry
  mechanism is provider-agnostic, so nothing here blocks it, but it's out
  of scope for this change.

## Design

### 1. Eager worker warm-up at SciQLop startup

Trigger `remote_registry().worker_for(<speasy plugin_key>)` (or an
equivalent explicit warm-up call) during SciQLop's own startup sequence —
not lazily on first registration. This pays the variable 1.85s-32s cold
cost once, off the user's critical path, before any plot exists to need it.

### 2. Registering a product as remote, at graph-creation time

When a user creates a graph for a Speasy product, `speasy_id` is resolved
from the clicked `ProductsModelNode` exactly as today (main process, needs
the live inventory tree — this cannot move to the worker). Build a small
stateless closure over that resolved `speasy_id`:

```python
def _build_remote_speasy_fetch(speasy_id: str, kwargs_base: dict):
    def _remote_fetch(start, stop, **knobs):
        v = spz.get_data(speasy_id, start, stop, **{**kwargs_base, **knobs})
        if v:
            return v.replace_fillval_by_nan(inplace=True, convert_to_float=True)
        return None
    return _remote_fetch
```

This is exactly `SpeasyPlugin.get_data()`'s existing body, relocated — no
new logic, no behavior change. Register it via `remote_registry().register(...)`
and create the graph through the `add_remote_*` factory instead of the
normal one, mirroring `EasyProvider`'s existing pattern
(`easy_provider.py:197-203`) one-for-one.

### 3. Fixing the remote reduction path (`reduction.py`)

Two changes, both benefit every remote provider, not just Speasy:

- `_epoch_seconds` (line 14) has the identical redundant-copy shape just
  fixed in speasy's own `datetime64_to_epoch`
  (`.astype("datetime64[ns]").astype("int64").astype(np.float64) / 1e9`).
  Same fix: view instead of astype for the reinterpretation step, drop the
  redundant final cast.
- `_from_speasy` has no sortedness check at all — unlike
  `data_provider.py`'s in-process post-process pipeline, which we today
  extended with `_is_time_sorted`/`_sort_variable_by_time` specifically to
  catch a time value returning to an earlier point mid-array (a merge-seam
  glitch). Reuse those two functions here rather than re-implement them.

FILLVAL replacement is **not** added to `reduce_result` generically — it's
Speasy/ISTP-specific and correctly stays inside the registered callable
(step 2), matching how the generic in-process `_get_data` post-process in
`data_provider.py` also doesn't know about FILLVAL today.

## Known risk, documented not solved here

`plugin_key_for()` groups by top-level Python package
(`callback.__module__.split(".")[0]`). Third-party plugins (`sciqlop_radio`,
`sciqlop_sismo`) each get their own worker naturally, since each is its own
installed package. A closure defined inside `SciQLop.plugins.speasy_provider`
keys as `"SciQLop"` — the same key any *other* bundled (not third-party)
bundled plugin's remote closure would get, so they'd share one worker
process. Not a correctness issue (each product still gets its own channel;
requests from different bundled plugins would simply queue within that one
shared worker's single-threaded loop), but a throughput consideration if a
second bundled plugin later adopts this pattern. Flagged for the
implementation plan to decide: accept the sharing, or give Speasy's
registration an explicit plugin_key override.

## Testing

- Unit: the remote-closure builder produces output matching
  `SpeasyPlugin.get_data()`'s in-process result for the same product/range
  (FILLVAL replaced, same values) — a real regression guard, since the two
  code paths must never drift apart.
- Unit: `reduction.py`'s epoch-conversion fix — same regression-test shape
  as today's speasy fix (redundant-copy guard, non-contiguous input,
  bit-identical-output check against the old formula).
- Unit: `reduction.py`'s new sortedness check — same mid-array-reversal
  case as today's `data_provider.py` test, reused (not re-authored) since
  the functions are shared.
- Integration: a real (not stand-in) remote-worker round trip fetching a
  small Speasy product end-to-end, verifying the graph receives correct,
  FILLVAL-clean, sorted, epoch-converted data.
- Startup: verify the Speasy worker is alive (`RemoteRegistry`'s worker
  entry populated, or `remote.worker_alive` tracing counter) shortly after
  app init, without requiring a plot to exist first.
