"""Scenes and models in the products tree, and what dropping (or plotting) them does."""
import shiboken6
from SciQLopPlots import OverlayLevel, OverlayPosition, OverlaySizeMode, ProductsModel

from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.enums import ParameterType
from SciQLop.core.product_kinds import BOUNDARY, PRODUCT_KIND_KEY, SCENE
from SciQLop.core.models import ProductsModelNodeType, add_product_node
from .model import resolve
from .registry import BOUNDARIES, SCENES
from .scene_plot import scene_plot_for

log = getLogger(__name__)

KIND_KEY = "sciqlop_kind"
_PRODUCT_KINDS = {"scene": SCENE, "boundary": BOUNDARY}
SCENE_KINDS = ("scene", "boundary")
_STATUS_BAR_MS = 8000


def kind_of(product: list[str]):
    """The node's sciqlop_kind ("product" when untagged); None when the path is not in the tree."""
    node = ProductsModel.node(product)
    return None if node is None else node.metadata().get(KIND_KEY, "product")


def _status_bar(panel):
    status_bar = getattr(panel.window(), "statusBar", None)
    return status_bar() if callable(status_bar) else None


def show_refusal(plot, panel, message: str) -> None:
    """On *plot*'s overlay while it lives, else on the status bar of *panel*'s window. Never raises."""
    log.warning(message)
    try:
        if plot is not None and shiboken6.isValid(plot):
            from SciQLop.components.plotting.ui.diagnostic_overlay import overlay_of
            overlay_of(plot).show_message(message, OverlayLevel.Error, OverlaySizeMode.FitContent,
                                          OverlayPosition.Top)
        elif panel is not None and _status_bar(panel) is not None:
            _status_bar(panel).showMessage(message, _STATUS_BAR_MS)
    except Exception:
        log.warning("could not show %r", message, exc_info=True)


def _boundary_path(model) -> list[str]:
    return ["Models", model.body.capitalize(), model.kind, model.label or model.name]


def _add_node(path: list[str], kind: str, description: str) -> None:
    add_product_node(path[:-1], path[-1], "scenes", {KIND_KEY: kind, PRODUCT_KIND_KEY: _PRODUCT_KINDS[kind],
                                                     "description": description, "stable_id": "/".join(path)},
                     ProductsModelNodeType.PARAMETER, ParameterType.Scalar)


def add_scene_node(scene) -> None:
    _add_node(["Scenes", scene.name], "scene", f"{scene.body} scene in {scene.frame}")


def add_boundary_node(model) -> None:
    _add_node(_boundary_path(model), "boundary", f"{model.description} {model.reference}".strip())


def follow_registries() -> None:
    """List every boundary and scene in the products tree as it is contributed, whoever contributes it.

    Main thread only. Marks the signals object it connected, so it is idempotent and reconnects when a test
    swaps in fresh signals."""
    for registry, add_node in ((BOUNDARIES, add_boundary_node), (SCENES, add_scene_node)):
        if not getattr(registry.signals, "_tree_follows", False):
            registry.signals.added.connect(add_node)
            registry.signals._tree_follows = True


def _without_root(product: list[str]) -> list[str]:
    """Dragged paths start with the tree's invisible "root" node."""
    return product[1:] if product[:1] == ["root"] else product


def _boundary_at(product: list[str]):
    path = _without_root(product)
    found = [m for m in BOUNDARIES.list() if _boundary_path(m) == path]
    if not found:
        raise ValueError("this model is not registered anymore")
    return found[0]


def _take_placeholder(plot, panel):
    """Remove the empty plot the panel made for a drop between plots, and give back its index.

    simplify: any empty non-scene plot counts, as SciQLopPlots does not flag its placeholders;
    a user's own empty plot is replaced too. Use a placeholder flag once SciQLopPlots has one."""
    if plot is None or panel is None or scene_plot_for(plot) is not None or plot.plottables():
        return None
    index = panel.index(plot)
    panel.remove_plot(plot)
    return index


def plot_scene(plot, product, panel):
    from SciQLop.user_api.plot import PlotPanel
    resolved = resolve(product[-1])
    slot = _take_placeholder(plot, panel)
    sp = PlotPanel(panel).plot_scene(resolved.scene)
    if slot is not None:
        panel.move_plot(panel.plot_count() - 1, slot)
    return sp


def set_boundary(plot, product, panel):
    model = _boundary_at(product)
    sp = scene_plot_for(plot)
    sp.set_boundary(model.kind, model)
    return sp


def add_trajectory(plot, product, panel):
    scene_plot_for(plot).add_trajectory("//".join(_without_root(product)))


def refuse(plot, product, panel):
    slot = _take_placeholder(plot, panel)
    show_refusal(None if slot is not None else plot, panel,
                 f"{product[-1]} is a model: drop it on a scene plot of its body")


def drop(plot, product: list[str], panel):
    """Put *product* on *plot* (None: on *panel*) as its kind says. Never raises: a refusal or
    failure shows why. Returns the ScenePlot a scene or model went to, else None."""
    from SciQLop.components.plotting.drops import drop_product
    return drop_product(plot, product, panel)
