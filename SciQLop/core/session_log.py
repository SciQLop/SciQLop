"""What the last session left behind: its dated log, and a marker if it crashed.

Shared by the launchers (which own the log and see how the GUI process ended)
and the GUI (which dumps its stacks into the log and offers a crash report on
the next start). Stdlib + platformdirs only: the thin launcher imports it.

Design: docs/superpowers/specs/2026-09-29-crash-report-agent-design.md
"""
from __future__ import annotations

import faulthandler
import functools
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

SESSION_LOG_ENV = "SCIQLOP_SESSION_LOG"
KEPT_LOGS = 10
CRASH_MARKER_NAME = "crash-pending.json"
_LOG_GLOB = "sciqlop-*.log"
_NTSTATUS_ERROR = 0xC0000000

_trace_file = None


def launcher_data_dir() -> Path:
    """Same root as the C++ launcher's paths::user_data_dir() — not
    SciQLop.components.storage.user_data_dir(), which adds a data/ level."""
    from platformdirs import user_data_dir
    return Path(user_data_dir(appname="sciqlop", appauthor="LPP", ensure_exists=True))


def session_log_name(now: datetime, pid: int) -> str:
    return f"sciqlop-{now:%Y%m%d-%H%M%S}-{pid}.log"


def prune_logs(directory: Path, keep: int = KEPT_LOGS) -> None:
    """Names sort chronologically, so the oldest are simply the first ones."""
    for old in sorted(directory.glob(_LOG_GLOB))[:-keep]:
        old.unlink(missing_ok=True)


def new_session_log(directory: Path, now: Optional[datetime] = None,
                    pid: Optional[int] = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / session_log_name(now or datetime.now(), pid or os.getpid())
    path.touch()
    prune_logs(directory)
    return path


@functools.cache
def session_log() -> Path:
    """This launcher process's log: the one the native launcher created (and
    advertised in SESSION_LOG_ENV), else a new one. Restart and workspace-switch
    rounds of the same process keep appending to it."""
    chosen = os.environ.get(SESSION_LOG_ENV)
    if chosen:
        return Path(chosen)
    return new_session_log(launcher_data_dir() / "logs")


def is_crash(returncode: int) -> bool:
    """Killed by a signal (POSIX: negative) or by an NTSTATUS exception
    (Windows) — not a handled exit such as the app's own exit(1)."""
    return returncode < 0 or returncode >= _NTSTATUS_ERROR


def describe_exit(returncode: int) -> str:
    """One wording for every place that reports how SciQLop ended."""
    import signal
    if returncode == 0:
        return "exited normally"
    if returncode < 0:
        try:
            name = signal.Signals(-returncode).name
        except ValueError:
            name = "unknown signal"
        return f"crashed ({name}, signal {-returncode})"
    if returncode >= _NTSTATUS_ERROR:
        return f"crashed (Windows exception 0x{returncode:08X})"
    return f"exited with code {returncode}"


def crash_marker(returncode: int, pid: int, log: Path,
                 now: Optional[datetime] = None) -> dict:
    return {
        "time": (now or datetime.now()).astimezone().isoformat(timespec="seconds"),
        "pid": pid,
        "platform": sys.platform,
        "signal": -returncode if returncode < 0 else None,
        "ntstatus": f"0x{returncode:08X}" if returncode >= _NTSTATUS_ERROR else None,
        "log": str(log),
    }


def write_crash_marker(marker: dict, directory: Optional[Path] = None) -> None:
    path = (directory or launcher_data_dir()) / CRASH_MARKER_NAME
    path.write_text(json.dumps(marker, indent=1), encoding="utf-8")


def record_if_crashed(proc, log: Optional[Path], directory: Optional[Path] = None) -> None:
    if log is None or proc.returncode is None or not is_crash(proc.returncode):
        return
    try:
        write_crash_marker(crash_marker(proc.returncode, proc.pid, log), directory)
    except OSError:
        pass


def take_crash_marker(directory: Optional[Path] = None) -> Optional[dict]:
    """Read and delete the marker, so a crash is offered for reporting once.
    A marker whose log was rotated away is dropped: nothing left to report."""
    path = (directory or launcher_data_dir()) / CRASH_MARKER_NAME
    try:
        marker = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        marker = None
    path.unlink(missing_ok=True)
    if not isinstance(marker, dict) or not Path(marker.get("log", "")).is_file():
        return None
    return marker


def enable_crash_traces() -> None:
    """Dump every thread's Python stack on a fatal signal.

    Writes straight into the session log rather than stderr, so the dump
    does not depend on the two relay processes (Python launcher drain thread,
    C++ tee) still draining when the GUI dies."""
    global _trace_file
    chosen = os.environ.get(SESSION_LOG_ENV)
    if chosen:
        _trace_file = open(chosen, "a", encoding="utf-8")
        faulthandler.enable(file=_trace_file, all_threads=True)
    elif sys.stderr is not None:
        faulthandler.enable(all_threads=True)
