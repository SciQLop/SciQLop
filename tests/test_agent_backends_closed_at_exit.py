"""Closing SciQLop stops every agent backend: an agent process must not outlive the application."""
import asyncio
from types import SimpleNamespace

import pytest

from SciQLop.components.agents import chat_dock

from .fixtures import *  # noqa: F401,F403
from .test_agent_chat_dock_wiring import _FAKE, dock  # noqa: F401 — fixture
from .test_agent_dock_follows_contributions import closed  # noqa: F401 — fixture


def _window_with(agent_dock):
    window = SimpleNamespace(close=lambda: None)
    if agent_dock is not None:
        setattr(window, chat_dock._DOCK_ATTR, agent_dock)
    return window


@pytest.fixture(autouse=True)
def _no_plugin_is_closed(monkeypatch):
    """_async_close closes the loaded plugins too: those belong to the session's main window."""
    import SciQLop.components.plugins as plugins
    monkeypatch.setattr(plugins, "loaded_plugins", SimpleNamespace())


def test_closing_the_window_closes_the_backend_of_every_session(closed, dock, qtbot):
    from SciQLop.core.ui.mainwindow import SciQLopMainWindow
    backend = dock._sessions[_FAKE].backend

    closing = asyncio.ensure_future(SciQLopMainWindow._async_close(_window_with(dock)))
    qtbot.waitUntil(closing.done, timeout=2000)

    assert closed == [backend]


def test_a_window_without_agent_dock_closes(qapp):
    from SciQLop.core.ui.mainwindow import SciQLopMainWindow
    done = []
    window = _window_with(None)
    window.close = lambda: done.append(True)

    asyncio.new_event_loop().run_until_complete(SciQLopMainWindow._async_close(window))

    assert done == [True]
