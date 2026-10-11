"""A welcome-page fetch that finishes after the page closed stays quiet.

At shutdown with --webengine, the fetch threads emitted their result on the
deleted backend: "RuntimeError: Signal source has been deleted", twice.
"""
from .fixtures import *  # noqa: F401,F403 — qapp/main_window fixtures
import threading
import urllib.request

import shiboken6


def test_a_fetch_finishing_after_the_backend_is_deleted_raises_nothing(main_window, monkeypatch):
    from SciQLop.components.welcome.backend import WelcomeBackend
    release, errors, done = threading.Event(), [], threading.Event()

    def slow_urlopen(*args, **kwargs):
        release.wait(5)
        raise OSError("offline")

    def record(args):
        errors.append(args.exc_value)

    monkeypatch.setattr(urllib.request, "urlopen", slow_urlopen)
    monkeypatch.setattr(threading, "excepthook", record)
    original_thread = threading.Thread

    def tracked_thread(*args, target=None, **kwargs):
        def run():
            try:
                target()
            finally:
                done.set()
        return original_thread(*args, target=run, **kwargs)

    monkeypatch.setattr(threading, "Thread", tracked_thread)

    backend = WelcomeBackend()
    backend.fetch_featured_packages()
    shiboken6.delete(backend)
    release.set()
    assert done.wait(5)
    assert errors == []
