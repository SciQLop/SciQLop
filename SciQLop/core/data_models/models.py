from dataclasses import dataclass, field
from typing import List
from .serialisation import register_spec_file_readonly, register_spec_file

__all__ = ["ExampleSpec", "ExampleSpecFile", "ExampleSpecROFile"]


@dataclass
class ExampleSpec:
    name: str = field(default_factory=str)
    description: str = field(default_factory=str)
    dependencies: List[str] = field(default_factory=list)
    image: str = field(default_factory=str)
    tags: List[str] = field(default_factory=list)
    notebook: str = field(default_factory=str)
    valid: bool = False


ExampleSpecFile = register_spec_file(ExampleSpec, "example.json")
ExampleSpecROFile = register_spec_file_readonly(ExampleSpec, "example.json")
