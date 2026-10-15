"""LayerProvider — annotation layers in the product tree, contributed to sciqlop.layers by path."""
import inspect
from typing import Callable, Optional

from SciQLop.core.unique_names import make_simple_incr_name
from SciQLop.core.extensions import ExtensionPoint, contribute_taking_over, declare
from SciQLop.core.models import add_product_node, remove_product_node, ProductsModelNodeType
from SciQLop.core.enums import ParameterType
from SciQLop.core.product_kinds import LAYER, PRODUCT_KIND_KEY
from SciQLop.user_api.knobs import extract_specs_from_callback
from SciQLop.user_api.layers.registry import MutableCallback, signature_kwargs
from SciQLop.user_api.layers.types import infer_type_from_annotation
from SciQLop.user_api.threading import on_main_thread
from SciQLop.components.sciqlop_logging import getLogger as _getLogger

log = _getLogger(__name__)

_LAYERS_ROOT = "Layers"


class LayerProvider:
    def __init__(self, path: str, callback: Callable,
                 annotation_type: Optional[str] = None, scope: str = "auto"):
        self.name = make_simple_incr_name(getattr(callback, "__name__", "layer"))
        self._path = f"{_LAYERS_ROOT}/{path}".split("/")
        self._callback = callback
        self._knob_specs = extract_specs_from_callback(callback)
        self.annotation_type = annotation_type or self._infer_type()
        self._scope = scope

        metadata = {
            "description": f"Annotation layer: {self.name}",
            "stable_id": f"{_LAYERS_ROOT}/{path}",
            "sciqlop_kind": "layer",
            PRODUCT_KIND_KEY: LAYER,
        }
        product_path = self._path[:-1]
        add_product_node(
            product_path, self._path[-1], self.name, metadata,
            ProductsModelNodeType.PARAMETER, ParameterType.Scalar,
        )

        _contribute_layer(self)

    def _infer_type(self) -> str:
        target = inspect.unwrap(self._callback)
        ann = inspect.get_annotations(target).get("return")
        return infer_type_from_annotation(ann) or "mixed"

    def resolve_scope(self) -> str:
        """Returns 'panel' or 'plot'. Resolves 'auto' from the callback signature:
        data-aware layers default to 'plot' (bound to a specific graph),
        range-only layers default to 'panel' (visible across all plots)."""
        if self._scope in ("panel", "plot"):
            return self._scope
        from SciQLop.user_api.layers._introspection import extract_data_type
        return "plot" if extract_data_type(self._callback) is not None else "panel"

    def get_knobs(self) -> list:
        return list(self._knob_specs)

    def update_callback(self, callback: Callable):
        self._callback = callback
        self._knob_specs = extract_specs_from_callback(callback)

    @property
    def callback(self):
        return self._callback

    @property
    def path(self):
        return self._path


LAYERS = declare(ExtensionPoint(
    "sciqlop.layers", LayerProvider, what="layer", key=lambda p: "/".join(p.path),
    doc="Annotation layers by product-tree path (Layers/...)."))


@on_main_thread
def _contribute_layer(provider: LayerProvider) -> LayerProvider:
    return contribute_taking_over(LAYERS, provider, log)


def _swaps_in_place(existing: LayerProvider, func: Callable) -> bool:
    wrapper = existing.callback
    return isinstance(wrapper, MutableCallback) and signature_kwargs(wrapper.callback) == signature_kwargs(func)


@on_main_thread
def define_layer(path: str, func: Callable, scope: str = "auto") -> LayerProvider:
    """Create the layer at Layers/<path>, or hot-reload the one already there.

    Same knob signature: the body is swapped inside the wrapper, so attached layers run it.
    Other signature: the provider gets a new wrapper; new drops get the new knobs,
    layers already attached keep the old wrapper.
    Either way the layer is contributed again, so the redefiner becomes its owner."""
    key = f"{_LAYERS_ROOT}/{path}"
    if key not in LAYERS:
        return LayerProvider(path, MutableCallback(func), scope=scope)
    existing = LAYERS.get(key)
    existing._scope = scope
    if _swaps_in_place(existing, func):
        existing.callback.callback = func
    else:
        existing.update_callback(MutableCallback(func))
    return _contribute_layer(existing)


def _withdraw_layer(provider: LayerProvider) -> None:
    # simplify: layers already dropped on plots keep rendering after withdrawal; detach them here when a plugin's withdrawal must clear plots too.
    remove_product_node(provider.path)


def follow_layers() -> None:
    """Remove a layer's product-tree node when it leaves sciqlop.layers.

    Main thread only. Marks the signals object it connected, so it is idempotent."""
    if not getattr(LAYERS.signals, "_withdrawal_follows", False):
        LAYERS.signals.removed.connect(_withdraw_layer)
        LAYERS.signals._withdrawal_follows = True
