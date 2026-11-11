"""Command-line tools that plugins declare in plugin.json ("tools"), installed into the workspace's own
.tools folder, each in its own environment, so their pinned dependencies never touch the workspace venv
(Mistral Vibe pins agent-client-protocol and mcp versions SciQLop can't share).

Two kinds: "uv" (a Python package, `uv tool install`, .tools/envs + .tools/bin) and "npm" (an npm package,
`npm install --prefix .tools/npm/<package>`). Each kind is a row of _KINDS: how to install, run, read the
installed version, tell whether it is outdated, and remove.

Nothing is recorded in the workspace manifest: the tools a workspace offers are those its active plugins
declare, like their python_dependencies. Installing happens on demand, never in the startup sync. Only
declared commands resolve, and never from PATH, so the workspace decides which version runs. That is a
consistency rule, not a security boundary: plugins already run arbitrary code.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, NamedTuple, Optional

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.utils import canonicalize_name

from SciQLop.components.plugins.backend.loader.context import STATES
from SciQLop.components.plugins.backend.loader.plugin_desc import ToolSpec

from .uv import uv_command

TOOLS_DIRNAME = ".tools"
_JS_SUFFIXES = (".js", ".cjs", ".mjs")
_SITE_PACKAGES = ("lib/*/site-packages/*.dist-info", "Lib/site-packages/*.dist-info")   # posix, Windows


class ToolMissing(RuntimeError):
    """A declared tool is not installed in this workspace yet: offer to install *tool*."""

    def __init__(self, tool: ToolSpec, command: str, message: str = ""):
        super().__init__(message or f"{command} is not installed in this workspace: it comes with {tool.package}")
        self.tool, self.command = tool, command


class ToolOutdated(ToolMissing):
    """Installed, but its plugin now asks for another version range: offer to update it."""

    def __init__(self, tool: ToolSpec, command: str, installed: str):
        super().__init__(tool, command, f"{tool.package} {installed} is installed; its plugin needs {tool.version}")
        self.installed = installed


class Installed(NamedTuple):
    kind: str
    package: str


# ---- paths ----

def _workspace(workspace_dir: Optional[os.PathLike]) -> Path:
    path = workspace_dir or os.environ.get("SCIQLOP_WORKSPACE_DIR")
    if not path:
        raise RuntimeError("no workspace: SCIQLOP_WORKSPACE_DIR is not set")
    return Path(path)


def bin_dir(workspace_dir: Optional[os.PathLike] = None) -> Path:
    return _workspace(workspace_dir) / TOOLS_DIRNAME / "bin"


def _envs_dir(workspace: Path) -> Path:
    return workspace / TOOLS_DIRNAME / "envs"


def _npm_root(workspace: Path) -> Path:
    return workspace / TOOLS_DIRNAME / "npm"


def npm_slug(package: str) -> str:
    """A folder name for an npm package, scoped ones included: @opencode/cli -> opencode__cli."""
    return package.lstrip("@").replace("/", "__")


# ---- uv kind ----

def _uv_env(workspace: Path) -> dict:
    return dict(os.environ, UV_TOOL_DIR=str(_envs_dir(workspace)), UV_TOOL_BIN_DIR=str(bin_dir(workspace)))


def _uv_install(tool: ToolSpec, workspace: Path) -> tuple[list[str], dict]:
    """``--native-tls``: corporate proxies (see live_install). No SciQLop overrides or constraints: the tool's
    pins must stay its own. ``--python``: the tool's own request when it declares one (uv may then download an
    interpreter), else SciQLop's interpreter, so nothing is downloaded behind the user's back. Installing over
    an older version with a new range upgrades it (uv)."""
    argv = uv_command("tool", "install", "--native-tls", "--python", tool.python or sys.executable,
                      f"{tool.package}{tool.version}")
    return argv, _uv_env(workspace)


def _uv_argv(tool: ToolSpec, workspace: Path, command: str) -> Optional[list[str]]:
    path = bin_dir(workspace) / (command + (".exe" if sys.platform == "win32" else ""))
    return [str(path)] if path.is_file() else None


def _uv_version(tool: ToolSpec, workspace: Path) -> Optional[str]:
    """From the dist-info folder in the tool's environment: no process to start on every backend launch."""
    wanted = canonicalize_name(tool.package)
    env = _envs_dir(workspace) / wanted
    infos = [i for pattern in _SITE_PACKAGES for i in env.glob(pattern)] if env.is_dir() else []
    for info in infos:
        name, _, version = info.name.removesuffix(".dist-info").rpartition("-")
        if canonicalize_name(name) == wanted:
            return version
    return None


def _uv_outdated(tool: ToolSpec, installed: str) -> bool:
    try:
        return bool(tool.version) and not SpecifierSet(tool.version).contains(installed, prereleases=True)
    except InvalidSpecifier:
        return False


def _uv_installed(workspace: Path) -> list[str]:
    envs = _envs_dir(workspace)
    return sorted(p.name for p in envs.iterdir() if (p / "uv-receipt.toml").is_file()) if envs.is_dir() else []


def _uv_remove(package: str, workspace: Path) -> None:
    subprocess.run(uv_command("tool", "uninstall", package), env=_uv_env(workspace),
                   capture_output=True, text=True, check=True)


# ---- npm kind (the layout opencode's installer settled on: node + npm-cli.js, no shell on Windows) ----

def find_npm() -> Optional[str]:
    """SciQLop's bundled npm first (the launcher puts its node dir on PATH), else a system one."""
    return shutil.which("npm")


def _node_for(npm: str) -> Optional[str]:
    here = Path(npm).parent
    return next((str(here / n) for n in ("node.exe", "node") if (here / n).is_file()), None) or shutil.which("node")


def _npm_package_root(npm: str) -> Optional[Path]:
    """npm's own package folder: next to the npm script (SciQLop's bundled node, Windows installs), or where a
    symlinked npm (Linux packages: /usr/bin/npm -> .../npm/bin/npm-cli.js) resolves to."""
    for root in (Path(npm).parent / "node_modules" / "npm", Path(npm).resolve().parents[1]):
        if (root / "bin" / "npm-cli.js").is_file():
            return root
    return None


def _npm_prefix(tool_package: str, workspace: Path) -> Path:
    return _npm_root(workspace) / npm_slug(tool_package)


def _npm_install(tool: ToolSpec, workspace: Path) -> tuple[list[str], dict]:
    """``node npm-cli.js`` rather than ``npm``: on Windows npm is npm.cmd, which CreateProcess can't run
    without a shell. ``--prefix`` rather than ``-g``: the global prefix may be inside SciQLop's install."""
    npm = find_npm()
    if npm is None:
        raise RuntimeError(f"npm not found: install Node.js (https://nodejs.org) to install {tool.package}")
    node, root = _node_for(npm), _npm_package_root(npm)
    runner = [node, str(root / "bin" / "npm-cli.js")] if node is not None and root is not None else [npm]
    spec = f"{tool.package}@{tool.version}" if tool.version else tool.package
    return runner + ["install", "--prefix", str(_npm_prefix(tool.package, workspace)), "--no-audit", "--no-fund",
                     spec], dict(os.environ)


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def _npm_package_dir(tool_package: str, workspace: Path) -> Path:
    return _npm_prefix(tool_package, workspace) / "node_modules" / tool_package


def _npm_bin_target(package_dir: Path, command: str) -> Optional[Path]:
    bins = _read_json(package_dir / "package.json").get("bin")
    if isinstance(bins, str):
        bins = {package_dir.name: bins}
    target = (bins or {}).get(command)
    return package_dir / target if target else None


def _is_javascript(path: Path) -> bool:
    if path.suffix in _JS_SUFFIXES:
        return True
    with path.open("rb") as f:
        first = f.readline(200)
    return first.startswith(b"#!") and b"node" in first


def _npm_argv(tool: ToolSpec, workspace: Path, command: str) -> Optional[list[str]]:
    """The command's real target from the package's "bin", not node_modules/.bin: on Windows that holds only
    .cmd/.ps1 shims. A JavaScript target runs with node; a native one (opencode's binary) directly."""
    target = _npm_bin_target(_npm_package_dir(tool.package, workspace), command)
    if target is None or not target.is_file():
        return None
    if not _is_javascript(target):
        return [str(target)]
    npm = find_npm()
    node = _node_for(npm) if npm else shutil.which("node")
    if node is None:
        raise RuntimeError(f"node not found: {command} is a Node.js program")
    return [node, str(target)]


def _npm_version(tool: ToolSpec, workspace: Path) -> Optional[str]:
    return _read_json(_npm_package_dir(tool.package, workspace) / "package.json").get("version")


_SATISFIES_JS = "process.exit(require(process.argv[1]).satisfies(process.argv[2], process.argv[3]) ? 0 : 1)"


def _npm_outdated(tool: ToolSpec, installed: str) -> bool:
    """Whether *installed* falls outside the plugin's range, asked of the semver module npm ships (npm rewrites
    the range it records, so comparing range text would flag good installs). Unknown when node or that module
    can't be found: not outdated, so a working tool is never blocked."""
    npm = find_npm()
    node, root = (_node_for(npm), _npm_package_root(npm)) if npm else (None, None)
    semver = root / "node_modules" / "semver" if root is not None else None
    if not tool.version or node is None or semver is None or not semver.is_dir():
        return False
    result = subprocess.run([node, "-e", _SATISFIES_JS, str(semver), installed, tool.version],
                            capture_output=True, timeout=10)
    return result.returncode == 1


def _npm_installed(workspace: Path) -> list[str]:
    root = _npm_root(workspace)
    if not root.is_dir():
        return []
    return sorted(name for p in root.iterdir() for name in _read_json(p / "package.json").get("dependencies", {}))


def _npm_remove(package: str, workspace: Path) -> None:
    shutil.rmtree(_npm_prefix(package, workspace))


# ---- the kinds, as data ----

@dataclass(frozen=True)
class _Kind:
    install: Callable[[ToolSpec, Path], tuple[list[str], dict]]
    argv: Callable[[ToolSpec, Path, str], Optional[list[str]]]
    version: Callable[[ToolSpec, Path], Optional[str]]
    outdated: Callable[[ToolSpec, Path, str], bool]
    installed: Callable[[Path], list[str]]
    remove: Callable[[str, Path], None]
    same_package: Callable[[str, str], bool]


_KINDS = {
    "uv": _Kind(_uv_install, _uv_argv, _uv_version, lambda t, w, v: _uv_outdated(t, v), _uv_installed, _uv_remove,
                lambda a, b: canonicalize_name(a) == canonicalize_name(b)),
    "npm": _Kind(_npm_install, _npm_argv, _npm_version, lambda t, w, v: _npm_outdated(t, v), _npm_installed,
                 _npm_remove, lambda a, b: a == b),
}


# ---- the API ----

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


def tool_argv(command: str, workspace_dir: Optional[os.PathLike] = None) -> list[str]:
    """How to run *command* from this workspace's tools: its path, or node and its script. Raises ToolMissing
    when its plugin declares it but it is not installed, ToolOutdated when the installed version no longer
    fits the plugin's range, LookupError when no active plugin declares it."""
    tool, workspace = _declaring(command), _workspace(workspace_dir)
    kind = _KINDS[tool.kind]
    argv = kind.argv(tool, workspace, command)
    if argv is None:
        raise ToolMissing(tool, command)
    installed = kind.version(tool, workspace)
    if installed is not None and kind.outdated(tool, workspace, installed):
        raise ToolOutdated(tool, command, installed)
    return argv


def tool_command(command: str, workspace_dir: Optional[os.PathLike] = None) -> str:
    """The executable of *command* (see tool_argv). A Node.js script needs node in front: use tool_argv."""
    argv = tool_argv(command, workspace_dir)
    if len(argv) != 1:
        raise ValueError(f"{command} runs as {argv!r}: use tool_argv()")
    return argv[0]


def install_command(tool: ToolSpec, workspace_dir: Optional[os.PathLike] = None) -> tuple[list[str], dict]:
    """argv and environment that install (or update) *tool* into the workspace."""
    return _KINDS[tool.kind].install(tool, _workspace(workspace_dir))


def unused_tools(workspace_dir: Optional[os.PathLike] = None) -> list[Installed]:
    """Tools installed in this workspace that no active plugin declares."""
    workspace, declared = _workspace(workspace_dir), declared_tools()
    return [Installed(name, package) for name, kind in _KINDS.items() for package in kind.installed(workspace)
            if not any(t.kind == name and kind.same_package(t.package, package) for t in declared)]


def remove_tool(tool: Installed, workspace_dir: Optional[os.PathLike] = None) -> None:
    _KINDS[tool.kind].remove(tool.package, _workspace(workspace_dir))
