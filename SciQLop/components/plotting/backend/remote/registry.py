"""Registry of out-of-process products: fail-fast pickle validation at
registration, and one worker per plugin."""
from __future__ import annotations

from typing import Dict, Iterable, Optional, Tuple, Union

import cloudpickle

from SciQLop.core.snippets import split_product_path

from .worker_handle import RemoteWorker

_Key = Tuple[str, ...]


def _key(product_path: Union[str, Iterable[str]]) -> _Key:
    """One key for every spelling of a product path: a registered string
    ("a/b", "a//b") and a tree path (["root", "a", "b"] from a drop) agree."""
    return tuple(split_product_path(product_path))


def plugin_key_for(callback) -> str:
    return (getattr(callback, "__module__", "") or "remote").split(".")[0]


class RemoteRegistry:
    def __init__(self):
        self._specs: Dict[_Key, Tuple[bytes, int, str]] = {}   # path -> (blob, arity, plugin_key)
        self._colored: set = set()
        self._workers: Dict[str, RemoteWorker] = {}

    def register(self, path: str, callback, arity: int, colored: bool = False) -> None:
        try:
            blob = cloudpickle.dumps(callback)
        except Exception as e:
            raise ValueError(
                f"product '{path}' is out_of_process but its callback cannot be "
                f"pickled for the worker: {e}"
            ) from e
        self._specs[_key(path)] = (blob, arity, plugin_key_for(callback))
        (self._colored.add if colored else self._colored.discard)(_key(path))

    def is_remote(self, product_path: list) -> bool:
        return _key(product_path) in self._specs

    def is_colored(self, product_path: list) -> bool:
        return _key(product_path) in self._colored

    def spec_for(self, product_path: list) -> Tuple[bytes, int]:
        blob, arity, _ = self._specs[_key(product_path)]
        return blob, arity

    def worker_for(self, product_path: list) -> RemoteWorker:
        _, _, plugin_key = self._specs[_key(product_path)]
        worker = self._workers.get(plugin_key)
        if worker is None or worker._proc is None:
            worker = RemoteWorker(plugin_key=plugin_key)
            worker.start()
            self._workers[plugin_key] = worker
        return worker

    def shutdown_all(self) -> None:
        for w in self._workers.values():
            w.shutdown()
        self._workers.clear()


_REGISTRY: Optional[RemoteRegistry] = None


def remote_registry() -> RemoteRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = RemoteRegistry()
    return _REGISTRY
