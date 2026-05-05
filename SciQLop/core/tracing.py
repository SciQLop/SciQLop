"""Forward-compatible facade over the SciQLopPlots runtime tracer.

Re-exports the upstream `SciQLopPlots.tracing` surface when available, and
otherwise provides no-op stand-ins with the same names so call sites do not
need to branch.

Adds two small things on top of the upstream API:

* `traced(...)` — strict superset of upstream `tracing.traced` that detects
  `async def` callables (opens the zone around the awaited body) and supports
  `capture=("arg", ...)` to record selected bound parameters as zone args.

* Auto thread naming — the first time a given thread emits a zone, counter or
  async event, we call `set_thread_name` with the Python thread name, falling
  back to the Qt thread's `objectName()` for foreign threads spawned outside
  Python. Without this, worker threads show up as `Thread <tid>` in Perfetto.

Open the resulting trace JSON in https://ui.perfetto.dev/
"""
from __future__ import annotations

import functools
import inspect
import threading
from typing import Any, Iterable, Optional


try:
    from SciQLopPlots import tracing as _t

    _enable = _t.enable
    _disable = _t.disable
    _flush = _t.flush
    _is_enabled = _t.is_enabled
    _set_thread_name = _t.set_thread_name
    _counter = _t.counter
    _async_begin = _t.async_begin
    _async_end = _t.async_end
    _Zone = _t.zone
    _Session = _t.session
    _UPSTREAM_AVAILABLE = True
except ImportError:
    _UPSTREAM_AVAILABLE = False

    def _enable(path: str) -> None:
        return None

    def _disable() -> None:
        return None

    def _flush() -> None:
        return None

    def _is_enabled() -> bool:
        return False

    def _set_thread_name(name: str) -> None:
        return None

    def _counter(name: str, value: float, cat: str = "") -> None:
        return None

    def _async_begin(name: str, cat: str = "") -> int:
        return 0

    def _async_end(handle: int) -> None:
        return None

    class _Zone:
        __slots__ = ("_args",)

        def __init__(self, name: str, cat: str = "", **args: Any) -> None:
            self._args = args

        def __enter__(self) -> "_Zone":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    class _Session:
        __slots__ = ("_path",)

        def __init__(self, path: str) -> None:
            self._path = path

        def __enter__(self) -> "_Session":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None


_THREAD_NAMED = threading.local()
_SYNTHETIC_LOCK = threading.Lock()
_SYNTHETIC_COUNTERS: dict = {}


def _alloc_synthetic_name(prefix: str) -> str:
    with _SYNTHETIC_LOCK:
        n = _SYNTHETIC_COUNTERS.get(prefix, 0) + 1
        _SYNTHETIC_COUNTERS[prefix] = n
    return f"{prefix}-{n}"


def _try_qt_thread_name() -> str:
    """Return QThread.currentThread().objectName() iff we can prove the
    QThread Qt sees actually corresponds to our worker (and not the main
    thread proxy that Qt returns for foreign threads when no QApplication
    is running).
    """
    try:
        from PySide6.QtCore import QCoreApplication, QThread
        app = QCoreApplication.instance()
        if app is None:
            return ""
        qt = QThread.currentThread()
        if qt is None or qt == app.thread():
            return ""
        return qt.objectName() or ""
    except Exception:
        return ""


def _resolve_thread_name(hint: str = "") -> str:
    t = threading.current_thread()
    name = getattr(t, "name", "") or ""
    if not name.startswith("Dummy-"):
        return name
    qt_name = _try_qt_thread_name()
    if qt_name:
        return qt_name
    if hint:
        prefix = hint.split(".", 1)[0] or "worker"
        return _alloc_synthetic_name(prefix)
    return f"worker-{t.ident}"


def _ensure_thread_named(hint: str = "") -> None:
    if getattr(_THREAD_NAMED, "done", False):
        return
    _THREAD_NAMED.done = True
    name = _resolve_thread_name(hint)
    if name:
        try:
            _set_thread_name(name)
        except Exception:
            pass


def enable(path: str) -> None:
    _enable(path)


def disable() -> None:
    _disable()


def flush() -> None:
    _flush()


def is_enabled() -> bool:
    return _is_enabled()


def set_thread_name(name: str) -> None:
    _THREAD_NAMED.done = True
    _set_thread_name(name)


def counter(name: str, value: float, cat: str = "") -> None:
    _ensure_thread_named(hint=name)
    _counter(name, value, cat)


def async_begin(name: str, cat: str = "") -> int:
    _ensure_thread_named(hint=name)
    return _async_begin(name, cat)


def async_end(handle: int) -> None:
    _async_end(handle)


class zone:
    """Context manager for a synchronous zone, with auto thread naming."""

    __slots__ = ("_inner", "_name")

    def __init__(self, name: str, cat: str = "", **args: Any) -> None:
        self._inner = _Zone(name, cat, **args)
        self._name = name

    def __enter__(self) -> "zone":
        _ensure_thread_named(hint=self._name)
        self._inner.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return self._inner.__exit__(exc_type, exc, tb)


class session:
    """Enable tracing for the duration of a `with` block."""

    __slots__ = ("_inner",)

    def __init__(self, path: str) -> None:
        self._inner = _Session(path)

    def __enter__(self) -> "session":
        self._inner.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return self._inner.__exit__(exc_type, exc, tb)


def _bound_args_subset(sig: inspect.Signature, capture: Iterable[str],
                       args: tuple, kwargs: dict) -> dict:
    try:
        bound = sig.bind_partial(*args, **kwargs)
    except TypeError:
        return {}
    out = {}
    for name in capture:
        if name in bound.arguments:
            out[name] = bound.arguments[name]
    return out


def traced(name: Optional[str] = None, cat: str = "",
           capture: Iterable[str] = ()):
    """Decorator that wraps a call in a synchronous zone.

    Strict superset of `SciQLopPlots.tracing.traced`:
      * works on `async def` functions (zone spans the awaited body),
      * `capture=("start", "stop")` records those bound parameters as zone args.
    """
    capture = tuple(capture)

    def decorator(fn):
        zname = name or fn.__qualname__
        sig = inspect.signature(fn) if capture else None

        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args, **kwargs):
                zargs = _bound_args_subset(sig, capture, args, kwargs) if sig else {}
                with zone(zname, cat, **zargs):
                    return await fn(*args, **kwargs)

            return async_wrapper

        @functools.wraps(fn)
        def sync_wrapper(*args, **kwargs):
            zargs = _bound_args_subset(sig, capture, args, kwargs) if sig else {}
            with zone(zname, cat, **zargs):
                return fn(*args, **kwargs)

        return sync_wrapper

    return decorator


__all__ = [
    "enable", "disable", "flush", "is_enabled", "set_thread_name",
    "counter", "async_begin", "async_end",
    "zone", "session", "traced",
]
