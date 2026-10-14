"""Scenes and models in the products tree, and what dropping them does."""
from SciQLopPlots import OverlayLevel, OverlayPosition, OverlaySizeMode

from SciQLop.components.plotting.ui import time_sync_panel
from SciQLop.components.plotting.ui.diagnostic_overlay import overlay_of
from SciQLop.core.enums import ParameterType
from SciQLop.core.models import ProductsModelNodeType, add_product_node
from .registry import BOUNDARIES
from .scene_plot import scene_plot_for

KIND_KEY = "sciqlop_kind"


def show_drop_error(plot, message: str) -> None:
    overlay_of(plot).show_message(message, OverlayLevel.Error, OverlaySizeMode.FitContent, OverlayPosition.Top)


def _boundary_path(model) -> list[str]:
    return ["Models", model.body.capitalize(), model.kind, model.label or model.name]


def _add_node(path: list[str], kind: str, description: str) -> None:
    add_product_node(path[:-1], path[-1], "scenes", {KIND_KEY: kind, "description": description,
                                                     "stable_id": "/".join(path)},
                     ProductsModelNodeType.PARAMETER, ParameterType.Scalar)


def add_scene_node(scene) -> None:
    _add_node(["Scenes", scene.name], "scene", f"{scene.body} scene in {scene.frame}")


def add_boundary_node(model) -> None:
    _add_node(_boundary_path(model), "boundary", f"{model.description} {model.reference}".strip())


def plot_scene(plot, product, panel):
    from SciQLop.user_api.plot import PlotPanel
    PlotPanel(panel).plot_scene(product[-1])


def _without_root(product: list[str]) -> list[str]:
    """Dragged paths start with the tree's invisible "root" node."""
    return product[1:] if product[:1] == ["root"] else product


def _boundary_at(product: list[str]):
    path = _without_root(product)
    found = [m for m in BOUNDARIES.list() if _boundary_path(m) == path]
    if not found:
        raise ValueError("this model is not registered anymore")
    return found[0]


def set_boundary(plot, product, panel):
    model = _boundary_at(product)
    scene_plot_for(plot).set_boundary(model.kind, model)


def add_trajectory(plot, product, panel):
    scene_plot_for(plot).add_trajectory("//".join(_without_root(product)))


def refuse(plot, product, panel):
    show_drop_error(plot, f"{product[-1]} is a model: drop it on a scene plot of its body")


def plot_product(plot, product, panel):
    time_sync_panel.plot_product(plot, product)


def attach_layer(plot, product, panel):
    time_sync_panel.attach_layer(plot, product, panel=panel)


_TABLE = {
    ("scene", False): plot_scene, ("scene", True): plot_scene,
    ("boundary", True): set_boundary, ("boundary", False): refuse,
    ("product", True): add_trajectory, ("product", False): plot_product,
    ("layer", False): attach_layer, ("layer", True): attach_layer,
}


def drop_handler(kind: str, target_is_scene: bool):
    """KeyError for a kind this table does not know: the drop callback shows it on the plot."""
    return _TABLE[(kind, target_is_scene)]
