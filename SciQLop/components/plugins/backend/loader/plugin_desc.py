from pydantic import BaseModel, Field
from typing import List
import json


class Author(BaseModel):
    name: str
    email: str
    organization: str


class PluginDesc(BaseModel):
    name: str
    version: str
    description: str
    authors: List[Author]
    license: str
    python_dependencies: List[str] = Field(default_factory=list, description="Required python packages")
    dependencies: List[str] = Field(default_factory=list, description="Required plugins")
    disabled: bool = Field(default=False, description="Whether the plugin is disabled by default")

    @staticmethod
    def from_json(path: str) -> "PluginDesc":
        with open(path, "r") as f:
            data = json.load(f)
        return PluginDesc(**data)
