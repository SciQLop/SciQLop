# Speasy out-of-process fetch — design

**Date:** 2026-09-10
**Status:** BLOCKED — independent review (below) found the registration
mechanism and the "no behavior change" claim both don't hold; needs a real
redesign of §"Registering a product as remote" and a plan for the
`_post_plot` gap before an implementation plan can be written from this.
Paused here at the user's request (2026-09-10); not resumed yet.

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

## Independent review (2026-09-10, Fable, high effort)

Dispatched a fresh review agent against this spec and the real source (not
this document alone). Two of its findings were independently re-verified by
reading the cited code directly, both confirmed real:

- **Registration mechanism doesn't fit Speasy's catalog.**
  `remote_registry().is_remote(product)` (`time_sync_panel.py:733`) just
  checks dict membership — a product must already be registered *before*
  `plot_product` runs. `EasyProvider` satisfies this by registering its
  whole (small, curated) set of virtual products once at plugin-load time.
  Speasy's catalog is ~100k products; pre-registering all of them the same
  way isn't viable, and "register at graph-creation time" (as written in
  §2 above) is too late — `is_remote()` is checked before any
  graph-creation-time hook would run. Needs a different mechanism, e.g. a
  provider-side `remote_spec(node)` protocol checked lazily, not a
  pre-populated path registry.
- **"No behavior change" is false.** `plot_product` branches into
  `plot_remote(...)` and returns directly for a remote product
  (`time_sync_panel.py:733-745`) — it never reaches `_post_plot`
  (`time_sync_panel.py:609-631`), which wires up `plot_hints`/
  `plot_hints_from_variable` (units, labels, log-scale defaults),
  `data_meta_from_variable`, `_attach_graph_context` (snippets, inspector
  Graph section), `_set_product_path`, and the shiboken keepalive pins.
  All of that is silently lost for every Speasy plot as designed. Needs
  either a protocol change (worker returns hint metadata alongside the
  array layout) or an explicit decision to accept the loss for v1.

Remaining findings (not independently re-verified line-by-line, but the
review cited specific file:line evidence for each — worth checking before
resuming):

1. The closure sketch in §2 skips `speasy_kwargs()` — AMDA template params
   and SSC/3DView frame knobs would silently fail as written.
2. `get_data` can't be relocated, only duplicated — `Depends()` resolution
   (`dependencies.py:97`) still needs the in-process path.
3. Remote errors/speasy warnings surface via stdlib `logging`
   (`channel.py:33,88`), not SciQLop's Qt-signal-based `sciqlop_logging` —
   likely invisible in a GUI/AppImage launch.
4. Worker crash (`_on_worker_died`, `worker_handle.py:220-226`) permanently
   silences every open Speasy graph — no re-INSTALL of channels on
   respawn, only on the *next new* graph's `worker_for()` call.
5. The worker's `serve()` loop (`worker.py:117-129`) handles one channel at
   a time — multiple simultaneously-panning Speasy graphs, which overlap
   their network I/O today, would serialize behind one worker. Could make
   heavy multi-graph panning worse, not better.
6. The measured 1.85s/32s cold-start numbers likely reflect `import
   speasy`'s own inventory-init cost (triggered lazily inside
   `reduce_result`'s `_is_speasy_variable` check on the *first reply*, not
   at worker spawn) rather than "worker spawn + connect" as attributed in
   §"What already exists". Changes what an eager warm-up actually needs to
   force (a real `import speasy` in the worker, not just a spawned
   process).
7. The worker never receives `SpeasyPlugin.__init__`'s three startup
   patches (inventory-recursion SIGSEGV workaround, User-Agent, cache
   `ThreadStorage` fix) — needs its own bootstrap hook.
8. No zero-width-component guard in `reduction.py`, unlike
   `data_provider.py:25-33,173-176` — SciQLopPlots aborts the process on
   that shape (`Q_ASSERT(stride > 0)`).
9. No remote graph factory exists for `PlotType.Projections`
   (`add_remote_line_graph` is declared only on `SciQLopPlot`, not
   `SciQLopNDProjectionPlot`) — "always remote" needs a gate for this case.
10. No shared-memory budget considered — fine on this machine, not
    necessarily under Flatpak/AppImage's smaller `/dev/shm` defaults.
11. Reusing `_is_time_sorted`/`_sort_variable_by_time` as proposed imports
    `data_provider.py` (Qt signals, tracing) into the numpy-only worker —
    move the two helpers to a shared Qt-free module instead.
12. `reduction.py`'s `/1e9` and speasy's fixed `*1e-9` differ by 1 ULP on
    ~43% of sampled values — "bit-identical" in the Testing section should
    be scoped to reduction's own old formula, or the two should be unified
    to the same formula.

**Not resumed.** Next session: start from the two confirmed findings above
(registration mechanism, `_post_plot` gap) — they're load-bearing enough
that the design likely needs a real rethink of how a product becomes
"remote" at all, not a patch to §2.
