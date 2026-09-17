"""sciqlop_build_panel: declarative, all-or-nothing panel construction.

A thin mapping onto the shared panel IR (PanelTemplate, in
components/plotting/panel_template.py) that every exporter/importer already
uses — this is not another walker over Qt objects.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, field_validator

from SciQLop.components.plotting.panel_template import (
    AxisModel, PanelTemplate, PlotModel, ProductModel, TimeRangeModel, resolve_product_path,
)


class _BuildPlotSpec(BaseModel):
    products: List[str]
    y_log: bool = False

    @field_validator("products")
    @classmethod
    def _non_empty_products(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("each plot needs at least one product")
        return v


class BuildPanelSpec(BaseModel):
    time_range: Optional[TimeRangeModel] = None
    plots: List[_BuildPlotSpec]

    @field_validator("plots")
    @classmethod
    def _non_empty_plots(cls, v: List[_BuildPlotSpec]) -> List[_BuildPlotSpec]:
        if not v:
            raise ValueError("plots must contain at least one subplot")
        return v


def parse_spec(payload: Dict[str, Any]) -> BuildPanelSpec:
    return BuildPanelSpec.model_validate(payload)


def unknown_product_paths(spec: BuildPanelSpec) -> List[str]:
    """Every product path in *spec* that does not resolve to a node in the
    live products tree, in spec order. Checking this before touching the GUI
    is what lets sciqlop_build_panel create nothing on a bad path — apply()
    itself only logs a warning and skips."""
    from SciQLopPlots import ProductsModel
    pm = ProductsModel.instance()
    return [
        path
        for plot in spec.plots
        for path in plot.products
        if pm.node(resolve_product_path(path)) is None
    ]


def template_from_spec(spec: BuildPanelSpec) -> PanelTemplate:
    return PanelTemplate(
        name="",  # apply() doesn't read the template's name; the real panel gets its own
        time_range=spec.time_range,
        plots=[
            PlotModel(
                products=[ProductModel(path=path) for path in plot.products],
                y_axis=AxisModel(log=plot.y_log),
            )
            for plot in spec.plots
        ],
    )
