"""`acp_config_options` reads config options from a throwaway ACP session.

Agents persist every session they create (opencode 1.x has no session/delete),
and the dock's history lists the sessions of the workspace dir — so a probe
opened there stacked one empty "New session" per SciQLop start.
"""
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.skipif(
    pytest.importorskip("acp") is None, reason="agent-client-protocol not installed"
)

from SciQLop.components.agents.acp import sessions


def _fake_agent(monkeypatch, workspace):
    opened = []

    class _Conn:
        async def new_session(self, cwd, mcp_servers):
            opened.append(cwd)
            option = SimpleNamespace(id="model", options=[SimpleNamespace(name="M", value="p/m")])
            return SimpleNamespace(session_id="s1", config_options=[option])

    async def spawn(_command):
        return None, _Conn()

    async def kill(_proc, _conn):
        pass

    monkeypatch.setattr(sessions, "_spawn_agent", spawn)
    monkeypatch.setattr(sessions, "_kill", kill)
    monkeypatch.setattr(sessions, "current_workspace_dir", lambda: workspace)
    return opened


def test_probe_session_is_not_opened_in_the_workspace(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    opened = _fake_agent(monkeypatch, workspace)
    assert sessions.acp_config_options(["agent"]) == {"model": [("M", "p/m")]}
    assert len(opened) == 1
    assert opened[0] != str(workspace)


def test_probe_dir_exists_and_is_stable_across_starts(monkeypatch, tmp_path):
    # One fixed dir: the agent accumulates at most one project for it.
    from pathlib import Path

    opened = _fake_agent(monkeypatch, tmp_path / "workspace")
    sessions.acp_config_options(["agent"])
    sessions.acp_config_options(["agent"])
    assert opened[0] == opened[1]
    assert Path(opened[0]).is_absolute() and Path(opened[0]).is_dir()


def test_explicit_cwd_is_still_honoured(monkeypatch, tmp_path):
    opened = _fake_agent(monkeypatch, tmp_path / "workspace")
    sessions.acp_config_options(["agent"], cwd=tmp_path)
    assert opened == [str(tmp_path)]
