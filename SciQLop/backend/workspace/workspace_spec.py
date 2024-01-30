import json
from datetime import datetime
import os
from typing import List
from dataclasses import dataclass, field
from SciQLop.backend.common.dataclasses import from_json, to_json, from_dict
from SciQLop.backend.common import ensure_dir_exists


@dataclass
class WorkspaceSpec:
    last_used: str = ""
    last_modified: str = ""
    python_path: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    name: str = "default"
    description: str = ""
    image: str = ""
    notebook: str = ""


class WorkspaceSpecFile:

    def __init__(self, path: str, **kwargs):
        if not path.endswith(".json"):
            path = os.path.join(path, "workspace_spec.json")
        self._workspace_spec_path = path
        if not os.path.exists(path):
            self._spec = WorkspaceSpec(**kwargs)
            self._save()
        else:
            with open(path, 'r') as f:
                self._spec = from_json(WorkspaceSpec(), f.read())

    @property
    def workspace_spec_path(self):
        return self._workspace_spec_path

    def _save(self):
        workspace_spec_dir = os.path.dirname(self._workspace_spec_path)
        ensure_dir_exists(workspace_spec_dir)
        self._spec.last_modified = datetime.now().isoformat()
        with open(self._workspace_spec_path, 'w') as f:
            f.write(to_json(self._spec))

    def __getattr__(self, item):
        if item.startswith("_") or item in self.__dict__:
            return self.__dict__[item]
        return getattr(self._spec, item)

    def __setattr__(self, key, value):
        if key.startswith("_") or key in self.__dict__:
            self.__dict__[key] = value
        else:
            setattr(self._spec, key, value)
            self._save()
