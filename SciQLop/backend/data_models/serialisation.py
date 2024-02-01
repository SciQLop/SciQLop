import os
from datetime import datetime
import functools
from ..common import ensure_dir_exists
from ..common.dataclasses import from_json, to_json
from ..sciqlop_logging import getLogger

log = getLogger(__name__)


def _ensure_fname(path, fname) -> str:
    if not path.endswith(".json"):
        return str(os.path.join(path, fname))
    return path


class ReadOnlySpecFile:

    def __init__(self, path: str, spec_class: type, spec_filename: str, **kwargs):
        self._path = _ensure_fname(path, spec_filename)
        assert os.path.exists(path)
        with open(self._path, 'r') as f:
            self._spec = from_json(spec_class(**kwargs), f.read())

    @property
    def path(self):
        return self._path

    @property
    def directory(self):
        return os.path.dirname(os.path.realpath(self._path))

    def __getattr__(self, item):
        if item.startswith("_") or item in self.__dict__:
            return self.__dict__[item]
        return getattr(self._spec, item)


class SpecFile(ReadOnlySpecFile):

    def __init__(self, path: str, spec_class: type, spec_filename: str, **kwargs):
        path = _ensure_fname(path, spec_filename)
        ensure_dir_exists(os.path.dirname(path))
        if not os.path.exists(path):
            with open(path, 'w') as f:
                log.info(f"Saving spec file {path}")
                f.write(to_json(spec_class(**kwargs)))
        super().__init__(path, spec_class=spec_class, spec_filename=spec_filename, **kwargs)

    def _save(self):
        ensure_dir_exists(self.directory)
        if hasattr(self._spec, "last_modified"):
            self._spec.last_modified = datetime.now().isoformat()
        with open(self._path, 'w') as f:
            log.info(f"Saving spec file {self._path}")
            f.write(to_json(self._spec))

    def __setattr__(self, key, value):
        if key.startswith("_") or key in self.__dict__:
            self.__dict__[key] = value
        else:
            setattr(self._spec, key, value)
            self._save()


def register_spec_file_readonly(spec_class: type, spec_filename: str):
    return functools.partial(ReadOnlySpecFile, spec_class=spec_class, spec_filename=spec_filename)


def register_spec_file(spec_class: type, spec_filename: str):
    return functools.partial(SpecFile, spec_class=spec_class, spec_filename=spec_filename)
