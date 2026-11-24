"""What a click on a link in the agent transcript does.

Shared by the native and the web transcript views: web links go to the system
browser, files in the workspace open in the JupyterLab pane, anything else is
refused with a message the dock shows in its status line.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional
from urllib.parse import unquote, urlsplit

from ..tools.notebooks import workspace_dir

_WEB_SCHEMES = ("http", "https")


@dataclass(frozen=True)
class LinkAction:
    """``target`` is the URL (web), the path relative to the workspace
    (workspace), or the message to show (refused)."""
    kind: Literal["web", "workspace", "refused"]
    target: str


def _local_path(href: str) -> Optional[str]:
    parts = urlsplit(href)
    if parts.scheme == "file":
        return None if parts.netloc else unquote(parts.path)
    # A one-letter scheme is a Windows drive ("C:/..."), not a URL scheme.
    if parts.scheme and len(parts.scheme) > 1:
        return None
    return unquote(href)


def _is_unc(path: str) -> bool:
    return path.startswith(("//", "\\\\"))


def _lexically_inside(path: str, workspace: Path) -> bool:
    # Checked on the text alone: on Windows, touching a UNC path makes the
    # system contact that server (and send NTLM credentials) before any
    # check that runs after resolve() or exists().
    candidate = os.path.normpath(os.path.join(workspace, path))
    try:
        return os.path.commonpath([candidate, str(workspace)]) == str(workspace)
    except ValueError:  # different drives on Windows
        return False


def classify_link(href: str, workspace: Path) -> LinkAction:
    if urlsplit(href).scheme in _WEB_SCHEMES:
        return LinkAction("web", href)
    path = _local_path(href)
    if not path or _is_unc(path):
        return LinkAction("refused", f"Can't open this link: {href!r}")
    workspace = workspace.resolve()
    if not _lexically_inside(path, workspace):
        return LinkAction("refused", f"Can't open {path}: it is outside the workspace")
    target = (workspace / path).resolve()
    if not target.is_relative_to(workspace):
        return LinkAction("refused", f"Can't open {path}: it is outside the workspace")
    if not target.exists():
        return LinkAction("refused", f"Can't open {path}: no such file in the workspace")
    return LinkAction("workspace", target.relative_to(workspace).as_posix())


def _open_in_browser(url: str) -> None:
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices
    QDesktopServices.openUrl(QUrl(url))


def _open_in_lab(rel_path: str) -> None:
    from SciQLop.core.sciqlop_application import sciqlop_app
    sciqlop_app().main_window.open_in_jupyterlab(rel_path)


def open_link(href: str) -> Optional[str]:
    """Open ``href``; return a message for the user when nothing was opened."""
    try:
        action = classify_link(href, workspace_dir())
    except RuntimeError as error:
        return f"Can't open {href}: {error}"
    if action.kind == "web":
        _open_in_browser(action.target)
    elif action.kind == "workspace":
        _open_in_lab(action.target)
    else:
        return action.target
    return None
