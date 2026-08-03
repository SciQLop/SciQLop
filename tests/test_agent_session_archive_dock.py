"""The dock hands claimed sessions to an archiving backend and deletes on request."""
import pytest

from .fixtures import qapp_cls, sciqlop_resources  # noqa: F401 — fixtures
from .test_agent_chat_dock_wiring import _FakeBackend, _settle  # noqa: F401

_ARCHIVING = "ArchivingAgent"


class _Entry:
    def __init__(self, sid, label, mtime):
        self.id, self.label, self.mtime = sid, label, mtime


class _ArchivingBackend(_FakeBackend):
    display_name = _ARCHIVING
    supports_sessions = True

    def __init__(self, ctx=None):
        super().__init__(ctx)
        self.entries = [_Entry("kept", "Auto kept", 2.0), _Entry("loose", "Auto loose", 1.0)]
        self.archived = None
        self.deleted = []

    def list_sessions(self):
        return list(self.entries)

    def archive_sessions(self, session_ids):
        self.archived = list(session_ids)

    def delete_session(self, session_id):
        self.deleted.append(session_id)
        self.entries = [e for e in self.entries if e.id != session_id]


@pytest.fixture
def loop():
    """A current event loop for the dock's `_spawn`.

    Any earlier test using `asyncio.run` leaves the current loop unset, and the
    dock spawns tasks while binding its first backend.
    """
    import asyncio

    made = asyncio.new_event_loop()
    asyncio.set_event_loop(made)
    yield made
    asyncio.set_event_loop(None)
    made.close()


@pytest.fixture
def dock(qtbot, sciqlop_resources, monkeypatch, loop):
    from SciQLop.components.agents import model_capabilities
    from SciQLop.components.agents.chat_dock import AgentChatDock
    from SciQLop.components.agents.registry import (
        register_agent_backend, unregister_agent_backend)
    from SciQLop.components.agents.settings import AgentChatSettings, AgentSessionMeta

    async def _no_network():
        return None

    monkeypatch.setattr(model_capabilities, "ensure_registry_fresh", _no_network)
    saved = AgentChatSettings()
    restore = (dict(saved.effort), saved.tool_verbosity, saved.last_backend)
    register_agent_backend(_ArchivingBackend)
    try:
        widget = AgentChatDock(main_window=None)
        qtbot.addWidget(widget)
        widget._backend_combo.setCurrentText(_ARCHIVING)
        _settle(qtbot)
        yield widget
    finally:
        unregister_agent_backend(_ARCHIVING)
        meta = AgentSessionMeta()
        for sid in ("kept", "loose"):
            meta.forget(_ARCHIVING, sid)
        with AgentChatSettings() as cfg:
            cfg.effort, cfg.tool_verbosity, cfg.last_backend = restore


def _backend(dock):
    return dock._sessions[dock._current].backend


def test_claimed_sessions_are_handed_to_the_backend_on_refresh(dock):
    from SciQLop.components.agents.settings import AgentSessionMeta

    AgentSessionMeta().set_name(_ARCHIVING, "kept", "Magnetopause")
    dock._populate_session_list(_backend(dock))
    assert _backend(dock).archived == ["kept"]


def test_nothing_claimed_asks_for_nothing(dock):
    dock._populate_session_list(_backend(dock))
    assert _backend(dock).archived == []


def test_delete_erases_the_session_and_its_overlay(dock, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from SciQLop.components.agents.settings import AgentSessionMeta

    AgentSessionMeta().set_name(_ARCHIVING, "kept", "Magnetopause")
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    dock._on_session_delete("kept")

    assert _backend(dock).deleted == ["kept"]
    assert AgentSessionMeta().get(_ARCHIVING, "kept").name == ""


def test_declining_the_confirmation_deletes_nothing(dock, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from SciQLop.components.agents.settings import AgentSessionMeta

    AgentSessionMeta().set_name(_ARCHIVING, "kept", "Magnetopause")
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    dock._on_session_delete("kept")

    assert _backend(dock).deleted == []
    assert AgentSessionMeta().get(_ARCHIVING, "kept").name == "Magnetopause"


def test_the_open_session_is_never_deleted_under_the_user(dock, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    dock._sessions[dock._current].resume_id = "kept"
    dock._on_session_delete("kept")

    assert _backend(dock).deleted == []


def test_a_finished_turn_refreshes_the_archive(dock, loop):
    from SciQLop.components.agents.chat import TextBlock
    from SciQLop.components.agents.settings import AgentSessionMeta

    AgentSessionMeta().set_name(_ARCHIVING, "kept", "Magnetopause")
    backend = _backend(dock)
    backend.archived = None

    async def _one_block(prompt, image_paths=None):
        yield TextBlock(text="done")

    backend.ask = _one_block
    session = dock._sessions[dock._current]
    loop.run_until_complete(dock._run_turn(session, "hi", []))

    assert backend.archived == ["kept"]


def test_a_backend_without_archiving_is_left_alone(qtbot, sciqlop_resources, monkeypatch, loop):
    from SciQLop.components.agents import model_capabilities
    from SciQLop.components.agents.chat_dock import AgentChatDock
    from SciQLop.components.agents.registry import (
        register_agent_backend, unregister_agent_backend)

    async def _no_network():
        return None

    monkeypatch.setattr(model_capabilities, "ensure_registry_fresh", _no_network)
    register_agent_backend(_FakeBackend)
    try:
        widget = AgentChatDock(main_window=None)
        qtbot.addWidget(widget)
        _settle(qtbot)
        widget._populate_session_list(widget._sessions[widget._current].backend)
        widget._on_session_delete("whatever")  # must not raise
    finally:
        unregister_agent_backend(_FakeBackend.display_name)
