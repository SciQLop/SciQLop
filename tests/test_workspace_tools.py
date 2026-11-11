"""Command-line tools that plugins declare in plugin.json, installed with uv into the workspace's .tools
folder (proposal: plugins_sciqlop/sciqlop_vibe/SCIQLOP_CHANGES.md, review /tmp/workspace-tools-comments.md)."""
import sys

import pytest

from SciQLop.components.plugins.backend.loader.context import STATES, PluginState
from SciQLop.components.plugins.backend.loader.plugin_desc import PluginDesc, ToolSpec
from SciQLop.components.workspaces.backend import tools

VIBE = ToolSpec(package="mistral-vibe", version=">=3.1,<4", commands=["vibe-acp", "vibe"])


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("SCIQLOP_WORKSPACE_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def vibe_plugin(monkeypatch):
    monkeypatch.setitem(STATES, "sciqlop_vibe", PluginState("active", "0.1.0", tools=(VIBE,)))
    monkeypatch.setitem(STATES, "sciqlop_off", PluginState("failed", "0.1.0", tools=(
        ToolSpec(package="other", commands=["other-cli"]),)))


def _fake_install(workspace, command):
    path = tools.bin_dir(workspace) / (command + (".exe" if sys.platform == "win32" else ""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("")
    return path


def test_plugin_json_declares_tools():
    desc = PluginDesc(name="sciqlop_vibe", version="0.1.0",
                      tools=[{"package": "mistral-vibe", "version": ">=3.1,<4", "commands": ["vibe-acp"]}])
    assert desc.tools[0].package == "mistral-vibe" and desc.tools[0].kind == "uv"
    assert PluginDesc(name="x", version="1").tools == []


def test_only_active_plugins_declare_tools(vibe_plugin):
    assert tools.declared_tools() == [VIBE]


def test_an_installed_tool_resolves_to_the_workspace_bin(workspace, vibe_plugin):
    path = _fake_install(workspace, "vibe-acp")
    assert tools.tool_command("vibe-acp") == str(path)


def test_a_missing_tool_says_which_package_provides_it(workspace, vibe_plugin):
    with pytest.raises(tools.ToolMissing) as missing:
        tools.tool_command("vibe-acp")
    assert missing.value.tool == VIBE and missing.value.command == "vibe-acp"
    assert "mistral-vibe" in str(missing.value)


def test_a_command_no_active_plugin_declares_is_refused(workspace, vibe_plugin):
    _fake_install(workspace, "other-cli")   # even installed: its plugin is not active
    with pytest.raises(LookupError):
        tools.tool_command("other-cli")


def test_a_tool_on_path_is_not_used(workspace, vibe_plugin, tmp_path_factory, monkeypatch):
    elsewhere = tmp_path_factory.mktemp("path")
    (elsewhere / "vibe-acp").write_text("")
    monkeypatch.setenv("PATH", str(elsewhere))
    with pytest.raises(tools.ToolMissing):
        tools.tool_command("vibe-acp")


def test_the_install_command_keeps_the_tool_in_the_workspace(workspace):
    argv, env = tools.install_command(VIBE, workspace)
    assert argv[1:4] == ["tool", "install", "--native-tls"]
    assert argv[-1] == "mistral-vibe>=3.1,<4"
    assert "--python" in argv and argv[argv.index("--python") + 1] == sys.executable
    assert env["UV_TOOL_DIR"] == str(workspace / ".tools" / "envs")
    assert env["UV_TOOL_BIN_DIR"] == str(workspace / ".tools" / "bin")


def test_a_tool_can_ask_for_its_own_python(workspace):
    argv, _ = tools.install_command(ToolSpec(package="t", commands=["t"], python=">=3.12,<3.14"), workspace)
    assert argv[argv.index("--python") + 1] == ">=3.12,<3.14"


def test_exported_workspaces_leave_the_tools_out():
    from pathlib import Path
    from SciQLop.components.workspaces.backend.workspace_archive import is_excluded
    assert is_excluded(Path(".tools/envs/mistral-vibe/bin/python"))


# ---- the agent dock offers the install ----

from .fixtures import qapp_cls, sciqlop_resources  # noqa: E402,F401 — fixtures
from .test_agent_chat_dock_wiring import _FakeBackend, _settle  # noqa: E402
from .test_agent_session_archive_dock import loop  # noqa: E402,F401 — fixture

_NEEDS_TOOL = "NeedsVibe"


class _NeedsVibe(_FakeBackend):
    display_name = _NEEDS_TOOL

    def __init__(self, ctx=None):
        tools.tool_command("vibe-acp")   # what an AcpAgentBackend's acp_command() does
        super().__init__(ctx)


@pytest.fixture
def open_dock(qtbot, sciqlop_resources, monkeypatch, loop, workspace, vibe_plugin):
    from SciQLop.components.agents import model_capabilities
    from SciQLop.components.agents.chat_dock import AgentChatDock
    from SciQLop.components.agents.registry import register_agent_backend, unregister_agent_backend
    from SciQLop.components.agents.settings import AgentChatSettings

    async def _no_network():
        return None
    monkeypatch.setattr(model_capabilities, "ensure_registry_fresh", _no_network)
    saved = AgentChatSettings().last_backend
    register_agent_backend(_NeedsVibe)
    docks = []

    def open_on_vibe():
        dock = AgentChatDock(main_window=None)
        qtbot.addWidget(dock)
        docks.append(dock)
        dock._backend_combo.setCurrentText(_NEEDS_TOOL)
        _settle(qtbot)
        return dock
    try:
        yield open_on_vibe
    finally:
        unregister_agent_backend(_NEEDS_TOOL)
        with AgentChatSettings() as cfg:
            cfg.last_backend = saved


def test_the_dock_offers_to_install_a_missing_tool_then_retries(qtbot, open_dock, workspace, monkeypatch):
    from SciQLop.components.agents import chat_dock
    offered = []

    def install(parent, tool):
        offered.append(tool)
        _fake_install(workspace, "vibe-acp")
        return True
    monkeypatch.setattr(chat_dock, "offer_tool_install", install)
    dock = open_dock()
    qtbot.waitUntil(lambda: offered == [VIBE], timeout=2000)
    qtbot.waitUntil(lambda: dock._current == _NEEDS_TOOL, timeout=2000)


def test_declining_the_install_leaves_the_failure_message(qtbot, open_dock, monkeypatch):
    from SciQLop.components.agents import chat_dock
    offered = []
    monkeypatch.setattr(chat_dock, "offer_tool_install", lambda parent, tool: offered.append(tool) or False)
    dock = open_dock()
    qtbot.waitUntil(lambda: offered == [VIBE], timeout=2000)
    _settle(qtbot)
    assert dock._current != _NEEDS_TOOL
