"""Installing into the running workspace must not move the stack SciQLop is running on.

%install ran a bare `uv pip install`, so `%install somepkg` could upgrade PySide6,
SciQLopPlots or numpy under the live process. It now shares the app store's
guarded install: the loaded base stack is pinned, SciQLop stays host-provided.
"""
import importlib.metadata
from pathlib import Path
from types import SimpleNamespace

from SciQLop.components.workspaces.backend import live_install


def _captured_run(monkeypatch):
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        for flag in ("--constraint", "--override"):
            if flag in cmd:
                seen[flag] = Path(cmd[cmd.index(flag) + 1]).read_text()
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(live_install.subprocess, "run", fake_run)
    return seen


def test_a_guarded_install_pins_the_running_pyside6(monkeypatch):
    seen = _captured_run(monkeypatch)
    live_install.guarded_install(["somepkg"])
    pyside = importlib.metadata.version("PySide6")
    assert f"PySide6=={pyside}" in seen["--constraint"]
    assert "sciqlop" in seen["--override"].lower()
    assert seen["cmd"][-1] == "somepkg"


def test_the_install_magic_uses_the_guarded_install(tmp_path, monkeypatch):
    from SciQLop.components.workspaces.backend.workspace import Workspace
    from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest
    seen = _captured_run(monkeypatch)
    m = WorkspaceManifest(name="T")
    m.save(tmp_path / "workspace.sciqlop")
    ws = Workspace.__new__(Workspace)
    ws._manifest, ws._manifest_path = m, tmp_path / "workspace.sciqlop"
    assert ws.add_packages(["somepkg"])["ok"] is True
    assert "--constraint" in seen["cmd"]
