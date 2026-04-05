# SciQLop/user_api/virtual_products/registry.py
"""VP lifecycle: MutableCallback wrapper, registry for hot-reload, registration into product tree."""
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import numpy as np


class MutableCallback:
    def __init__(self, callback: Callable):
        self.callback = callback
        self.after_call: Optional[Callable] = None

    def _update_metadata(self, callback: Callable):
        """Forward signature/annotations so EasyProvider can inspect argument types."""
        import functools
        functools.update_wrapper(self, callback)

    @property
    def callback(self):
        return self._callback

    @callback.setter
    def callback(self, value):
        self._callback = value
        self._update_metadata(value)

    def __call__(self, start, stop):
        import time as _time
        t0 = _time.monotonic()
        result = self._callback(start, stop)
        elapsed = _time.monotonic() - t0
        if self.after_call is not None:
            self.after_call(result, elapsed)
        return result


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


_registry = VPRegistry()


def _invoke_on_main_thread(func, *args, **kwargs):
    """Run func on the Qt main thread, blocking until done."""
    from SciQLop.user_api.threading import invoke_on_main_thread
    return invoke_on_main_thread(func, *args, **kwargs)


def _product_type_to_enum(product_type: str):
    from SciQLop.user_api.virtual_products import VirtualProductType
    return {
        "scalar": VirtualProductType.Scalar,
        "vector": VirtualProductType.Vector,
        "multicomponent": VirtualProductType.MultiComponent,
        "spectrogram": VirtualProductType.Spectrogram,
    }[product_type]


def _infer_multicomponent_labels(cached_data: Any) -> List[str]:
    """Infer default labels from cached evaluation data."""
    try:
        if isinstance(cached_data, (tuple, list)) and len(cached_data) >= 2:
            y = cached_data[1]
            if hasattr(y, 'shape') and y.ndim == 2:
                return [f"C{i}" for i in range(y.shape[1])]
    except Exception:
        pass
    return ["C0"]


def register_virtual_product(name: str, wrapper: MutableCallback, product_type: str,
                              labels: Optional[List[str]], path: Optional[str],
                              cached_data: Any = None):
    """Register a virtual product using the existing create_virtual_product API."""
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType

    vp_path = path or name
    vp_type = _product_type_to_enum(product_type)

    if vp_type == VirtualProductType.Scalar:
        effective_labels = labels or [name]
    elif vp_type == VirtualProductType.Vector:
        effective_labels = labels or ["X", "Y", "Z"]
    elif vp_type == VirtualProductType.MultiComponent:
        effective_labels = labels or _infer_multicomponent_labels(cached_data)
    else:
        effective_labels = None

    def _do_register():
        if vp_type == VirtualProductType.Spectrogram:
            create_virtual_product(vp_path, wrapper, vp_type)
        else:
            create_virtual_product(vp_path, wrapper, vp_type, labels=effective_labels)

    _invoke_on_main_thread(_do_register)
