"""Core contributions of the scenes component: the projection plot kind (and, from Task 2, the scenes drop rules)."""
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


PLOT_KINDS.contribute(PlotKind(PROJECTION, "Scene", plot_product=_plot_scene_item, owns=_owns), owner="sciqlop")


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
