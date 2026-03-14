# SciQLop/user_api/virtual_products/magic.py
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional


class MutableCallback:
    def __init__(self, callback: Callable):
        self.callback = callback

    def __call__(self, start, stop):
        return self.callback(start, stop)


@dataclass
class RegistryEntry:
    wrapper: MutableCallback
    product_type: str
    labels: Optional[List[str]]
    signature_changed: bool = False
    panel: object = None  # will hold debug panel ref


class VPRegistry:
    def __init__(self):
        self._entries: Dict[str, RegistryEntry] = {}

    def register(self, name: str, callback: Callable,
                 product_type: str, labels: Optional[List[str]]) -> RegistryEntry:
        existing = self._entries.get(name)
        if existing and existing.product_type == product_type and existing.labels == labels:
            existing.wrapper.callback = callback
            existing.signature_changed = False
            return existing

        wrapper = MutableCallback(callback)
        entry = RegistryEntry(
            wrapper=wrapper,
            product_type=product_type,
            labels=labels,
            signature_changed=existing is not None,
        )
        self._entries[name] = entry
        return entry

    def get(self, name: str) -> Optional[RegistryEntry]:
        return self._entries.get(name)
