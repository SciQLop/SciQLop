"""Plugins load one by one, after the first backend plugin has created the dock and its session: a tool or a
skill contributed later must still reach the agent, and last run's plugin skills must survive start-up."""
import asyncio

import pytest

from SciQLop.components.agents import (
    AGENT_BACKENDS, AGENT_SKILLS, AGENT_TOOLS, AgentSkill, AgentTool, register_agent_backend)
from SciQLop.components.agents import chat_dock
from SciQLop.components.agents.chat import ChatMessage, TextBlock
from SciQLop.core.extensions import owned_by

from .fixtures import *  # noqa: F401,F403
from .test_agent_chat_dock_wiring import _FAKE, _FakeBackend, _settle, dock  # noqa: F401 — fixture

_LATE = "late_plugin"
_SCHEMA = {"type": "object", "properties": {}}


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.setattr(chat_dock, "current_workspace_dir", lambda: ws)
    return ws


@pytest.fixture
def built(monkeypatch):
    """Every fake backend the dock builds, with the context it was given."""
    backends = []
    original = _FakeBackend.__init__

    def _init(self, ctx=None):
        original(self, ctx)
        self.ctx = ctx
        backends.append(self)

    monkeypatch.setattr(_FakeBackend, "__init__", _init)
    return backends


@pytest.fixture
def late():
    yield
    AGENT_TOOLS.remove_owner(_LATE)
    AGENT_SKILLS.remove_owner(_LATE)
    AGENT_BACKENDS.remove_owner(_LATE)


def _skill_source(tmp_path, name="late-skill"):
    folder = tmp_path / "src" / name
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text("# late", encoding="utf-8")
    return folder


def _published(ws, name="late-skill"):
    return ws / ".claude" / "skills" / name / "SKILL.md"


def _built_for(dock, built):
    """Docks left over by earlier tests follow the extension points too."""
    return [b for b in built if b.ctx is not None and b.ctx.confirm_cb.__self__ is dock]


def _tool_names(backend):
    return {t["name"] for t in backend.ctx.tools}


def _contribute_late(tmp_path):
    with owned_by(_LATE):
        AGENT_TOOLS.contribute(AgentTool("late_echo", "Echo.", _SCHEMA, lambda p: "hi"))
        AGENT_SKILLS.contribute(AgentSkill("late-skill", _skill_source(tmp_path)))


def test_a_late_tool_and_skill_reach_the_untouched_session(workspace, built, dock, late, qtbot, tmp_path):
    first = dock._current_backend()
    assert "late_echo" not in _tool_names(first)

    _contribute_late(tmp_path)
    qtbot.waitUntil(lambda: dock._current_backend() is not first, timeout=3000)
    _settle(qtbot)

    assert "late_echo" in _tool_names(dock._current_backend())
    assert _published(workspace).is_file()
    assert len(_built_for(dock, built)) == 2  # one rebuild for the whole burst


def test_a_session_with_messages_gets_the_tool_on_new_session(workspace, built, dock, late, qtbot, tmp_path):
    session = dock._sessions[_FAKE]
    session.messages.append(ChatMessage(role="user", blocks=[TextBlock(text="hi")], done=True))
    first = session.backend

    _contribute_late(tmp_path)
    qtbot.waitUntil(_published(workspace).is_file, timeout=3000)
    _settle(qtbot)
    assert dock._current_backend() is first
    assert "late_echo" not in _tool_names(first)

    dock._on_reset()
    assert dock._current_backend() is not first
    assert "late_echo" in _tool_names(dock._current_backend())
    assert dock._sessions[_FAKE].messages == []


def test_a_handed_out_tools_list_is_never_mutated(workspace, built, dock, late, qtbot, tmp_path):
    tools = dock._current_backend().ctx.tools
    before = list(tools)

    _contribute_late(tmp_path)
    qtbot.waitUntil(lambda: len(_built_for(dock, built)) == 2, timeout=3000)
    assert tools == before


@pytest.fixture
def last_runs_record(workspace):
    skills = workspace / ".claude" / "skills"
    _published(workspace).parent.mkdir(parents=True)
    _published(workspace).write_text("# late", encoding="utf-8")
    (skills / ".sciqlop-published").write_text("late-skill\n", encoding="utf-8")
    return workspace


def test_last_runs_plugin_skill_is_back_once_its_plugin_loads(last_runs_record, built, dock, late, qtbot, tmp_path):
    with owned_by(_LATE):
        AGENT_SKILLS.contribute(AgentSkill("late-skill", _skill_source(tmp_path)))
    qtbot.waitUntil(_published(last_runs_record).is_file, timeout=3000)


class _Hanging(_FakeBackend):
    display_name = "AAA-Hanging"

    async def ask(self, prompt, image_paths=None):
        await asyncio.get_event_loop().create_future()
        yield None


def test_withdrawing_the_backend_in_use_cancels_its_turn(dock, late, qtbot, monkeypatch):
    with owned_by(_LATE):
        register_agent_backend(_Hanging)
    dock._select_backend(_Hanging.display_name)
    _settle(qtbot)
    dock._input.setPlainText("hello")
    dock._on_send()
    _settle(qtbot)
    turn = dock._turn_task
    assert turn is not None and not turn.done()

    cancels = []
    monkeypatch.setattr(_FakeBackend, "cancel", lambda self: cancels.append(self) or asyncio.sleep(0))
    AGENT_BACKENDS.remove_owner(_LATE)
    _settle(qtbot)

    assert turn.cancelled()
    assert dock._current == _FAKE
    assert dock._sessions[_FAKE].messages == []
    dock._on_stop()
    assert cancels == []
