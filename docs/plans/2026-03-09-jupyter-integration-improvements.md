# Jupyter Integration Improvements

**Date**: 2026-03-09
**Status**: Approved

## Problem

The Jupyter/IPython kernel integration has several pain points:

1. **GUI responsiveness**: The kernel poller fires every 10ms regardless of load, wasting CPU when idle and not adapting to busy periods
2. **Fragile shutdown**: `run_cell("quit()")` blocks if kernel is stuck; subprocess cleanup has no timeout
3. **Tangled responsibilities**: `WorkspaceManager` directly manages kernel lifecycle, mixing workspace and kernel concerns
4. **Redundant guard**: `_is_iterating` flag in poller is dead logic since `@asyncSlot` already serializes

## Design

### 1. Adaptive Kernel Poller

Replace fixed 10ms `QTimer` interval with adaptive polling:
- **Fast** (5ms) after `do_one_iteration()` processed messages
- **Slow** (50-100ms) after idle iterations (no messages processed)
- Remove `_is_iterating` boolean guard — `@asyncSlot` serialization makes it redundant
- Keep `do_one_iteration()` as the polling mechanism (ipykernel's expected API)

### 2. Shutdown Hardening

**Subprocess cleanup** (in `ClientsManager.cleanup()`):
- `terminate()` first (SIGTERM)
- `waitForFinished(3000)` with 3s timeout
- `kill()` (SIGKILL) if still alive after timeout

**Kernel shutdown** (replace `run_cell("quit()")`):
- Stop the kernel poller
- Call `kernel.do_shutdown()` (ipykernel's proper shutdown API)
- Close ZMQ sockets cleanly

**Order**: kill clients first (they depend on the kernel), then shut down the kernel.

### 3. Extract KernelManager

New class in `components/jupyter/kernel/` that owns the full kernel lifecycle:
- `init()` — create `SciQLopKernelApp`, initialize
- `start()` — start kernel + poller
- `push_variables()` — with deferred variable support
- `shutdown()` — stop poller, shutdown kernel
- `connection_file` property

`WorkspaceManager` delegates to `KernelManager` instead of directly managing `InternalIPKernel` + `ClientsManager`.

### 4. File Organization

Keep `SciQLop/Jupyter/` at top level (provisioner runs in JupyterLab's subprocess, separate namespace makes sense, avoids entry point changes).

Rename `components/jupyter/IPythonKernel/` to `components/jupyter/kernel/` for clarity.

### Not In Scope

- JupyterLab startup error handling / process crash detection
- QSocketNotifier-based ZMQ integration (fights ipykernel internals)
- Moving kernel to a QThread or separate process
- Out-of-process kernel prototype (future work, separate effort)
