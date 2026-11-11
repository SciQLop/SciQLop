"""Command-line tools that plugins declare in plugin.json ("tools"), installed with uv into the workspace's
own .tools folder. Each tool gets its own environment, so its pinned dependencies never touch the workspace
venv (Mistral Vibe pins agent-client-protocol and mcp versions SciQLop can't share).

Nothing is recorded in the workspace manifest: the tools a workspace offers are those its active plugins
declare, like their python_dependencies. Installing happens on demand, never in the startup sync.
Only declared commands resolve, and never from PATH, so the workspace decides which version runs.
That is a consistency rule, not a security boundary: plugins already run arbitrary code.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from SciQLop.components.plugins.backend.loader.context import STATES
from SciQLop.components.plugins.backend.loader.plugin_desc import ToolSpec

from .uv import uv_command

TOOLS_DIRNAME = ".tools"


class ToolMissing(RuntimeError):
    """A declared tool is not installed in this workspace yet: offer to install *tool*."""

    def __init__(self, tool: ToolSpec, command: str):
        super().__init__(f"{command} is not installed in this workspace: it comes with {tool.package}")
        self.tool, self.command = tool, command


def _workspace(workspace_dir: Optional[os.PathLike]) -> Path:
    path = workspace_dir or os.environ.get("SCIQLOP_WORKSPACE_DIR")
    if not path:
        raise RuntimeError("no workspace: SCIQLOP_WORKSPACE_DIR is not set")
    return Path(path)


def bin_dir(workspace_dir: Optional[os.PathLike] = None) -> Path:
    return _workspace(workspace_dir) / TOOLS_DIRNAME / "bin"


def _envs_dir(workspace_dir: Path) -> Path:
    return workspace_dir / TOOLS_DIRNAME / "envs"


def declared_tools() -> list[ToolSpec]:
    """The tools the active plugins declare, each once."""
    seen = {}
    for state in STATES.values():
        if state.status == "active":
            for tool in state.tools:
                seen.setdefault(tool, None)
    return list(seen)


def _declaring(command: str) -> ToolSpec:
    tool = next((t for t in declared_tools() if command in t.commands), None)
    if tool is None:
        raise LookupError(f"{command!r} is not a command any active plugin declares in its plugin.json tools")
    return tool


def _executable(workspace_dir: Path, command: str) -> Path:
    return bin_dir(workspace_dir) / (command + (".exe" if sys.platform == "win32" else ""))


def tool_command(command: str, workspace_dir: Optional[os.PathLike] = None) -> str:
    """The path of *command* in this workspace's tools. Raises ToolMissing when its plugin declares it but it
    is not installed yet, LookupError when no active plugin declares it."""
    tool = _declaring(command)
    path = _executable(_workspace(workspace_dir), command)
    if not path.is_file():
        raise ToolMissing(tool, command)
    return str(path)


def install_command(tool: ToolSpec, workspace_dir: Optional[os.PathLike] = None) -> tuple[list[str], dict]:
    """argv and environment that install *tool* into the workspace with uv.

    ``--native-tls``: corporate proxies (see live_install). No SciQLop overrides or constraints: the tool's
    pins must stay its own. ``--python``: the tool's own request when it declares one (uv may then download
    an interpreter), else SciQLop's interpreter, so nothing is downloaded behind the user's back."""
    workspace = _workspace(workspace_dir)
    env = dict(os.environ, UV_TOOL_DIR=str(_envs_dir(workspace)), UV_TOOL_BIN_DIR=str(bin_dir(workspace)))
    argv = uv_command("tool", "install", "--native-tls", "--python", tool.python or sys.executable,
                      f"{tool.package}{tool.version}")
    return argv, env
