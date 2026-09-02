"""Generate a pyproject.toml for a SciQLop workspace virtual environment.

The generated file merges plugin ``python_dependencies`` with workspace
``requires`` from the manifest so that ``uv sync`` can resolve them all
into one coherent environment.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import logging
import os
import re
import sys
from pathlib import Path
from typing import List, Sequence, Union

from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest
from SciQLop.core.common.files import write_text_atomic

log = logging.getLogger(__name__)

# Packages whose version must match the base Python environment exactly.
# These are C extensions or tightly coupled libraries that break if the
# workspace venv installs a different version via transitive dependencies.
#
# ``ipython`` is here because jupyqt drives ``InteractiveShell`` internals:
# IPython 9.16 turned ``run_cell_async(transformed_cell=None)`` into a hard
# TypeError, which kills the jupyverse kernel module on the first execute and
# surfaces as "connection to the Jupyter server could not be established".
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
    "ipython",
)

# Where a dev (`.dev`) build's workspace venv gets SciQLop from: there is no
# such thing as a released `.dev` version, so a bare "sciqlop[all]" would
# resolve the latest actual release from PyPI instead — silently testing the
# installer against old code. Installing from the tip of main instead lets a
# pre-release build exercise the workspace/install flow against the code it
# was actually built from.
_DEV_BUILD_REQUIREMENT = "sciqlop[all] @ git+https://github.com/SciQLop/SciQLop.git@main"

# Distribution-name prefixes of the embedded Jupyter server stack. jupyqt is
# pinned to the host version, so the fps/jupyverse release train it drives must
# be pinned with it — these ship as one coordinated set and a workspace venv
# that re-resolves only part of it gets a kernel that cannot start.
_PINNED_BASE_TRAINS = ("fps", "jupyverse")

# Packages that the workspace venv inherits from the host SciQLop install
# (via --system-site-packages) and must never appear in the workspace
# dependency list, because the dev cycle uses .dev versions that don't
# exist on PyPI and would make uv sync unsatisfiable. Plugins that declare
# these in their python_dependencies are over-specifying — the host
# install is always the source of truth.
_HOST_PROVIDED_PACKAGES = frozenset({"sciqlop"})

# PEP 508 package name: letters, digits, hyphens, underscores, dots.
# We capture the base name (before any extras bracket or version specifier).
_PKG_NAME_RE = re.compile(r"^([A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?)")
_URL_RE = re.compile(r"^(https?://|git\+https?://)")
_GITHUB_REPO_RE = re.compile(r"github\.com/[^/]+/([^/]+)")


def _canonical(name: str) -> str:
    """Return the PEP 503 canonical form of a distribution name."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _installed_train_packages() -> List[str]:
    """Return installed distributions belonging to a pinned release train."""
    found = {}
    for dist in importlib.metadata.distributions():
        name = dist.metadata["Name"]
        if not name:
            continue
        canonical = _canonical(name)
        if canonical.split("-")[0] in _PINNED_BASE_TRAINS:
            found[canonical] = name
    return sorted(found.values())


def _base_constraints() -> List[str]:
    """Return ``name==version`` pins for base packages present in the running Python."""
    constraints = []
    seen = set()
    for pkg in list(_PINNED_BASE_PACKAGES) + _installed_train_packages():
        canonical = _canonical(pkg)
        if canonical in seen:
            continue
        try:
            version = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            continue
        seen.add(canonical)
        constraints.append(f"{pkg}=={version}")
    return constraints


def host_provided_overrides() -> List[str]:
    """Return ``override-dependencies`` entries that neutralise host-provided packages.

    A requirement carrying an always-false environment marker is dropped from
    resolution entirely. We use it to remove *transitive* ``SciQLop`` requirements
    that plugin wheels declare (``Requires-Dist: SciQLop>=X``): the host install
    provides SciQLop through ``--system-site-packages``, and dev-cycle ``.dev``
    versions don't exist on PyPI, so letting uv resolve them pulls a mismatched
    SciQLop (plus its whole pyside6/speasy/shiboken6 stack) into the venv — which
    either shadows the host binaries or makes resolution unsatisfiable.

    Stripping direct deps (``_HOST_PROVIDED_PACKAGES`` above) only covers
    manifest/plugin declarations, not the transitive wheel requirements; this
    override closes that gap and is shared with the appstore install path.
    """
    return [f"{pkg} ; python_version < '0'" for pkg in sorted(_HOST_PROVIDED_PACKAGES)]


def running_sciqlop_version() -> str:
    """Version of the SciQLop the launcher itself came from, or ""."""
    try:
        return importlib.metadata.version("SciQLop")
    except importlib.metadata.PackageNotFoundError:
        return ""


def sciqlop_requirement(pinned_version: str = "") -> str:
    """The workspace's SciQLop dependency.

    ``[all]`` because the bare package is only the launcher — a workspace venv
    that installed it would have nothing to run.

    A development version installs from the tip of ``main`` instead of being
    pinned: ``0.13.0.dev0`` does not exist on PyPI, and leaving it unpinned
    would silently resolve the latest *released* version, which defeats using
    a dev build to test the installer/workspace flow ahead of a release.
    Released versions pin exactly, which is what makes a workspace
    reproducible.
    """
    version = pinned_version or running_sciqlop_version()
    if not version or ".dev" in version:
        return _DEV_BUILD_REQUIREMENT
    return f"sciqlop[all]=={version}"


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


def _project_slug(name: str) -> str:
    """Slug used in the generated PEP 508 project name; never empty.

    `_slugify` only keeps a-z0-9-, so a name that is entirely non-ASCII
    (CJK, Cyrillic, ...) strips to "", producing the invalid project name
    "sciqlop-workspace-" that uv rejects outright. Fall back to a short
    hash of the original name so the workspace can still start.
    """
    slug = _slugify(name)
    if slug:
        return slug
    return "ws-" + hashlib.sha1(name.encode()).hexdigest()[:8]


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


def strip_host_provided(reqs: Sequence[str]) -> List[str]:
    """Drop requirements for packages the running SciQLop install provides.

    The workspace venv inherits them via ``--system-site-packages``. Re-resolving
    them from an index is both wrong (it would shadow the running host package)
    and broken for dev builds: a ``0.13.0.dev0`` host does not satisfy a plugin's
    ``SciQLop>=0.13.0`` under PEP 440, so uv falls back to PyPI — which only has
    ``<=0.12.0`` — and the whole install fails. See _HOST_PROVIDED_PACKAGES.
    """
    kept: list[str] = []
    for r in reqs:
        if _extract_package_name(r) in _HOST_PROVIDED_PACKAGES:
            log.warning(
                "Dropping host-provided requirement %r (provided by the "
                "SciQLop install)", r)
            continue
        kept.append(r)
    return kept


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
    # jupyqt must be installed in the workspace venv (not just inherited from
    # base) so that the lab data files (share/jupyter/lab/) are present under
    # sys.prefix, which is the venv directory at runtime. jupyqt provides them
    # via jupyverse → fps-jupyterlab → jupyterlab-js. Do NOT add the real
    # "jupyterlab" here: it ships the exact same data file paths, and uv's
    # RECORD-based uninstall (no refcounting) means removing or upgrading
    # either package guts the other's files (see lab_assets.repair_lab_assets,
    # which heals venvs already damaged in the field).
    implicit_deps = [sciqlop_requirement(manifest.sciqlop_version), "jupyqt"]
    raw_deps = [_normalize_url_requirement(r) for r in implicit_deps + list(manifest.requires) + list(plugin_deps)]
    all_deps = _deduplicate_requirements(raw_deps)
    slug = _project_slug(manifest.name)

    # Format the dependencies list
    if all_deps:
        deps_lines = "\n".join(f'    "{dep}",' for dep in all_deps)
        deps_block = f"dependencies = [\n{deps_lines}\n]"
    else:
        deps_block = "dependencies = [\n]"

    # No constraint or override blocks: the workspace owns its whole stack now,
    # so there is no host environment to pin against or to hide SciQLop from.
    constraint_block = ""
    override_block = ""

    # Restrict uv resolution to platforms SciQLop actually targets so that
    # marker splits like sys_platform == 'emscripten' (which has no wheels for
    # SciQLop or many native deps) don't break workspace dependency sync.
    environments_block = (
        "environments = [\n"
        "    \"sys_platform == 'linux'\",\n"
        "    \"sys_platform == 'darwin'\",\n"
        "    \"sys_platform == 'win32'\",\n"
        "]"
    )

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
{environments_block}
{override_block}
{constraint_block}
"""

    # Idempotent write: only touch the file when the content actually
    # changes, so its mtime can be used downstream to detect stale lockfiles.
    output = Path(output_path)
    if not output.exists() or output.read_text() != content:
        write_text_atomic(output, content)
