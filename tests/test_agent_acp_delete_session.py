"""ACP backends delete sessions when the agent advertises session/delete (opencode 2 does, opencode 1 does not).

The fake agent is a real subprocess speaking ACP on stdio, so these go through the client SDK on the wire.
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.skipif(
    pytest.importorskip("acp") is None, reason="agent-client-protocol not installed"
)

from SciQLop.components.agents.acp import sessions
from SciQLop.components.agents.acp.backend import AcpAgentBackend

_AGENT = str(Path(__file__).with_name("acp_fake_agent.py"))


def _agent(tmp_path, deletes: bool, sessions_in=None):
    state = tmp_path / "agent_state.json"
    state.write_text(json.dumps({"sessions": [{"sessionId": sid, "cwd": str(cwd)} for sid, cwd in sessions_in or []]}))
    return [sys.executable, _AGENT, str(state), *(["--deletes"] if deletes else [])], state


def _ids(state):
    return [s["sessionId"] for s in json.loads(state.read_text())["sessions"]]


def _backend(command):
    return SimpleNamespace(acp_command=lambda: command)


def test_an_agent_that_advertises_delete_deletes_the_session(tmp_path):
    command, state = _agent(tmp_path, deletes=True, sessions_in=[("a", tmp_path), ("b", tmp_path)])
    sessions.acp_list_sessions(command, cwd=tmp_path)
    assert AcpAgentBackend.can_delete_sessions(_backend(command))
    AcpAgentBackend.delete_session(_backend(command), "a")
    assert _ids(state) == ["b"]


def test_an_agent_without_delete_cannot_delete(tmp_path):
    command, state = _agent(tmp_path, deletes=False, sessions_in=[("a", tmp_path)])
    sessions.acp_list_sessions(command, cwd=tmp_path)
    assert not AcpAgentBackend.can_delete_sessions(_backend(command))


def test_before_any_agent_ran_delete_is_not_offered(tmp_path):
    command, _ = _agent(tmp_path, deletes=True)
    assert not AcpAgentBackend.can_delete_sessions(_backend(command))


def test_a_failed_delete_raises(tmp_path):
    command, state = _agent(tmp_path, deletes=False, sessions_in=[("a", tmp_path)])
    with pytest.raises(Exception):
        sessions.acp_delete_session(command, "a")
    assert _ids(state) == ["a"]


def test_the_probe_runs_in_the_workspace_and_deletes_its_session_when_the_agent_can(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(sessions, "current_workspace_dir", lambda: workspace)
    command, state = _agent(tmp_path, deletes=True, sessions_in=[("kept", workspace)])
    sessions.acp_config_options(command)
    assert _ids(state) == ["kept"]
    assert json.loads(state.read_text())["created"] == [str(workspace)]


def test_the_probe_of_an_agent_without_delete_stays_out_of_the_workspace(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(sessions, "current_workspace_dir", lambda: workspace)
    command, state = _agent(tmp_path, deletes=False)
    sessions.acp_config_options(command)
    [probe] = json.loads(state.read_text())["sessions"]
    assert probe["cwd"] != str(workspace)


@pytest.mark.parametrize("backend, offered", [
    (SimpleNamespace(), False),
    (SimpleNamespace(delete_session=lambda sid: None), True),
    (SimpleNamespace(delete_session=lambda sid: None, can_delete_sessions=lambda: False), False),
    (SimpleNamespace(delete_session=lambda sid: None, can_delete_sessions=lambda: True), True),
])
def test_the_dock_offers_delete_only_when_the_backend_can(backend, offered):
    from SciQLop.components.agents.chat_dock import deletes_sessions
    assert deletes_sessions(backend) is offered


def test_an_sdk_with_delete_session_is_used_directly():
    import asyncio
    deleted = []

    class _Conn:
        async def delete_session(self, session_id):
            deleted.append(session_id)

    asyncio.run(sessions.delete_session_on(_Conn(), "s7"))
    assert deleted == ["s7"]
