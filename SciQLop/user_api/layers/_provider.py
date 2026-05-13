"""LayerProvider — registers annotation layers in the product tree."""
import inspect
from typing import Callable, Optional

from SciQLop.core.unique_names import make_simple_incr_name
from SciQLop.core.models import products, ProductsModelNode, ProductsModelNodeType
from SciQLop.core.enums import ParameterType
from SciQLop.user_api.knobs import extract_specs_from_callback
from SciQLop.user_api.layers.types import infer_type_from_annotation
from SciQLop.components.sciqlop_logging import getLogger as _getLogger

log = _getLogger(__name__)

_LAYERS_ROOT = "Layers"
LAYER_META_KEY = "sciqlop_layer"

_layer_providers: dict[str, "LayerProvider"] = {}


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
            LAYER_META_KEY: "true",
        }
        product_path = self._path[:-1]
        leaf = ProductsModelNode(
            self._path[-1], self.name, metadata,
            ProductsModelNodeType.PARAMETER, ParameterType.Scalar,
        )
        products.add_node(product_path, leaf)

        _layer_providers[self.name] = self

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
