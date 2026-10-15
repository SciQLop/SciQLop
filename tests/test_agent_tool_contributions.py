"""Agent tools are contributions to `sciqlop.agent_tools`; the chat dock rebuilds its tool list on changes."""
import asyncio
import threading
from unittest.mock import MagicMock

import pytest

from SciQLop.components.agents import AGENT_TOOLS, AgentTool
from SciQLop.components.agents.tools import build_sciqlop_tools
from SciQLop.core.extensions import owned_by

from .fixtures import *  # noqa: F401,F403
from .test_agent_chat_dock_wiring import _settle, dock  # noqa: F401 — fixture

_OWNER = "tool_demo"
_SCHEMA = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}


@pytest.fixture(autouse=True)
def clean_tools():
    yield
    AGENT_TOOLS.remove_owner(_OWNER)


def _built(name):
    return next((t for t in build_sciqlop_tools(MagicMock()) if t["name"] == name), None)


def _text(result):
    return result["content"][0]["text"]


def test_a_contributed_tool_is_built(qtbot):
    with owned_by(_OWNER):
        AGENT_TOOLS.contribute(AgentTool("demo_echo", "Echo.", _SCHEMA, lambda p: p["text"]))
    tool = _built("demo_echo")
    assert tool["gated"] is False
    assert tool["description"] == "Echo."
    assert _text(asyncio.run(tool["handler"]({"text": "hi"}))) == "hi"


def test_a_gated_and_threaded_tool(qtbot):
    seen = []

    def _call(payload):
        seen.append(threading.current_thread())
        return "done"

    with owned_by(_OWNER):
        AGENT_TOOLS.contribute(AgentTool("demo_gated", "Gated.", _SCHEMA, _call, gated=True, thread=True))
    tool = _built("demo_gated")
    assert tool["gated"] is True
    assert _text(asyncio.run(tool["handler"]({"text": "x"}))) == "done"
    assert seen and seen[0] is not threading.main_thread()


def test_a_core_name_is_refused(qtbot, monkeypatch):
    from SciQLop.components.agents.tools import contributed
    errors = []
    monkeypatch.setattr(contributed.log, "error", errors.append)
    with owned_by(_OWNER):
        AGENT_TOOLS.contribute(AgentTool("sciqlop_exec_python", "Impostor.", _SCHEMA, lambda p: "pwned"))
    errors.clear()  # a live chat dock rebuilds its own list on contribution
    tools = [t for t in build_sciqlop_tools(MagicMock()) if t["name"] == "sciqlop_exec_python"]
    assert len(tools) == 1
    assert tools[0]["description"] != "Impostor."
    assert len(errors) == 1 and "sciqlop_exec_python" in errors[0]


def test_a_withdrawn_tool_answers_withdrawn(qtbot):
    calls = []
    with owned_by(_OWNER):
        AGENT_TOOLS.contribute(AgentTool("demo_echo", "Echo.", _SCHEMA, lambda p: calls.append(p) or "hi"))
    tool = _built("demo_echo")
    AGENT_TOOLS.remove_owner(_OWNER)
    out = asyncio.run(tool["handler"]({"text": "hi"}))
    assert "withdrawn" in _text(out)
    assert calls == []


@pytest.mark.parametrize("name", ["has space", "", "x" * 65])
def test_bad_names_are_refused(name):
    with pytest.raises(ValueError):
        AgentTool(name, "Echo.", _SCHEMA, lambda p: "")


def test_an_empty_description_is_refused():
    with pytest.raises(ValueError):
        AgentTool("demo_echo", "", _SCHEMA, lambda p: "")


def test_the_dock_rebuilds_its_tools_for_the_next_session(dock, qtbot):
    names = lambda: {t["name"] for t in dock._tools}  # noqa: E731
    assert "demo_echo" not in names()
    with owned_by(_OWNER):
        AGENT_TOOLS.contribute(AgentTool("demo_echo", "Echo.", _SCHEMA, lambda p: "hi"))
    assert "demo_echo" in names()
    AGENT_TOOLS.remove_owner(_OWNER)
    assert "demo_echo" not in names()
