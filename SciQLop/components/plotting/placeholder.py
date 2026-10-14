"""A plot that stands in for one whose kind is not available; it keeps its node so saving again loses nothing."""
import shiboken6
from SciQLopPlots import OverlayLevel, OverlayPosition, OverlaySizeMode, PlotType

from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.plot_kinds import plugin_of

log = getLogger(__name__)
_KEPT: dict = {}


def _key(plot) -> int:
    return shiboken6.getCppPointer(plot)[0]


def _message(model, reason: str) -> str:
    why = f": {reason}" if reason else f" (plugin {plugin_of(model.kind)!r} is not installed or not enabled)"
    return f"This {model.kind} plot cannot be shown{why}. Install or enable the plugin, then reopen the template."


def add_placeholder(panel, model, reason: str = ""):
    """simplify: names the plugin from the kind's id prefix; look it up in the app-store index by `provides`
    once that index carries it (sciqlop-appstore generator)."""
    from SciQLop.components.plotting.ui.diagnostic_overlay import overlay_of
    from SciQLop.components.scenes.scene_plot import concrete_plot
    panel.create_plot(len(panel.plots()), PlotType.TimeSeries)
    plot = concrete_plot(panel.plots()[-1])
    key = _key(plot)
    _KEPT[key] = model
    plot.destroyed.connect(lambda *_: _KEPT.pop(key, None))
    message = _message(model, reason)
    log.warning(message)
    overlay_of(plot).show_message(message, OverlayLevel.Warning, OverlaySizeMode.FitContent, OverlayPosition.Top)
    return plot


def placeholder_model(plot):
    try:
        return _KEPT.get(_key(plot))
    except Exception:
        return None
