"""Bodies, boundary models and scenes: three extension points keyed by their published names."""
from operator import attrgetter
from typing import TypeVar

from SciQLop.core.extensions import ExtensionPoint, NotRegistered, declare  # noqa: F401  NotRegistered re-exported

T = TypeVar("T")


class Registry(ExtensionPoint[T]):
    """An extension point keyed by `name`, with the published register(item, replace) call."""

    def __init__(self, id: str, what: str):
        # object: Boundary is a non-runtime Protocol, and Body/Scene live in model.py, which imports this module.
        super().__init__(id, object, what=what, key=attrgetter("name"))

    def register(self, item: T, replace: bool = False) -> T:
        if item.name in self._items and not replace:
            raise ValueError(f"{self._what} {item.name!r} is already registered")
        return self.contribute(item, replace=True)


BODIES: Registry = declare(Registry("sciqlop.scenes.bodies", "body"))
BOUNDARIES: Registry = declare(Registry("sciqlop.scenes.boundaries", "boundary"))
SCENES: Registry = declare(Registry("sciqlop.scenes.scenes", "scene"))
