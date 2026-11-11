"""Command-line tools that plugins declare in plugin.json, installed with uv into the workspace's .tools
folder (proposal: plugins_sciqlop/sciqlop_vibe/SCIQLOP_CHANGES.md, review /tmp/workspace-tools-comments.md)."""
import json
import shutil
import subprocess
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

    def install(parent, tool, installed=None):
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
    monkeypatch.setattr(chat_dock, "offer_tool_install", lambda parent, tool, installed=None: offered.append(tool) or False)
    dock = open_dock()
    qtbot.waitUntil(lambda: offered == [VIBE], timeout=2000)
    _settle(qtbot)
    assert dock._current != _NEEDS_TOOL


# ---- updates: the installed version no longer fits the plugin's range ----

def _fake_uv_env(workspace, package, version):
    site = workspace / ".tools" / "envs" / package / "lib" / "python3.14" / "site-packages"
    (site / f"{package.replace('-', '_')}-{version}.dist-info").mkdir(parents=True, exist_ok=True)
    (site / f"{package.replace('-', '_')}-{version}.dist-info" / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: {package}\nVersion: {version}\n")
    (workspace / ".tools" / "envs" / package / "uv-receipt.toml").write_text(
        f'[tool]\nrequirements = [{{ name = "{package}" }}]\n')


def test_an_installed_version_outside_the_range_asks_for_an_update(workspace, vibe_plugin):
    _fake_install(workspace, "vibe-acp")
    _fake_uv_env(workspace, "mistral-vibe", "3.0.2")
    with pytest.raises(tools.ToolOutdated) as outdated:
        tools.tool_command("vibe-acp")
    assert outdated.value.installed == "3.0.2" and outdated.value.tool == VIBE
    assert isinstance(outdated.value, tools.ToolMissing)   # the dock's install offer catches both


def test_a_version_inside_the_range_runs(workspace, vibe_plugin):
    path = _fake_install(workspace, "vibe-acp")
    _fake_uv_env(workspace, "mistral-vibe", "3.4.0")
    assert tools.tool_command("vibe-acp") == str(path)


def test_the_offer_says_update_for_an_outdated_tool(qtbot):
    from SciQLop.components.workspaces.ui.tool_install import _InstallDialog
    dialog = _InstallDialog(None, VIBE, installed="3.0.2")
    qtbot.addWidget(dialog)
    assert dialog.windowTitle() == "Update mistral-vibe?" and "3.0.2" in dialog._label.text()


# ---- removing the tools no active plugin declares ----

def test_tools_no_active_plugin_declares_are_unused(workspace, vibe_plugin):
    _fake_uv_env(workspace, "mistral-vibe", "3.4.0")
    _fake_uv_env(workspace, "old-cli", "1.0")
    _fake_npm(workspace, "@scope/old-js", "1.0.0", {"old-js": "cli.js"}, spec="^1")
    assert sorted((t.kind, t.package) for t in tools.unused_tools()) == [("npm", "@scope/old-js"), ("uv", "old-cli")]


def test_removing_a_uv_tool_asks_uv(workspace, monkeypatch):
    calls = []
    monkeypatch.setattr(tools.subprocess, "run", lambda argv, **kw: calls.append((argv, kw["env"])))
    tools.remove_tool(tools.Installed("uv", "old-cli"))
    argv, env = calls[0]
    assert argv[1:] == ["tool", "uninstall", "old-cli"] and env["UV_TOOL_DIR"] == str(workspace / ".tools" / "envs")


def test_removing_an_npm_tool_deletes_its_folder(workspace):
    prefix = _fake_npm(workspace, "@scope/old-js", "1.0.0", {"old-js": "cli.js"}, spec="^1")
    tools.remove_tool(tools.Installed("npm", "@scope/old-js"))
    assert not prefix.exists()


def test_the_palette_command_removes_after_asking(qtbot, workspace, vibe_plugin, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from SciQLop.components.workspaces.ui import tool_install
    _fake_uv_env(workspace, "old-cli", "1.0")
    removed = []
    monkeypatch.setattr(tools, "remove_tool", removed.append)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    tool_install.remove_unused_tools(None)
    assert removed == [tools.Installed("uv", "old-cli")]


# ---- npm ----

OPENCODE = ToolSpec(package="@opencode/cli", version=">=2 <3", commands=["opencode"], kind="npm")


def _fake_npm(workspace, package, version, bins, spec, native=False):
    prefix = workspace / ".tools" / "npm" / tools.npm_slug(package)
    pkg = prefix / "node_modules" / package
    pkg.mkdir(parents=True, exist_ok=True)
    (prefix / "package.json").write_text(json.dumps({"dependencies": {package: spec}}))
    (pkg / "package.json").write_text(json.dumps({"name": package, "version": version, "bin": bins}))
    for target in bins.values():
        (pkg / target).parent.mkdir(parents=True, exist_ok=True)
        (pkg / target).write_bytes(b"\x7fELF" if native else b"#!/usr/bin/env node\nconsole.log(1)\n")
    return prefix


@pytest.fixture
def opencode_plugin(monkeypatch):
    monkeypatch.setitem(STATES, "sciqlop_opencode", PluginState("active", "0.4.0", tools=(OPENCODE,)))


@pytest.fixture
def fake_npm(tmp_path_factory, monkeypatch):
    """An npm layout like SciQLop's bundled one: node and node_modules/npm/bin/npm-cli.js next to npm."""
    root = tmp_path_factory.mktemp("node")
    for f in ("npm", "node", "node_modules/npm/bin/npm-cli.js", "node_modules/npm/node_modules/semver/index.js"):
        (root / f).parent.mkdir(parents=True, exist_ok=True)
        (root / f).write_text("")
    monkeypatch.setattr(tools, "find_npm", lambda: str(root / "npm"))
    # The fake node can't run npm's semver check: every installed version is in range unless a test says no.
    monkeypatch.setattr(tools.subprocess, "run", lambda argv, **kw: subprocess.CompletedProcess(argv, 0))
    return root


def test_a_native_npm_command_runs_directly(workspace, opencode_plugin, fake_npm):
    prefix = _fake_npm(workspace, "@opencode/cli", "2.1.0", {"opencode": "bin/opencode.exe"}, spec=">=2 <3", native=True)
    assert tools.tool_argv("opencode") == [str(prefix / "node_modules" / "@opencode/cli" / "bin" / "opencode.exe")]
    assert tools.tool_command("opencode") == tools.tool_argv("opencode")[0]


def test_a_javascript_npm_command_runs_with_node(workspace, fake_npm, monkeypatch):
    tool = ToolSpec(package="cowsay", commands=["cowsay"], kind="npm")
    monkeypatch.setitem(STATES, "js", PluginState("active", "1", tools=(tool,)))
    prefix = _fake_npm(workspace, "cowsay", "1.6.0", {"cowsay": "cli.js"}, spec="^1.6.0")
    assert tools.tool_argv("cowsay") == [str(fake_npm / "node"), str(prefix / "node_modules" / "cowsay" / "cli.js")]
    with pytest.raises(ValueError):
        tools.tool_command("cowsay")   # one path can't run it: use tool_argv


def test_an_npm_version_outside_the_range_asks_for_an_update(workspace, opencode_plugin, fake_npm, monkeypatch):
    _fake_npm(workspace, "@opencode/cli", "1.9.0", {"opencode": "bin/opencode.exe"}, spec="^1.9.0", native=True)
    asked = []

    def semver(argv, **kw):   # stands in for node + npm's semver module: 1.9.0 is not >=2 <3
        asked.append(argv[-3:])
        return subprocess.CompletedProcess(argv, 1)
    monkeypatch.setattr(tools.subprocess, "run", semver)
    with pytest.raises(tools.ToolOutdated) as outdated:
        tools.tool_argv("opencode")
    assert outdated.value.installed == "1.9.0"
    assert asked == [[str(fake_npm / "node_modules/npm/node_modules/semver"), "1.9.0", ">=2 <3"]]


@pytest.mark.skipif(not shutil.which("npm"), reason="needs npm")
def test_npm_ranges_are_checked_by_npms_own_semver():
    def outdated(installed, wanted):
        return tools._npm_outdated(ToolSpec(package="esbuild", version=wanted, commands=["esbuild"], kind="npm"),
                                   installed)
    assert not outdated("0.25.12", "^0.25.0")    # npm records "^0.25.12": text comparison would say outdated
    assert outdated("0.25.12", "^0.26.0")
    assert not outdated("2.1.0", ">=2 <3")


def test_a_missing_npm_tool_is_missing(workspace, opencode_plugin, fake_npm):
    with pytest.raises(tools.ToolMissing):
        tools.tool_argv("opencode")


def test_the_npm_install_command_uses_node_and_its_own_prefix(workspace, fake_npm):
    argv, env = tools.install_command(OPENCODE, workspace)
    prefix = workspace / ".tools" / "npm" / tools.npm_slug("@opencode/cli")
    assert argv == [str(fake_npm / "node"), str(fake_npm / "node_modules/npm/bin/npm-cli.js"), "install",
                    "--prefix", str(prefix), "--no-audit", "--no-fund", "@opencode/cli@>=2 <3"]


def test_without_npm_the_install_says_so(workspace, monkeypatch):
    monkeypatch.setattr(tools, "find_npm", lambda: None)
    with pytest.raises(RuntimeError, match="npm"):
        tools.install_command(OPENCODE, workspace)
