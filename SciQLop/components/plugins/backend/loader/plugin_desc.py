import json
from typing import List

from pydantic import BaseModel, ConfigDict, Field

from SciQLop.components.sciqlop_logging import getLogger

log = getLogger(__name__)

# from_json runs several times per plugin per scan; one warning per file is enough.
_warned: set[str] = set()


class Author(BaseModel):
    name: str
    email: str
    organization: str


class PluginDesc(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    version: str
    description: str = ""
    authors: List[Author] = Field(default_factory=list)
    license: str = ""
    python_dependencies: List[str] = Field(default_factory=list, description="Required python packages")
    dependencies: List[str] = Field(default_factory=list, description="Required plugins, PEP 440 specifiers")
    optional_dependencies: List[str] = Field(default_factory=list, description="Plugins used when present")
    provides: dict[str, List[str]] = Field(default_factory=dict,
                                           description="Extension point id -> contribution ids, for the app store")
    disabled: bool = Field(default=False, description="Whether the plugin is disabled by default")

    @staticmethod
    def from_json(path: str) -> "PluginDesc":
        with open(path, "r") as f:
            desc = PluginDesc(**json.load(f))
        if desc.model_extra and path not in _warned:
            _warned.add(path)
            log.warning("%s: unknown keys ignored: %s", path, ", ".join(sorted(desc.model_extra)))
        return desc
