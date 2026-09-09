"""Pure-Python appstore registry access: fetch, compat-filter, and lookups.

Shared by the interactive App Store page (``components/appstore/backend.py``)
and the launcher's best-effort plugin auto-update on a SciQLop version change
(``components/workspaces/backend/workspace_setup.py``) -- both need the exact
same "which version is compatible" answer, so there is one place that fetches
and filters the registry index. Lives under ``components/plugins`` (not
``components/appstore``, whose package ``__init__`` eagerly imports the
QWebEngine-based store page) so the launcher can import it without pulling in
Qt/WebEngine.
"""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import PurePosixPath
from typing import NamedTuple

import packaging.version

from SciQLop.components.plugins.backend.settings import InstalledPackage, canonical_package_name
from SciQLop.components.plugins.compat import host_satisfies

DEFAULT_STORE_URL = "https://sciqlop.github.io/sciqlop-appstore/index.json"

_PEP440_SPLIT = re.compile(r"[><=!~;@\s]")


def fetch_index(url: str = DEFAULT_STORE_URL) -> list[dict]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def is_compatible(version_entry: dict) -> bool:
    """True if `version_entry["sciqlop"]` is missing/empty or matches our version."""
    return host_satisfies(version_entry.get("sciqlop") or "")


def compatible_versions(plugin: dict) -> list[dict]:
    return [v for v in plugin.get("versions", []) if is_compatible(v)]


def filter_packages(packages: list[dict]) -> list[dict]:
    """Drop incompatible versions, then drop plugins with no compatible version.

    Versions are sorted ascending by parsed version, so the last entry is the
    latest -- the JS client reads `versions[versions.length - 1]` for that.
    """
    out: list[dict] = []
    for pkg in packages:
        compatible = compatible_versions(pkg)
        if not compatible:
            continue
        filtered = dict(pkg)
        filtered["versions"] = sorted(compatible, key=lambda v: packaging.version.parse(v["version"]))
        out.append(filtered)
    return out


def latest_version(plugin: dict) -> dict | None:
    versions = plugin.get("versions", [])
    if not versions:
        return None
    return max(versions, key=lambda v: packaging.version.parse(v["version"]))


def package_name_from_pip(pip_field: str) -> str | None:
    """Extract the distribution name from a pip specifier or wheel URL."""
    pip_field = pip_field.strip()
    if pip_field.startswith("http://") or pip_field.startswith("https://"):
        filename = PurePosixPath(pip_field.split("?")[0].split("#")[0]).name
        if filename.endswith(".whl"):
            return canonical_package_name(filename.split("-")[0])
        return None
    name = _PEP440_SPLIT.split(pip_field, 1)[0].strip()
    return canonical_package_name(name) if name else None


def latest_compatible_pip_spec(dist_name: str, compatible_packages: list[dict]) -> str | None:
    """The latest compatible pip spec for *dist_name*, or ``None`` if it's
    absent from *compatible_packages* (already filtered to compatible
    versions only, see ``filter_packages``)."""
    for pkg in compatible_packages:
        latest = latest_version(pkg)
        if latest and package_name_from_pip(latest["pip"]) == dist_name:
            return latest["pip"]
    return None


def display_name_for_dist(dist_name: str, packages: list[dict]) -> str | None:
    """The registry's human-readable package name for *dist_name*, searched
    across every version of every package (not just the latest), or ``None``
    if *dist_name* isn't in the registry at all."""
    for pkg in packages:
        for version_entry in pkg.get("versions", []):
            if package_name_from_pip(version_entry.get("pip", "")) == dist_name:
                return pkg.get("name")
    return None


class PluginUpdateCheck(NamedTuple):
    """Result of checking installed appstore plugins against the registry.

    ``updates``: canonical dist name -> new pip spec, for plugins whose pin
    should change to stay compatible with the current host (unchanged pins
    are omitted).
    ``unresolvable``: registry display names for plugins the registry knows
    about but has no compatible version for at all -- these need a
    user-visible notice; their existing pin is left untouched.
    """
    updates: dict[str, str]
    unresolvable: list[str]


def resolve_plugin_updates(installed: dict[str, InstalledPackage]) -> PluginUpdateCheck | None:
    """Best-effort: for each installed appstore package, find whether a newer
    SciQLop-compatible version is available, and flag any with none at all.

    Returns ``None`` if the registry can't be reached at all (offline) --
    callers should leave every pin untouched and retry on a later launch,
    same as any other network hiccup. Never raises.

    A dist name absent from the registry entirely (installed some other way,
    or the registry doesn't carry it) is silently skipped in both outputs --
    there's no compatibility data to judge it by, so it's left exactly as
    the plugin loader's own compat gate already handles it.
    """
    try:
        raw_packages = fetch_index()
    except Exception:
        return None
    compatible_packages = filter_packages(raw_packages)

    updates: dict[str, str] = {}
    unresolvable: list[str] = []
    for dist_name, pkg in installed.items():
        spec = latest_compatible_pip_spec(dist_name, compatible_packages)
        if spec is not None:
            if spec != pkg.pip:
                updates[dist_name] = spec
            continue
        display_name = display_name_for_dist(dist_name, raw_packages)
        if display_name is not None:
            unresolvable.append(display_name)
    return PluginUpdateCheck(updates=updates, unresolvable=unresolvable)
