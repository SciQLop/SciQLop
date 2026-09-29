"""In-process, privilege-free all-threads stack dump.

`py-spy`/`perf` need CAP_SYS_PTRACE/CAP_PERFMON, unavailable in sandboxed dev
environments and to normal end users. This gives an equivalent capability
from inside the process itself, two ways:

- `install_signal_dump()` arms SIGUSR1 via `faulthandler.register()` --
  deliberately not a plain `signal.signal()` handler: `faulthandler`'s C-level
  handler reads already-tracked per-thread frame pointers directly, so it
  keeps working even if some thread is stuck in a tight C loop holding the
  GIL, where a plain Python signal callback might never get scheduled.
  `kill -USR1 <pid>` needs no special capability, unlike ptrace-based tools.
- `dump_now(reason)` is a plain function for use from *live* code (a menu
  action, a watchdog's checker thread) -- it doesn't depend on signal
  delivery, so it can run from a thread that's still healthy even while some
  other thread in the process is the one that's stuck.
"""
from __future__ import annotations

import datetime
import faulthandler
import signal
import threading
from pathlib import Path
from typing import Optional

from SciQLop.components.storage import user_data_dir

_signal_log_file: Optional[object] = None


def default_directory() -> Path:
    return user_data_dir("diagnostics")


def _thread_name_header() -> str:
    """`faulthandler` labels each stack by native thread ident only (e.g.
    `Thread 0x00007f2e...`), not by `threading.Thread.name` -- next to
    useless on its own. Prepend an ident->name lookup for every thread
    Python knows about, using the same zero-padded hex faulthandler uses."""
    lines = ["# thread names (native ident -> Python name):"]
    for t in threading.enumerate():
        if t.ident is not None:
            lines.append(f"#   0x{t.ident:016x} -> {t.name}")
    return "\n".join(lines) + "\n\n"


def dump_now(reason: str, directory: Optional[Path] = None) -> Path:
    """Write a fresh, timestamped all-threads traceback dump and return its
    path. Safe to call from any live thread, including while some OTHER
    thread in the process is stuck."""
    directory = directory or default_directory()
    directory.mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now()
    stamp = now.strftime("%Y%m%d-%H%M%S-%f")
    path = directory / f"dump-{stamp}-{reason}.txt"
    with open(path, "w") as f:
        f.write(f"# SciQLop diagnostic dump\n# reason: {reason}\n"
                f"# time: {now.isoformat()}\n\n")
        f.write(_thread_name_header())
        faulthandler.dump_traceback(file=f, all_threads=True)
    return path


def install_signal_dump(directory: Optional[Path] = None) -> Optional[Path]:
    """Arm SIGUSR1 to append an all-threads traceback dump to a log file
    under `directory` for the rest of the process lifetime. Idempotent.
    Returns the log path, or None where SIGUSR1 does not exist (Windows).

    Unlike `dump_now`, entries here are bare `faulthandler` output -- ident
    only, no thread-name header -- because the whole point of using
    `faulthandler.register()` is that its C-level handler can fire even when
    no Python code (ours included) can safely run on the stuck thread; it
    can't be made to run our name-lookup logic at trigger time. Cross-
    reference idents against a `dump_now()` taken around the same time (or
    `thread_cpu_top`) to attach names."""
    global _signal_log_file
    if not hasattr(signal, "SIGUSR1"):
        return None
    directory = directory or default_directory()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "signal_dumps.log"
    if _signal_log_file is not None:
        faulthandler.unregister(signal.SIGUSR1)
        _signal_log_file.close()
    _signal_log_file = open(path, "a")
    faulthandler.register(signal.SIGUSR1, file=_signal_log_file,
                          all_threads=True, chain=False)
    return path


def uninstall_signal_dump() -> None:
    """Undo `install_signal_dump()`. Mainly for tests."""
    global _signal_log_file
    if hasattr(signal, "SIGUSR1"):
        faulthandler.unregister(signal.SIGUSR1)
    if _signal_log_file is not None:
        _signal_log_file.close()
        _signal_log_file = None
