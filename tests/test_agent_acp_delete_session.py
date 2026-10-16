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



def test_the_probe_keeps_the_commands_the_agent_announces(tmp_path):
    command, _ = _agent(tmp_path, deletes=False)
    command.append("--commands")
    sessions.acp_config_options(command, cwd=tmp_path)
    assert sessions.acp_probed_commands(command) == ["/review", "/sciqlop-catalogs"]


def test_an_agent_that_announces_nothing_has_no_probed_commands(tmp_path):
    command, _ = _agent(tmp_path, deletes=False)
    sessions.acp_config_options(command, cwd=tmp_path)
    assert sessions.acp_probed_commands(command) == []


def test_before_its_session_announces_commands_the_backend_offers_the_probed_ones(tmp_path):
    import asyncio
    command, _ = _agent(tmp_path, deletes=False)
    command.append("--commands")
    sessions.acp_config_options(command, cwd=tmp_path)
    backend = SimpleNamespace(acp_command=lambda: command, _slash_commands=[])
    assert asyncio.run(AcpAgentBackend.list_slash_commands(backend)) == ["/review", "/sciqlop-catalogs"]
    backend._slash_commands = ["/init"]
    assert asyncio.run(AcpAgentBackend.list_slash_commands(backend)) == ["/init"]



def _record_lookup_thread(monkeypatch, workspace):
    import threading
    threads = []

    def lookup():
        threads.append(threading.current_thread())
        return workspace

    monkeypatch.setattr(sessions, "current_workspace_dir", lookup)
    return threads


def test_the_probe_resolves_the_workspace_on_the_callers_thread(tmp_path, monkeypatch):
    # current_workspace_dir goes through an @on_main_thread call: made from the probe's worker while the main
    # thread waits for that worker, it deadlocked SciQLop at plugin load (opencode 2, macOS).
    import threading
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    threads = _record_lookup_thread(monkeypatch, workspace)
    command, state = _agent(tmp_path, deletes=True)
    sessions.acp_config_options(command)
    assert threads and all(t is threading.current_thread() for t in threads)
    assert json.loads(state.read_text())["created"] == [str(workspace)]


def test_the_sync_session_replay_resolves_the_workspace_on_the_callers_thread(tmp_path, monkeypatch):
    import threading
    threads = _record_lookup_thread(monkeypatch, tmp_path)
    command, _ = _agent(tmp_path, deletes=False)
    sessions.acp_load_session_messages(command, "s1", tmp_path)
    assert threads and all(t is threading.current_thread() for t in threads)


def test_a_worker_that_never_returns_times_out_instead_of_hanging():
    import threading
    release = threading.Event()

    async def stuck():
        release.wait()  # a blocking wait, like a call marshalled to a busy main thread

    outcome = {}

    def call():
        try:
            sessions._run_async(stuck, timeout=0.2)
        except Exception as error:
            outcome["error"] = error

    caller = threading.Thread(target=call, daemon=True)
    caller.start()
    caller.join(timeout=10)
    release.set()
    assert not caller.is_alive(), "_run_async waited for a stuck worker past its timeout"
    assert "error" in outcome
