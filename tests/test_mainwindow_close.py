"""closeEvent must not assume a usable asyncio loop (2026-06-09 review).

At pytest session teardown the current loop is absent or never ran;
`asyncio.ensure_future` then raised out of closeEvent, leaving the window
half-closed and erroring the last test's teardown.
"""
import asyncio
from unittest.mock import MagicMock

from .fixtures import *


def _restore_loop():
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        return None


def test_usable_event_loop_guards(qapp):
    from SciQLop.core.ui.mainwindow import SciQLopMainWindow
    prev = _restore_loop()
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        assert SciQLopMainWindow._usable_event_loop() is None, \
            "a loop that is not running cannot execute _async_close"
        loop.close()
        assert SciQLopMainWindow._usable_event_loop() is None
        asyncio.set_event_loop(None)
        assert SciQLopMainWindow._usable_event_loop() is None
    finally:
        asyncio.set_event_loop(prev)


def test_usable_event_loop_detects_running_loop(qapp):
    from SciQLop.core.ui.mainwindow import SciQLopMainWindow
    prev = _restore_loop()

    async def probe():
        return SciQLopMainWindow._usable_event_loop()

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        assert loop.run_until_complete(probe()) is loop
        loop.close()
    finally:
        asyncio.set_event_loop(prev)


def test_confirm_close_no_running_jobs_proceeds(qapp):
    from SciQLop.core.ui.mainwindow import _confirm_close_with_running_jobs
    event = MagicMock()
    cancelled = _confirm_close_with_running_jobs(None, event, [{"name": "x", "status": "done"}])
    assert cancelled is False
    event.ignore.assert_not_called()


def test_confirm_close_running_job_user_says_no_cancels(qapp, monkeypatch):
    from SciQLop.core.ui.mainwindow import _confirm_close_with_running_jobs
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.No)
    event = MagicMock()
    cancelled = _confirm_close_with_running_jobs(
        None, event, [{"name": "11-year build", "status": "running"}])
    assert cancelled is True
    event.ignore.assert_called_once()


def test_confirm_close_running_job_user_says_yes_proceeds(qapp, monkeypatch):
    from SciQLop.core.ui.mainwindow import _confirm_close_with_running_jobs
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    event = MagicMock()
    cancelled = _confirm_close_with_running_jobs(
        None, event, [{"name": "11-year build", "status": "running"}])
    assert cancelled is False
    event.ignore.assert_not_called()


def test_warn_if_jobs_running_fails_open_on_backend_error(qapp, monkeypatch):
    from SciQLop.core.ui.mainwindow import SciQLopMainWindow

    def _raise():
        raise RuntimeError("backend unavailable")

    monkeypatch.setattr(
        "SciQLop.components.jobs.backend.jobs_backend.jobs_backend_instance", _raise)

    win = SciQLopMainWindow.__new__(SciQLopMainWindow)  # bypass __init__, we only need the method
    event = MagicMock()
    cancelled = SciQLopMainWindow._warn_if_jobs_running(win, event)
    assert cancelled is False
    event.ignore.assert_not_called()


def test_confirm_close_no_dirty_catalogs_proceeds(qapp):
    from SciQLop.core.ui.mainwindow import _confirm_close_with_dirty_catalogs
    event = MagicMock()
    cancelled = _confirm_close_with_dirty_catalogs(None, event, [])
    assert cancelled is False
    event.ignore.assert_not_called()


def test_confirm_close_dirty_catalogs_user_says_no_cancels(qapp, monkeypatch):
    from SciQLop.core.ui.mainwindow import _confirm_close_with_dirty_catalogs
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.No)
    event = MagicMock()
    cancelled = _confirm_close_with_dirty_catalogs(None, event, ["DummyProvider"])
    assert cancelled is True
    event.ignore.assert_called_once()


def test_confirm_close_dirty_catalogs_user_says_yes_proceeds(qapp, monkeypatch):
    from SciQLop.core.ui.mainwindow import _confirm_close_with_dirty_catalogs
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    event = MagicMock()
    cancelled = _confirm_close_with_dirty_catalogs(None, event, ["DummyProvider"])
    assert cancelled is False
    event.ignore.assert_not_called()


def test_warn_if_catalogs_dirty_fails_open_on_backend_error(qapp, monkeypatch):
    from SciQLop.core.ui.mainwindow import SciQLopMainWindow

    def _raise(*a, **k):
        raise RuntimeError("registry unavailable")

    monkeypatch.setattr(
        "SciQLop.components.catalogs.backend.registry.CatalogRegistry.instance", _raise)

    win = SciQLopMainWindow.__new__(SciQLopMainWindow)  # bypass __init__, we only need the method
    event = MagicMock()
    cancelled = SciQLopMainWindow._warn_if_catalogs_dirty(win, event)
    assert cancelled is False
    event.ignore.assert_not_called()


def test_warn_if_catalogs_dirty_detects_dirty_provider(qapp, monkeypatch):
    from SciQLop.core.ui.mainwindow import SciQLopMainWindow
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from PySide6.QtWidgets import QMessageBox

    provider = DummyProvider(num_catalogs=1, events_per_catalog=1)
    cat = provider.catalogs()[0]
    provider.mark_dirty(cat)

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.No)
    win = SciQLopMainWindow.__new__(SciQLopMainWindow)
    event = MagicMock()
    cancelled = SciQLopMainWindow._warn_if_catalogs_dirty(win, event)
    assert cancelled is True
    event.ignore.assert_called_once()


def test_warn_if_catalogs_dirty_ignores_clean_provider(qapp):
    from SciQLop.core.ui.mainwindow import SciQLopMainWindow
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    DummyProvider(num_catalogs=1, events_per_catalog=1)

    win = SciQLopMainWindow.__new__(SciQLopMainWindow)
    event = MagicMock()
    cancelled = SciQLopMainWindow._warn_if_catalogs_dirty(win, event)
    assert cancelled is False
    event.ignore.assert_not_called()
