import os

from SciQLop.backend.data_models.models import ExampleSpecROFile
from SciQLop.backend import sciqlop_logging

log = sciqlop_logging.getLogger(__name__)

class Example:

    def __init__(self, json_file: str):
        log.info(f"Loading example from {json_file}")
        self._example_spec = ExampleSpecROFile(json_file)

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
        return os.path.join(self._example_spec.directory, self._example_spec.image)

    @property
    def directory(self):
        return self._example_spec.directory

    @property
    def json_file(self):
        return self._example_spec.path

    @property
    def tags(self):
        return self._example_spec.tags

    @property
    def is_valid(self):
        return self._example_spec.valid

    @property
    def notebook(self):
        return os.path.join(self._example_spec.directory, self._example_spec.notebook)
