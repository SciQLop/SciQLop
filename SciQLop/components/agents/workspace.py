"""Where the agent runs: the active workspace directory.

Agents are given this as their cwd, and it is where `AGENTS.md` is published,
so the resolution has to agree across the ACP layer, the guidance publisher and
the chat dock — hence one function rather than a copy per module.
"""
from __future__ import annotations

import os
from pathlib import Path


def current_workspace_dir() -> Path:
    try:
        from SciQLop.components.workspaces import workspaces_manager_instance
        mgr = workspaces_manager_instance()
        ws = getattr(mgr, "workspace", None)
        wdir = getattr(ws, "workspace_dir", None) if ws is not None else None
        if wdir:
            return Path(wdir).resolve()
    except Exception:
        pass
    env = os.environ.get("SCIQLOP_WORKSPACE_DIR")
    if env:
        return Path(env).resolve()
    return Path.cwd().resolve()
