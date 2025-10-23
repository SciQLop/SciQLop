from pandas.core.arraylike import OpsMixin
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
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
    dependencies: Dict[str, str]
    disabled: bool = Field(default=False)

    @staticmethod
    def from_json(path: str) -> "PluginDesc":
        with open(path, "r") as f:
            data = json.load(f)
        return PluginDesc(**data)
