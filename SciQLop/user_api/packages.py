"""Install Python packages into the active workspace and persist them.

Unlike a raw ``pip install``, ``install_packages`` records the packages in the
workspace manifest (``workspace.sciqlop``), so they are reinstalled on the next
launch and survive venv recreation. A newly installed plugin is loaded right
away, exactly as the app store does.
"""
from __future__ import annotations

import re
from importlib.metadata import PackageNotFoundError, version

from SciQLop.components.workspaces import workspaces_manager_instance
from SciQLop.components.plugins.plugin_registry import package_name_from_pip

_GITHUB_REPO = re.compile(r"^(?:gh:|https://github\.com/)([\w.-]+)/([\w.-]+?)(?:\.git)?(@[\w./-]+)?/?$")


def _expand_github(spec: str) -> str:
    """``gh:owner/repo[@ref]`` or a GitHub URL → ``repo @ git+https://github.com/owner/repo[@ref]``.

    simplify: the package name is guessed from the repo name; a repo whose
    distribution is named differently needs the full PEP 508 spec.
    """
    match = _GITHUB_REPO.match(spec.strip())
    if match is None:
        return spec
    owner, repo, ref = match.groups()
    return f"{repo} @ git+https://github.com/{owner}/{repo}{ref or ''}"


def _installed_version(dist_name: str) -> str | None:
    try:
        return version(dist_name)
    except PackageNotFoundError:
        return None


def _hot_load(dist_name: str) -> str | None:
    """Load a freshly installed plugin on the GUI thread; a reason string when the compat gate refused it."""
    from SciQLop.components.appstore.backend import _try_load_plugin
    from SciQLop.user_api.threading import invoke_on_main_thread
    return invoke_on_main_thread(_try_load_plugin, dist_name)


def _activate(dist_names: list[str], before: dict[str, str | None]) -> dict:
    """Hot-load new distributions; an upgraded one is already imported, so it needs a restart instead."""
    changed = [d for d in dist_names if _installed_version(d) not in (None, before[d])]
    refused = {d: _hot_load(d) for d in changed if before[d] is None}
    return {"restart_required": [d for d in changed if before[d] is not None],
            "not_loaded": {d: reason for d, reason in refused.items() if reason}}


def install_packages(*specs: str) -> dict:
    """Install one or more packages into the active workspace and record them.

    Accepts PEP 508 specifiers (e.g. ``"astropy"``, ``"scipy>=1.11"``) and GitHub
    shorthands (``"gh:owner/repo@tag"``). Returns ``{"ok", "installed",
    "already_present", "error", "restart_required", "not_loaded"}``.
    """
    wm = workspaces_manager_instance()
    if wm is None or not getattr(wm, "has_workspace", False):
        return {"ok": False, "installed": [],
                "already_present": [], "error": "no active workspace"}
    specs = [_expand_github(s) for s in specs]
    dist_names = [n for n in map(package_name_from_pip, specs) if n]
    before = {d: _installed_version(d) for d in dist_names}
    result = wm.workspace.add_packages(specs)
    if not result["ok"]:
        return result
    return {**result, **_activate(dist_names, before)}
