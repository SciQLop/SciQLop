"""Unified thread-safety primitives for marshaling calls to the Qt main thread.

Lifecycle:
  1. Before KernelManager init: invoke_on_main_thread runs func directly
     (caller is assumed to be on the main thread during startup).
  2. After init_invoker(): delegates to jupyqt's cross-thread invoker.

All user_api and magic code should import from this module.

Two primitives sit on top of the invoker: `@on_main_thread` for functions we own,
and `MainThreadProxy` for live QObjects handed to kernel-thread code. Both are
no-ops before `init_invoker()`, when the only caller is the main thread anyway.

When you need the real QObject behind a proxy (for example to pass it to a Qt
helper the proxy cannot handle), use `unwrap(obj)`. Most user-facing helpers are
already `@on_main_thread`, so you rarely need this.
"""
import logging
from functools import wraps

__all__ = [
    "init_invoker",
    "invoke_on_main_thread",
    "on_main_thread",
    "MainThreadProxy",
    "unwrap",
    "unwrap_all",
    "main_thread_safe",
]

_log = logging.getLogger(__name__)

_invoker = None


def init_invoker(invoker):
    """Called once by KernelManager to provide the jupyqt invoker."""
    global _invoker
    _invoker = invoker


def invoke_on_main_thread(func, *args, **kwargs):
    """Run func on the Qt main thread, blocking until done.

    Before init_invoker(): runs func directly (startup phase, already on main thread).
    After init_invoker(): delegates to jupyqt's cross-thread invoker.
    """
    if _invoker is None:
        return func(*args, **kwargs)
    return _invoker(func, *args, **kwargs)


def _on_main_thread() -> bool:
    from PySide6.QtCore import QThread, QCoreApplication
    app = QCoreApplication.instance()
    return app is None or QThread.currentThread() == app.thread()


class MainThreadProxy:
    """Wraps a QObject so every attribute access and call runs on the GUI thread.

    Cells run on the jupyqt kernel thread — agent tools and notebook code alike —
    so a direct Qt call from there is undefined behaviour and routinely aborts the
    process (`qFatal` inside `QQuickWidget::createFramebufferObject`). Handing out
    a proxy instead keeps such code alive at the cost of a blocking round-trip.

    Unlike jupyqt's `QtProxy` this also wraps QObjects returned *inside* a list,
    tuple, set or dict — `app.topLevelWidgets()[0]` is the usual way a raw widget
    escapes — and leaves signals alone so they stay connectable.

    Only attribute access is marshaled: dunder protocols (`len()`, `obj[i]`, `with`)
    reach the target directly and are not thread-safe.

    The wrapped QObject is intentionally not exposed as a public attribute.
    User code that needs the raw object can use `unwrap()`; normal attribute
    access to the raw target is blocked to prevent accidental cross-thread Qt
    calls.
    """

    __slots__ = ("_target", "__dict__", "__weakref__")

    def __init__(self, target):
        object.__setattr__(self, "_target", target)

    def __getattribute__(self, name):
        if name == "_target":
            raise AttributeError(
                "MainThreadProxy._target is private; use "
                "SciQLop.user_api.threading.unwrap() if you need the raw QObject."
            )
        return object.__getattribute__(self, name)

    def __dir__(self):
        names = list(object.__getattribute__(self, "__dict__").keys())
        names.extend(
            s for s in object.__getattribute__(self, "__class__").__slots__
            if s != "_target"
        )
        return sorted(set(names))

    def __getattr__(self, name):
        target = object.__getattribute__(self, "_target")
        attr = invoke_on_main_thread(getattr, target, name)

        from PySide6.QtCore import SignalInstance
        if isinstance(attr, SignalInstance):
            return attr  # Qt marshals queued connections itself
        if callable(attr):
            def caller(*args, **kwargs):
                return _wrap_for_main_thread(
                    invoke_on_main_thread(attr, *unwrap_all(args), **unwrap_all(kwargs))
                )
            return caller
        return _wrap_for_main_thread(attr)

    def __setattr__(self, name, value):
        target = object.__getattribute__(self, "_target")
        invoke_on_main_thread(setattr, target, name, unwrap(value))

    def __repr__(self):
        target = object.__getattribute__(self, "_target")
        return f"MainThreadProxy({invoke_on_main_thread(repr, target)})"


def _wrap_for_main_thread(value):
    """Proxy a QObject, recursing into the containers Qt commonly returns."""
    from PySide6.QtCore import QObject
    if isinstance(value, QObject):
        return MainThreadProxy(value)
    if isinstance(value, (list, tuple, set)):
        return type(value)(_wrap_for_main_thread(v) for v in value)
    if isinstance(value, dict):
        return {k: _wrap_for_main_thread(v) for k, v in value.items()}
    return value


def unwrap(obj):
    """Return the object a MainThreadProxy stands for; any other object as is."""
    if isinstance(obj, MainThreadProxy):
        return object.__getattribute__(obj, "_target")
    return obj


def unwrap_all(values):
    """Unwrap proxies in an args tuple or kwargs dict before crossing into Qt."""
    if isinstance(values, dict):
        return {k: unwrap(v) for k, v in values.items()}
    return tuple(unwrap(v) for v in values)


def main_thread_safe(obj):
    """Return `obj` on the GUI thread, a MainThreadProxy of it anywhere else."""
    return obj if _on_main_thread() else MainThreadProxy(obj)


def on_main_thread(func):
    """Decorator: marshal a call to the Qt main thread if not already there.

    No-op when called from the main thread or when no QApplication exists.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        if _on_main_thread():
            return func(*args, **kwargs)
        return invoke_on_main_thread(func, *args, **kwargs)
    return wrapper
