from typing import Generic, TypeVar

T = TypeVar("T")


class NotRegistered(LookupError):
    pass


class Registry(Generic[T]):
    def __init__(self, what: str):
        self._what = what
        self._items: dict[str, T] = {}

    def register(self, item: T, replace: bool = False) -> T:
        if item.name in self._items and not replace:
            raise ValueError(f"{self._what} {item.name!r} is already registered")
        self._items[item.name] = item
        return item

    def get(self, name: str) -> T:
        if name not in self._items:
            raise NotRegistered(f"no {self._what} named {name!r}; available: {', '.join(sorted(self._items))}")
        return self._items[name]

    def list(self, **filters) -> list[T]:
        return [i for i in self._items.values() if all(getattr(i, k, None) == v for k, v in filters.items())]


BODIES: Registry = Registry("body")
BOUNDARIES: Registry = Registry("boundary")
SCENES: Registry = Registry("scene")
