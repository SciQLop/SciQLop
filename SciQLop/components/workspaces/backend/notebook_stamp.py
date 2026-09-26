"""Record in each notebook the SciQLop version and packages it was written with.

The stamp lives in the notebook metadata under ``sciqlop``, shaped like PEP 723
inline script metadata (https://peps.python.org/pep-0723/) so other tools can
read it too::

    "metadata": {"sciqlop": {"version": "0.13.0", "dependencies": ["scipy==1.14.1"]}}

Local packages (paths, ``file:`` URLs, editable installs) are left out: they
cannot be installed on another machine, and would leak local paths.
"""
from __future__ import annotations

import importlib.metadata
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from packaging.requirements import InvalidRequirement, Requirement
from packaging.version import InvalidVersion, Version
from pydantic import BaseModel, ValidationError

from .workspace_manifest import WorkspaceManifest
from .workspace_project import running_sciqlop_version, strip_host_provided

STAMP_KEY = "sciqlop"

InstalledVersion = Callable[[str], Optional[str]]

_LOCAL_SPEC = re.compile(r"^(\.|/|~|-e\b|file:|[A-Za-z]:[\\/])")


class NotebookStamp(BaseModel):
    version: str
    dependencies: list[str]


@dataclass(frozen=True)
class EnvironmentGap:
    """What the running SciQLop lacks to reproduce a stamped notebook."""
    stamp: NotebookStamp
    running: str
    missing: list[str]
    needs_newer_sciqlop: bool


def installed_version(name: str) -> Optional[str]:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _parse(spec: str) -> Optional[Requirement]:
    try:
        return Requirement(spec)
    except InvalidRequirement:
        return None


def _is_local(spec: str) -> bool:
    requirement = _parse(spec)
    if requirement is not None and requirement.url:
        return requirement.url.startswith("file:")
    return bool(_LOCAL_SPEC.match(spec.strip()))


def _pin(spec: str, installed: InstalledVersion) -> str:
    requirement = _parse(spec)
    if requirement is None or requirement.url:
        return spec
    version = installed(requirement.name)
    if version is None:
        return spec
    extras = f"[{','.join(sorted(requirement.extras))}]" if requirement.extras else ""
    marker = f"; {requirement.marker}" if requirement.marker else ""
    return f"{requirement.name}{extras}=={version}{marker}"


def build_stamp(sciqlop_version: str, requirements: list[str],
                installed: InstalledVersion) -> NotebookStamp:
    shareable = [spec for spec in strip_host_provided(requirements) if not _is_local(spec)]
    return NotebookStamp(version=sciqlop_version,
                         dependencies=[_pin(spec, installed) for spec in shareable])


def stamp_notebook(notebook: dict, stamp: NotebookStamp) -> dict:
    metadata = {**notebook.get("metadata", {}), STAMP_KEY: stamp.model_dump()}
    return {**notebook, "metadata": metadata}


def read_stamp(notebook: dict) -> Optional[NotebookStamp]:
    raw = notebook.get("metadata", {}).get(STAMP_KEY)
    if raw is None:
        return None
    try:
        return NotebookStamp.model_validate(raw)
    except ValidationError:
        return None


def _is_satisfied(spec: str, installed: InstalledVersion, current_requirements: list[str]) -> bool:
    requirement = _parse(spec)
    if requirement is None:
        return spec in current_requirements
    if requirement.marker and not requirement.marker.evaluate():
        return True
    version = installed(requirement.name)
    if version is None:
        return False
    pinned = _exact_pin(requirement)
    if pinned is not None:
        return not _is_newer(pinned, version)
    return requirement.specifier.contains(version, prereleases=True)


def _exact_pin(requirement: Requirement) -> Optional[str]:
    """The version of a lone ``==`` pin, which stamps write. A newer installed
    version satisfies it: flagging it would offer to downgrade a working package."""
    specifiers = list(requirement.specifier)
    if len(specifiers) == 1 and specifiers[0].operator == "==" and "*" not in specifiers[0].version:
        return specifiers[0].version
    return None


def _is_newer(made_with: str, running: str) -> bool:
    try:
        return Version(made_with) > Version(running)
    except InvalidVersion:
        return False


def environment_gap(stamp: NotebookStamp, running: str, installed: InstalledVersion,
                    current_requirements: list[str]) -> Optional[EnvironmentGap]:
    """None when this SciQLop can run the notebook as it was written.

    An older notebook on a newer SciQLop is not a gap: flagging it would
    prompt on every notebook after each upgrade.
    """
    missing = [spec for spec in stamp.dependencies
               if not _is_satisfied(spec, installed, current_requirements)]
    needs_newer = _is_newer(stamp.version, running)
    if not missing and not needs_newer:
        return None
    return EnvironmentGap(stamp=stamp, running=running, missing=missing,
                          needs_newer_sciqlop=needs_newer)


def workspace_requirements(workspace_dir: str) -> list[str]:
    """Packages the workspace declares, plus the app-store plugins it installs."""
    from SciQLop.components.plugins.backend.settings import SciQLopPluginsSettings
    manifest = WorkspaceManifest.load(Path(workspace_dir) / "workspace.sciqlop")
    appstore = [package.pip for package in SciQLopPluginsSettings().installed_packages.values()]
    return list(manifest.requires) + appstore


def current_stamp(workspace_dir: str) -> NotebookStamp:
    return build_stamp(running_sciqlop_version(), workspace_requirements(workspace_dir),
                       installed_version)
