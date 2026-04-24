"""LayerProvider — registers annotation layers in the product tree."""
from typing import Callable, Optional

from SciQLop.core.unique_names import make_simple_incr_name
from SciQLop.core.enums import ParameterType
from SciQLop.user_api.knobs import extract_specs_from_callback
from SciQLop.user_api.layers.types import infer_type_from_annotation
from SciQLop.components.sciqlop_logging import getLogger as _getLogger

log = _getLogger(__name__)

_LAYERS_ROOT = "Layers"

_layer_providers: dict[str, "LayerProvider"] = {}


class LayerProvider:
    def __init__(self, path: str, callback: Callable, annotation_type: Optional[str] = None):
        from SciQLopPlots import ProductsModel, ProductsModelNode, ProductsModelNodeType

        self.name = make_simple_incr_name(getattr(callback, "__name__", "layer"))
        self._path = f"{_LAYERS_ROOT}/{path}".split("/")
        self._callback = callback
        self._knob_specs = extract_specs_from_callback(callback)
        self.annotation_type = annotation_type or self._infer_type()

        metadata = {
            "description": f"Annotation layer: {self.name}",
            "stable_id": f"{_LAYERS_ROOT}/{path}",
            "sciqlop_layer": "true",
        }
        leaf = ProductsModelNode(
            self._path[-1], self.name, metadata,
            ProductsModelNodeType.PARAMETER, ParameterType.Scalar,
        )
        root = ProductsModelNode(_LAYERS_ROOT)
        node = root
        for part in self._path[1:-1]:
            child = ProductsModelNode(part)
            node.add_child(child)
            node = child
        node.add_child(leaf)
        ProductsModel.instance().add_node([], root)

        _layer_providers[self.name] = self

    def _infer_type(self) -> str:
        ann = self._callback.__annotations__.get("return")
        return infer_type_from_annotation(ann) or "mixed"

    def get_knobs(self) -> list:
        return list(self._knob_specs)

    def refresh_knob_specs(self):
        self._knob_specs = extract_specs_from_callback(self._callback)

    @property
    def callback(self):
        return self._callback

    @property
    def path(self):
        return self._path
