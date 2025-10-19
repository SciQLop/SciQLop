from dataclasses import dataclass, field
from typing import List
from .serialisation import register_spec_file_readonly, register_spec_file

__all__ = ["WorkspaceSpec", "ExampleSpec", "WorkspaceSpecFile", "WorkspaceSpecROFile", "ExampleSpecFile",
           "ExampleSpecROFile"]


@dataclass
class WorkspaceSpec:
    last_used: str = ""
    last_modified: str = ""
    python_path: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    name: str = "default"
    description: str = ""
    image: str = ""
    notebooks: List[str] = field(default_factory=list)
    default_workspace: bool = False


WorkspaceSpecFile = register_spec_file(WorkspaceSpec, "workspace.json")
WorkspaceSpecROFile = register_spec_file_readonly(WorkspaceSpec, "workspace.json")


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
