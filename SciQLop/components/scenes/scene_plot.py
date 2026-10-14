"""Draw a resolved scene into a three-pane projection plot."""
import functools
import math
import threading
from dataclasses import dataclass

import numpy as np
import shiboken6
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPen
from SciQLopPlots import GraphType, PlotType

from SciQLop.components.plotting.ui.time_sync_panel import _CallbackErrorOverlay
from .model import ResolvedScene
from .summary import PANES, pane_summary

_AXES = "XYZ"
_KIND_COLOURS = {"magnetopause": "#4FC3F7", "bow_shock": "#FFB74D", "mpb": "#BA68C8"}
_DEFAULT_COLOUR = "#B0BEC5"
_CURVE_SUFFIX = {"centre": "", "low": " min", "high": " max"}
_SCENE_PLOTS: dict[int, object] = {}


@dataclass(frozen=True)
class BoundaryCurves:
    graphs: list      # per pane: centre (+ low, high when the scene has an envelope)
    reporters: list   # the graphs' error overlays, deleted with them


# simplify: lru_cache does not cache failures, so during a 3DView outage every curve retries
# on every range change. Upgrade path: a short-lived negative cache keyed like this one.
@functools.lru_cache(maxsize=64)
def _cached_summary(model, frame, pane, start, stop, how):
    return pane_summary(model, frame, pane, start, stop, how)


class _PaneCurve:
    """One curve of one boundary in one pane; the three curves of a pane share one summary.

    They also share one lock, so the second and third wait for the first and hit the cache
    instead of computing it again, while other panes and boundaries compute in parallel."""

    def __init__(self, model, frame: str, pane: int, which: str, how: str, lock: threading.Lock):
        self.model, self.frame, self.pane, self.which, self.how = model, frame, pane, which, how
        self._lock = lock
        self.__name__ = model.label or model.name

    def __call__(self, start, stop):
        with self._lock:
            s = _cached_summary(self.model, self.frame, self.pane, float(start), float(stop), self.how)
        return s.curve(self.which)


def _seeded_projection(panel_impl):
    """simplify: SciQLopMultiPlotPanel.create_plot(Projections) segfaults in SciQLopPlots 0.51.3
    (fixed upstream, unreleased); plot a one-sample curve to get the panes, then drop it.
    Use create_plot once a SciQLopPlots release carries the fix."""
    z = np.zeros(1)
    proj, seed = panel_impl.plot([z, z, z, z], plot_type=PlotType.Projections,
                                 graph_type=GraphType.ParametricCurve, labels=["", "", ""])
    proj.remove_plottable(seed)
    return proj


def _axis_labels(resolved: ResolvedScene) -> list[str]:
    return [f"{axis} {resolved.scene.frame} [{resolved.body.symbol}]" for axis in _AXES]


def _draw_body(proj, resolved: ResolvedScene) -> None:
    a = np.linspace(0, 2 * np.pi, 181)
    for pane in range(len(PANES)):
        proj.subplot(pane).plot(np.cos(a), np.sin(a), graph_type=GraphType.ParametricCurve,
                                labels=[resolved.body.threedview])


def _style(graph, colour: str, dashed: bool) -> None:
    for line in graph.components():
        pen = QPen(QColor(colour), 1.0 if dashed else 2.0)
        pen.setStyle(Qt.PenStyle.DashLine if dashed else Qt.PenStyle.SolidLine)
        line.set_pen(pen)


def _pane_graph(proj, pane: int, curve: _PaneCurve, label: str):
    sub = proj.subplot(pane)
    reporter = _CallbackErrorOverlay(curve)
    graph = sub.plot(reporter, graph_type=GraphType.ParametricCurve, labels=[label])
    graph = graph[1] if isinstance(graph, tuple) else graph
    reporter.attach(sub)
    graph.observe(proj.time_axis())
    rng = proj.time_axis().range()
    if math.isfinite(rng.start()) and math.isfinite(rng.stop()):
        graph.set_range(rng)
    return graph, reporter


def _curve_label(model, which: str) -> str:
    return f"{model.label or model.name}{_CURVE_SUFFIX[which]}"


def _pane_curves(proj, scene, pane: int, model, colour: str) -> list:
    curves = ["centre", "low", "high"] if scene.envelope else ["centre"]
    lock = threading.Lock()
    made = [_pane_graph(proj, pane, _PaneCurve(model, scene.frame, pane, which, scene.summary, lock),
                        _curve_label(model, which)) for which in curves]
    for (graph, _), which in zip(made, curves):
        _style(graph, colour, dashed=which != "centre")
    return made


def add_boundary(proj, resolved: ResolvedScene, kind: str, model) -> BoundaryCurves:
    colour = _KIND_COLOURS.get(kind, _DEFAULT_COLOUR)
    panes = [_pane_curves(proj, resolved.scene, pane, model, colour) for pane in range(len(PANES))]
    return BoundaryCurves(graphs=[[g for g, _ in made] for made in panes],
                          reporters=[r for made in panes for _, r in made])


def remove_boundary(proj, curves: BoundaryCurves) -> None:
    for pane, pane_graphs in enumerate(curves.graphs):
        for g in pane_graphs:
            proj.subplot(pane).remove_plottable(g)
    for reporter in curves.reporters:
        reporter.clear()
        reporter.deleteLater()


def create_scene_plot(panel_impl, resolved: ResolvedScene):
    proj = _seeded_projection(panel_impl)
    proj.set_axis_labels(_axis_labels(resolved))
    _draw_body(proj, resolved)
    return proj


def _key(qobject) -> int:
    return shiboken6.getCppPointer(qobject)[0]


def remember_scene_plot(proj, scene_plot) -> None:
    key = _key(proj)
    _SCENE_PLOTS[key] = scene_plot
    proj.destroyed.connect(lambda *_: _SCENE_PLOTS.pop(key, None))


def scene_plot_for(widget):
    """The ScenePlot showing *widget*: the projection itself or one of its panes; None otherwise."""
    while widget is not None:
        found = _SCENE_PLOTS.get(_key(widget))
        if found is not None:
            return found
        widget = widget.parent()
    return None
