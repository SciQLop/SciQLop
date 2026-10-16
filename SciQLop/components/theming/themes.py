"""Themes: the sciqlop.themes extension point (Tier 3 spec §4.3). The core themes are the palette files in
SciQLop/resources/palettes, contributed when this module is imported."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Union

import yaml

import SciQLop
from SciQLop.core.extensions import ExtensionPoint, declare, owned_by
from SciQLop.core.name_follower import CORE_OWNER

DEFAULT_THEME = "space"
CORE_THEMES = ("light", "dark", "neutral", "space", "github_light", "nord_light", "catppuccin_latte",
               "high_contrast_light")
palettes_path = os.path.join(SciQLop.sciqlop_root, "resources", "palettes")


@dataclass(frozen=True)
class Theme:
    id: str
    label: str
    palette: Union[dict, Path]  # role -> colour, or a .yaml file holding that mapping

    def __post_init__(self):
        self.colors()

    def colors(self) -> dict[str, str]:
        """A fresh copy of the role -> colour mapping; ValueError when the file is missing or not a mapping."""
        if isinstance(self.palette, dict):
            return dict(self.palette)
        try:
            colors = yaml.safe_load(Path(self.palette).read_text())
        except (OSError, yaml.YAMLError) as e:
            raise ValueError(f"theme {self.id}: cannot read {self.palette}: {e}") from e
        if not isinstance(colors, dict):
            raise ValueError(f"theme {self.id}: {self.palette} is not a mapping of roles to colours")
        return colors


THEMES = declare(ExtensionPoint("sciqlop.themes", Theme, what="theme", doc="Colour themes by id."))

with owned_by(CORE_OWNER):
    for _name in CORE_THEMES:
        THEMES.contribute(Theme(_name, _name, Path(palettes_path) / f"{_name}.yaml"))
