"""Drops on a plot panel go through sciqlop.drop_rules."""
from PySide6.QtCore import QObject, Slot
from SciQLopPlots import PlotDragNDropCallback, ProductsModel

from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.drop_rules import DROP_RULES, rule_for
from SciQLop.core.mime import decode_mime
from SciQLop.core.mime.types import PRODUCT_LIST_MIME_TYPE
from SciQLop.core.plot_kinds import plot_kind_of
from SciQLop.core.product_kinds import product_kind_of

log = getLogger(__name__)


def _kind_id(kind):
    return kind.id if kind is not None else None


def drop_product(plot, product: list[str], panel):
    """Put *product* on *plot* (None: on *panel*) as the drop rules say. Never raises: a refusal or failure
    shows why. Returns what the rule returned."""
    from SciQLop.components.scenes.scene_plot import concrete_plot
    from SciQLop.components.scenes.tree import show_refusal
    node = ProductsModel.node(product)
    if node is None:
        return None
    plot = concrete_plot(plot)
    rule = rule_for(PRODUCT_LIST_MIME_TYPE, _kind_id(product_kind_of(node)), _kind_id(plot_kind_of(plot)))
    if rule is None:
        return None
    try:
        return rule.drop(plot, product, panel)
    except Exception as e:
        log.error(f"drop of {product} failed", exc_info=True)
        show_refusal(plot, panel, f"{product[-1]}: {e}")
        return None


def dispatch_drop(panel, plot, mime_type: str, payload):
    if payload is None:
        return None
    if mime_type == PRODUCT_LIST_MIME_TYPE:
        return [drop_product(plot, product, panel) for product in payload]
    rule = rule_for(mime_type, None, _kind_id(plot_kind_of(plot)))
    return None if rule is None else rule.drop(plot, payload, panel)


class RuleDnDCallback(PlotDragNDropCallback):
    def __init__(self, mime_type: str, creates_plot: bool, parent):
        super().__init__(mime_type, creates_plot, parent)
        self._mime_type = mime_type

    def call(self, plot, mime_data):
        dispatch_drop(self.parent(), plot, self._mime_type, decode_mime(mime_data, [self._mime_type]))


def _creates_plot(mime_type: str) -> bool:
    return any(r.creates_plot for r in DROP_RULES.list(mime_type=mime_type))


def _accept(panel, mime_type: str) -> None:
    """simplify: the placeholder flag is fixed when the MIME type's first callback is made; a rule added later
    with creates_plot=True for an already-accepted MIME type does not change it. Recreate the callback if a
    plugin ever needs that."""
    if mime_type in panel._drop_callbacks:
        return
    callback = RuleDnDCallback(mime_type, _creates_plot(mime_type), panel)
    panel._drop_callbacks[mime_type] = callback
    panel.add_accepted_mime_type(callback)


class _RuleFollower(QObject):
    """Child of the panel: PySide6 drops the connection when it dies with the panel, and it holds no
    reference to the panel beyond the QObject parent (docs/qt-lifetime-patterns.md, pattern 1)."""

    @Slot(object)
    def on_rule_added(self, rule):
        _accept(self.parent(), rule.mime_type)


def accept_drop_rules(panel) -> None:
    """One callback per MIME type with rules, now and whenever a rule for a new MIME type is contributed."""
    panel._drop_callbacks = {}
    for mime_type in sorted({r.mime_type for r in DROP_RULES.list()}):
        _accept(panel, mime_type)
    panel._product_plot_callback = panel._drop_callbacks.get(PRODUCT_LIST_MIME_TYPE)
    DROP_RULES.signals.added.connect(_RuleFollower(panel).on_rule_added)
