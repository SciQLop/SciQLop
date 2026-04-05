"""Generate a pyproject.toml for a SciQLop workspace virtual environment.

The generated file merges plugin ``python_dependencies`` with workspace
``requires`` from the manifest so that ``uv sync`` can resolve them all
into one coherent environment.
"""

from __future__ import annotations

import importlib.metadata
import os
import re
import sys
from pathlib import Path
from typing import List, Sequence, Union

from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest

# Packages whose version must match the base Python environment exactly.
# These are C extensions or tightly coupled libraries that break if the
# workspace venv installs a different version via transitive dependencies.
_PINNED_BASE_PACKAGES = (
    "PySide6",
    "PySide6-Essentials",
    "PySide6-Addons",
    "PySide6-QtAds",
    "shiboken6",
    "SciQLopPlots",
    "speasy",
    "jupyqt",
    "jupyverse",
    "jupyterlab",
)

# PEP 508 package name: letters, digits, hyphens, underscores, dots.
# We capture the base name (before any extras bracket or version specifier).
_PKG_NAME_RE = re.compile(r"^([A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?)")
_URL_RE = re.compile(r"^(https?://|git\+https?://)")
_GITHUB_REPO_RE = re.compile(r"github\.com/[^/]+/([^/]+)")


def _base_constraints() -> List[str]:
    """Return ``name==version`` pins for base packages present in the running Python."""
    constraints = []
    for pkg in _PINNED_BASE_PACKAGES:
        try:
            version = importlib.metadata.version(pkg)
            constraints.append(f"{pkg}=={version}")
        except importlib.metadata.PackageNotFoundError:
            pass
    return constraints


def _slugify(name: str) -> str:
    """Convert a human-readable name to a URL/package-safe slug.

    >>> _slugify("My Study")
    'my-study'
    """
    slug = name.lower()
    slug = slug.replace("_", "-")
    slug = re.sub(r"[^a-z0-9-]", "-", slug)
    slug = slug.strip("-")
    return slug


def _name_from_wheel_url(url: str) -> str | None:
    """Extract the package name from a wheel filename in a URL."""
    filename = url.split("?")[0].split("#")[0].rsplit("/", 1)[-1]
    if filename.endswith(".whl"):
        return filename.split("-")[0].replace("_", "-").lower()
    return None


def _normalize_url_requirement(req: str) -> str:
    """Convert a raw URL to PEP 508 ``name @ url`` format if possible.

    If *req* is already a valid PEP 508 string or the package name cannot be
    guessed, it is returned unchanged.
    """
    stripped = req.strip()
    if not _URL_RE.match(stripped):
        return stripped
    # For wheel URLs, the filename is the authoritative source for the name
    whl_name = _name_from_wheel_url(stripped)
    if whl_name:
        return f"{whl_name} @ {stripped}"
    m = _GITHUB_REPO_RE.search(stripped)
    if m is None:
        return stripped
    name = m.group(1)
    # Strip common archive suffixes so "spok.git" or "spok/archive/..." → "spok"
    name = re.sub(r"(\.git|/archive/.*)$", "", name)
    return f"{name} @ {stripped}"


def _extract_package_name(req: str) -> str:
    """Return the normalised base package name from a PEP 508 requirement string."""
    m = _PKG_NAME_RE.match(req.strip())
    if m is None:
        return req.strip().lower()
    return m.group(1).lower().replace("_", "-").replace(".", "-")


def _deduplicate_requirements(reqs: Sequence[str]) -> List[str]:
    """De-duplicate requirements by package name, keeping the *last* occurrence."""
    seen: dict[str, int] = {}
    result: list[str] = []
    for req in reqs:
        key = _extract_package_name(req)
        if key in seen:
            # Remove the earlier entry
            result.pop(seen[key])
            # Adjust indices for entries that shifted
            seen = {k: (v if v < seen[key] else v - 1) for k, v in seen.items() if k != key}
        seen[key] = len(result)
        result.append(req)
    return result


def generate_pyproject_toml(
    manifest: WorkspaceManifest,
    plugin_deps: Sequence[str],
    output_path: Union[str, os.PathLike[str]],
) -> None:
    """Write a ``pyproject.toml`` that merges *manifest* requires and *plugin_deps*.

    Parameters
    ----------
    manifest:
        The parsed workspace manifest (must have ``name`` and ``requires``).
    plugin_deps:
        Additional Python dependency strings contributed by plugins.
    output_path:
        Filesystem path where the generated ``pyproject.toml`` will be written.
    """
    # jupyqt/jupyverse/jupyterlab must be installed in the workspace venv (not
    # just inherited from base) so that data files (share/jupyter/lab/) are
    # present under sys.prefix, which is the venv directory at runtime.
    implicit_deps = ["jupyqt", "jupyterlab"]
    raw_deps = [_normalize_url_requirement(r) for r in implicit_deps + list(manifest.requires) + list(plugin_deps)]
    all_deps = _deduplicate_requirements(raw_deps)
    slug = _slugify(manifest.name)

    # Format the dependencies list
    if all_deps:
        deps_lines = "\n".join(f'    "{dep}",' for dep in all_deps)
        deps_block = f"dependencies = [\n{deps_lines}\n]"
    else:
        deps_block = "dependencies = [\n]"

    constraints = _base_constraints()
    if constraints:
        constraint_lines = "\n".join(f'    "{c}",' for c in constraints)
        constraint_block = f"constraint-dependencies = [\n{constraint_lines}\n]"
    else:
        constraint_block = ""

    content = f"""\
# Auto-generated by SciQLop launcher. Do not edit manually.
# Source of truth: workspace.sciqlop manifest

[project]
name = "sciqlop-workspace-{slug}"
version = "0.0.0"
requires-python = ">={sys.version_info.major}.{sys.version_info.minor}"
{deps_block}

[tool.uv]
package = false
{constraint_block}
"""

    Path(output_path).write_text(content)
