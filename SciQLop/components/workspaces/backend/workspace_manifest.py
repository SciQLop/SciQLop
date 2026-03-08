"""Reader/writer for .sciqlop workspace manifest files (TOML format).

Manifest format::

    [workspace]
    name = "My Magnetosphere Study"
    description = "Studying reconnection events in 2024"

    [plugins]
    add = ["some_extra_plugin"]
    remove = ["experimental_collaboration"]

    [dependencies]
    requires = ["matplotlib>=3.8", "scipy", "hapiclient"]
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class WorkspaceManifest:
    """Dataclass representing a .sciqlop workspace manifest."""

    name: str
    description: str = ""
    plugins_add: list[str] = field(default_factory=list)
    plugins_remove: list[str] = field(default_factory=list)
    requires: list[str] = field(default_factory=list)

    @classmethod
    def default(cls, name: str) -> WorkspaceManifest:
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

        return cls(
            name=workspace["name"],
            description=workspace.get("description", ""),
            plugins_add=plugins.get("add", []),
            plugins_remove=plugins.get("remove", []),
            requires=dependencies.get("requires", []),
        )

    def save(self, path: Path | str) -> None:
        """Save the manifest to a TOML file."""
        path = Path(path)
        data: dict = {
            "workspace": {
                "name": self.name,
                "description": self.description,
            },
        }
        if self.plugins_add or self.plugins_remove:
            plugins: dict = {}
            if self.plugins_add:
                plugins["add"] = self.plugins_add
            if self.plugins_remove:
                plugins["remove"] = self.plugins_remove
            data["plugins"] = plugins

        if self.requires:
            data["dependencies"] = {"requires": self.requires}

        import tomli_w  # lazy import — optional dependency

        with open(path, "wb") as f:
            tomli_w.dump(data, f)
