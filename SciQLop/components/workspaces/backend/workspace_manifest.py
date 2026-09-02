"""Reader/writer for .sciqlop workspace manifest files (TOML format).

Manifest format::

    [workspace]
    name = "My Magnetosphere Study"
    description = "Studying reconnection events in 2024"
    image = "image.png"

    [plugins]
    add = ["some_extra_plugin"]
    remove = ["experimental_collaboration"]

    [dependencies]
    requires = ["matplotlib>=3.8", "scipy", "hapiclient"]

    [[examples.installed]]
    name = "MMS"
    source = "/path/to/SciQLop/examples/mms"
    version = "1"
"""

from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import tomli_w

from SciQLop.core.common.files import write_text_atomic

log = logging.getLogger(__name__)

LAST_USED_MARKER = ".last_used"


@dataclass
class InstalledExample:
    """Record of an example installed into a workspace."""
    name: str
    source: str
    version: str = ""


@dataclass
class WorkspaceManifest:
    """Dataclass representing a .sciqlop workspace manifest."""

    name: str
    # Which SciQLop the workspace's venv installs. Recorded when the workspace
    # is created so the environment stays reproducible as the launcher moves on;
    # empty means "whatever the launcher currently provides".
    sciqlop_version: str = ""
    description: str = ""
    image: str = ""
    default: bool = False
    plugins_add: list[str] = field(default_factory=list)
    plugins_remove: list[str] = field(default_factory=list)
    requires: list[str] = field(default_factory=list)
    examples: list[InstalledExample] = field(default_factory=list)
    _directory: str = field(default="", repr=False, compare=False, init=False)

    @property
    def directory(self) -> str:
        return self._directory

    @staticmethod
    def touch_last_used(workspace_dir: Path | str) -> None:
        (Path(workspace_dir) / LAST_USED_MARKER).touch()

    @staticmethod
    def last_used(workspace_dir: Path | str) -> str:
        marker = Path(workspace_dir) / LAST_USED_MARKER
        if marker.exists():
            return datetime.fromtimestamp(marker.stat().st_mtime).isoformat()
        return ""

    @staticmethod
    def last_modified(workspace_dir: Path | str) -> str:
        manifest = Path(workspace_dir) / "workspace.sciqlop"
        if manifest.exists():
            return datetime.fromtimestamp(manifest.stat().st_mtime).isoformat()
        return ""

    @classmethod
    def default_manifest(cls, name: str) -> WorkspaceManifest:
        """Create a default manifest with only a name."""
        return cls(name=name)

    @classmethod
    def load(cls, path: Path | str) -> WorkspaceManifest:
        """Load a manifest from a TOML file."""
        path = Path(path)
        with open(path, "rb") as f:
            data = tomllib.load(f)

        workspace = data.get("workspace", {})
        plugins = data.get("plugins", {})
        dependencies = data.get("dependencies", {})
        examples_data = data.get("examples", {})
        installed = [InstalledExample(**e) for e in examples_data.get("installed", [])]

        manifest = cls(
            name=workspace["name"],
            sciqlop_version=workspace.get("sciqlop_version", ""),
            description=workspace.get("description", ""),
            image=workspace.get("image", ""),
            default=workspace.get("default", False),
            plugins_add=plugins.get("add", []),
            plugins_remove=plugins.get("remove", []),
            requires=dependencies.get("requires", []),
            examples=installed,
        )
        manifest._directory = str(path.parent)
        return manifest

    @classmethod
    def load_or_repair(cls, path: Path | str) -> WorkspaceManifest:
        """Load a manifest, self-healing a corrupt file.

        A manifest that fails to parse (bad TOML, or missing the required
        ``name`` key) would otherwise break every future launch. Instead it
        is renamed aside as ``<name>.corrupt`` and replaced with either a
        fresh migration from a sibling ``workspace.json`` (if one exists) or
        a bare default manifest named after the workspace directory.
        """
        path = Path(path)
        try:
            return cls.load(path)
        except (tomllib.TOMLDecodeError, KeyError, UnicodeDecodeError, TypeError) as exc:
            log.warning("Corrupt manifest %s (%s), repairing", path, exc)

        workspace_dir = path.parent
        path.replace(path.with_name(path.name + ".corrupt"))

        from SciQLop.components.workspaces.backend.workspace_migration import migrate_workspace

        if migrate_workspace(workspace_dir):
            return cls.load(path)

        manifest = cls.default_manifest(workspace_dir.name)
        manifest.save(path)
        return manifest

    def save(self, path: Path | str) -> None:
        """Save the manifest to a TOML file."""
        path = Path(path)
        self._directory = str(path.parent)
        data: dict = {
            "workspace": {
                "name": self.name,
                "description": self.description,
            },
        }
        if self.sciqlop_version:
            data["workspace"]["sciqlop_version"] = self.sciqlop_version
        if self.image:
            data["workspace"]["image"] = self.image
        if self.default:
            data["workspace"]["default"] = self.default
        if self.plugins_add or self.plugins_remove:
            plugins: dict = {}
            if self.plugins_add:
                plugins["add"] = self.plugins_add
            if self.plugins_remove:
                plugins["remove"] = self.plugins_remove
            data["plugins"] = plugins

        if self.requires:
            data["dependencies"] = {"requires": self.requires}

        if self.examples:
            data["examples"] = {
                "installed": [{"name": e.name, "source": e.source, "version": e.version}
                              for e in self.examples]
            }

        write_text_atomic(path, tomli_w.dumps(data))
