"""Core contributions of the scenes component: the projection plot kind (with its template persistence) and the
scenes drop rules."""
from SciQLop.core.drop_rules import DROP_RULES, DropRule
from SciQLop.core.mime.types import PRODUCT_LIST_MIME_TYPE
from SciQLop.core.plot_kinds import PLOT_KINDS, PROJECTION, PlotKind
from SciQLop.core.product_kinds import BOUNDARY, SCENE


def _plot_scene_item(p, product, kwargs):
    """Scenes and models have no data provider: they go where a drop would put them."""
    from SciQLop.components.plotting.ui.time_sync_panel import _owning_time_sync_panel, _resolve_plot_target
    from SciQLop.components.scenes.scene_plot import concrete_plot
    from SciQLop.components.scenes.tree import drop
    target = concrete_plot(_resolve_plot_target(p, kwargs)[0])
    panel = _owning_time_sync_panel(target)
    sp = drop(None if target is panel else target, product, panel)
    return None if sp is None else (sp._get_impl_or_raise(), None)


def _owns(plot) -> bool:
    """Any object may be asked (plot_kind_of tries every kind); only a Qt object can be a scene plot."""
    from SciQLop.components.scenes.scene_plot import scene_plot_for
    try:
        return scene_plot_for(plot) is not None
    except (TypeError, AttributeError):
        return False


def _scene_config(plot) -> dict:
    from SciQLop.components.scenes.scene_plot import scene_plot_for
    sp = scene_plot_for(plot)
    return {"scene": sp.scene.name,
            "boundaries": {kind: model.name for kind, model in sp._resolved.boundaries.items()},
            "trajectories": list(sp._trajectories)}


def _scene_from_config(panel, config: dict):
    """simplify: only registered scenes and boundaries round-trip (by name); an ad-hoc Scene object is saved by
    name and restores as a placeholder. Save full scene definitions if users plot unregistered scenes."""
    from SciQLop.user_api.plot import PlotPanel
    sp = PlotPanel(panel).plot_scene(config["scene"])
    for kind, name in config.get("boundaries", {}).items():
        sp.set_boundary(kind, name)
    for source in config.get("trajectories", []):
        sp.add_trajectory(source)
    return sp


PLOT_KINDS.contribute(PlotKind(PROJECTION, "Scene", plot_product=_plot_scene_item, owns=_owns,
                               to_config=_scene_config, from_config=_scene_from_config), owner="sciqlop")


def _scene_rules():
    from SciQLop.components.scenes import tree
    return (DropRule("sciqlop.scenes.plot_scene", PRODUCT_LIST_MIME_TYPE, tree.plot_scene, product_kind=SCENE,
                     creates_plot=True),
            DropRule("sciqlop.scenes.set_boundary", PRODUCT_LIST_MIME_TYPE, tree.set_boundary,
                     product_kind=BOUNDARY, target=PROJECTION),
            DropRule("sciqlop.scenes.refuse_boundary", PRODUCT_LIST_MIME_TYPE, tree.refuse, product_kind=BOUNDARY),
            DropRule("sciqlop.scenes.add_trajectory", PRODUCT_LIST_MIME_TYPE, tree.add_trajectory,
                     target=PROJECTION))


for _rule in _scene_rules():
    DROP_RULES.contribute(_rule, owner="sciqlop")
