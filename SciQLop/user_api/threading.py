"""Unified thread-safety primitives for marshaling calls to the Qt main thread.

Lifecycle:
  1. Before KernelManager init: invoke_on_main_thread runs func directly
     (caller is assumed to be on the main thread during startup).
  2. After init_invoker(): delegates to jupyqt's cross-thread invoker.

All user_api and magic code should import from this module.
"""
import logging
from functools import wraps

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


def on_main_thread(func):
    """Decorator: marshal a call to the Qt main thread if not already there.

    No-op when called from the main thread or when no QApplication exists.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        from PySide6.QtCore import QThread, QCoreApplication
        app = QCoreApplication.instance()
        if app is None or QThread.currentThread() == app.thread():
            return func(*args, **kwargs)
        return invoke_on_main_thread(func, *args, **kwargs)
    return wrapper
