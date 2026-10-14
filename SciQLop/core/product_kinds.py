"""What a product's data looks like: the sciqlop.product_kinds extension point (spec §4.2).

A product kind is a data shape, not a rendering choice: GraphType stays the plot's choice of graph,
and VirtualProductType and the virtual-product type strings keep their published meaning.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from SciQLop.core.enums import ParameterType
from SciQLop.core.extensions import ExtensionPoint, declare

SCALAR, VECTOR, MULTICOMPONENT, SPECTROGRAM = (
    "sciqlop.scalar", "sciqlop.vector", "sciqlop.multicomponent", "sciqlop.spectrogram")
SCENE, BOUNDARY, LAYER = "sciqlop.scenes.scene", "sciqlop.scenes.boundary", "sciqlop.layer"
PRODUCT_KIND_KEY = "product_kind"  # product-tree node metadata; nodes without it are read by parameter type


@dataclass(frozen=True)
class ProductKind:
    id: str
    label: str
    arity: int                     # arrays per fetch: 2 = (time, values), 3 = (time, y, z), 0 = no data stream
    default_plot_kind: str         # a sciqlop.plot_kinds id (plan 1c)
    parameter_type: object = None  # the SciQLopPlots ParameterType a product-tree node of this kind carries


PRODUCT_KINDS = declare(ExtensionPoint("sciqlop.product_kinds", ProductKind, what="product kind",
                                       doc="Data shapes of products: what a fetch returns and how it plots by default."))

_CORE = (
    ProductKind(SCALAR, "Scalar", 2, "sciqlop.timeseries", ParameterType.Scalar),
    ProductKind(VECTOR, "Vector", 2, "sciqlop.timeseries", ParameterType.Vector),
    ProductKind(MULTICOMPONENT, "Multi-component", 2, "sciqlop.timeseries", ParameterType.Multicomponents),
    ProductKind(SPECTROGRAM, "Spectrogram", 3, "sciqlop.timeseries", ParameterType.Spectrogram),
    ProductKind(SCENE, "Scene", 0, "sciqlop.scenes.projection"),
    ProductKind(BOUNDARY, "Boundary model", 0, "sciqlop.scenes.projection"),
    ProductKind(LAYER, "Annotation layer", 0, "sciqlop.timeseries"),
)
# Speasy's nodes, and those of providers written before product kinds, only carry a parameter type.
_BY_PARAMETER_TYPE = {k.parameter_type: k.id for k in _CORE if k.parameter_type is not None}

for _kind in _CORE:
    PRODUCT_KINDS.contribute(_kind, owner="sciqlop")


def kind_id_for(parameter_type) -> Optional[str]:
    return _BY_PARAMETER_TYPE.get(parameter_type)


def product_kind_of(node) -> Optional[ProductKind]:
    """The node's tagged kind, else the kind of its parameter type; None when unknown here (plugin not loaded)."""
    kid = (node.metadata() or {}).get(PRODUCT_KIND_KEY) or kind_id_for(node.parameter_type())
    return PRODUCT_KINDS.get(kid) if kid in PRODUCT_KINDS else None
