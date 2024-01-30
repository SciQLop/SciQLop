import os
from dataclasses import dataclass, field
from typing import List

from SciQLop.backend.common.dataclasses import from_json


class Example:
    @dataclass
    class ExampleSpec:
        name: str = field(default_factory=str)
        description: str = field(default_factory=str)
        dependencies: List[str] = field(default_factory=list)
        image: str = field(default_factory=str)
        tags: List[str] = field(default_factory=list)
        notebook: str = field(default_factory=str)
        valid: bool = False

    class ExampleSpecFile:

        def __init__(self, path: str, **kwargs):
            if not path.endswith(".json"):
                path = os.path.join(path, "example.json")
            self._example_spec_path = path
            with open(path, 'r') as f:
                self._spec = from_json(Example.ExampleSpec(), f.read())
            if self.name is None:
                self.valid = False
            else:
                self.valid = True

        @property
        def example_spec_path(self):
            return self._example_spec_path

        def __getattr__(self, item):
            if item.startswith("_") or item in self.__dict__:
                return self.__dict__[item]
            return getattr(self._spec, item)

    def __init__(self, json_file: str):
        print(f"Loading example from {json_file}")
        self._example_spec = Example.ExampleSpecFile(json_file)
        self._json_file = self._example_spec.example_spec_path
        self._path = os.path.dirname(os.path.realpath(self._json_file))

    @property
    def name(self):
        return self._example_spec.name

    @property
    def dependencies(self):
        return self._example_spec.dependencies

    @property
    def description(self):
        return self._example_spec.description

    @property
    def image(self):
        return os.path.join(self._path, self._example_spec.image)

    @property
    def path(self):
        return self._path

    @property
    def json_file(self):
        return self._json_file

    @property
    def tags(self):
        return self._example_spec.tags

    @property
    def is_valid(self):
        return self._example_spec.valid

    @property
    def notebook(self):
        return os.path.join(self._path, self._example_spec.notebook)
