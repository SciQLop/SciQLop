"""Draw a resolved scene into a three-pane projection plot."""
import functools
import math
import re
import threading
from dataclasses import dataclass

import astropy.units as u
import numpy as np
import shiboken6
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPen
from SciQLopPlots import GraphType, PlotType

from SciQLop.components.plotting.ui.time_sync_panel import _CallbackErrorOverlay
from .frames import FrameError, normalise_frame, rotation
from .model import ResolvedScene
from .summary import PANES, pane_summary

_AXES = "XYZ"
_THREEDVIEW_SAMPLING_S = 600   # 3DView answers at 600 s whatever finer value is asked (measured 2026-10-13)
_EARTH_RADII = {"Re", "R_E", "RE"}
_EARTH_RADIUS = 6371.2 * u.km
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


def _speasy_id(source: str) -> str:
    """The speasy id of *source*; a products-tree path is looked up in ProductsModel (main thread only)."""
    if source.startswith("speasy//"):
        from SciQLopPlots import ProductsModel
        node = ProductsModel.node(source.split("//"))
        if node is None or not node.metadata("speasy_id"):
            raise ValueError(f"{source!r} is not a speasy product")
        return node.metadata("speasy_id")
    return source


def _threedview_frame(source: str, v, requested: str) -> str:
    """speasy falls back to J2000, with only a log warning, when 3DView cannot list its frames.

    simplify: the frame is read back from CATDESC ("position in GSM frame"); switch to a proper
    COORDINATE_SYSTEM attribute once speasy's 3DView variables carry one (speasy#406-style metadata)."""
    found = re.fullmatch(r"position in (\S+) frame", v.meta.get("CATDESC", "").strip())
    if found is None:
        raise FrameError(f"{source!r}: cannot confirm the frame of the 3DView trajectory")
    frame = normalise_frame(found.group(1))
    if frame != requested:
        raise FrameError(f"{source!r}: 3DView answered in {frame} instead of {requested}")
    return frame


def _fetch(source: str, frame: str, start: float, stop: float):
    """The variable (None when the range has no data) and the frame its values are in."""
    import speasy
    start, stop = (np.datetime64(int(s * 1e9), "ns") for s in (start, stop))
    if "/" not in source:
        v = speasy.get_data(f"cdpp3dview/{source}", start, stop, coordinate_frame=frame,
                            sampling=str(_THREEDVIEW_SAMPLING_S))
        return (None, None) if v is None else (v, _threedview_frame(source, v, frame))
    v = speasy.get_data(source, start, stop)
    if v is None:
        return None, None
    if "COORDINATE_SYSTEM" not in v.meta:
        raise FrameError(f"{source!r} has no COORDINATE_SYSTEM: its frame is unknown")
    return v, normalise_frame(v.meta["COORDINATE_SYSTEM"])


def _length_unit(unit: str):
    if unit.strip() in _EARTH_RADII:
        return _EARTH_RADIUS
    try:
        parsed = u.Unit(unit)
    except ValueError:
        parsed = None
    if parsed is None or not parsed.is_equivalent(u.km):
        raise ValueError(f"unit {unit!r} is not a length astropy knows")
    return parsed


def _in_body_radii(v, body) -> np.ndarray:
    name = v.meta.get("FIELDNAM", "the product")
    unit = v.unit or v.meta.get("UNITS")
    if not unit:
        raise ValueError(f"{name} has no unit")
    if v.values.ndim != 2 or v.values.shape[1] < 3:
        raise ValueError(f"{name} is not a position: values of shape {v.values.shape}")
    return (v.values[:, :3] * _length_unit(unit)).to_value(body.radius)


def trajectory_source(source: str, resolved: ResolvedScene):
    """A plot callback giving ``[t, x, y, z]`` of *source* (a 3DView body or a speasy id)
    in the scene's frame and body radii."""
    frame = resolved.scene.frame

    def fetch(start, stop):
        v, data_frame = _fetch(source, frame, float(start), float(stop))
        if v is None:
            return None
        xyz = _in_body_radii(v, resolved.body)   # before rotation: a bad product never downloads matrices
        t = v.time.astype("datetime64[ns]").astype("int64") / 1e9
        xyz = rotation(data_frame, frame, t).apply(xyz)
        return [t] + [np.ascontiguousarray(xyz[:, i]) for i in range(3)]

    fetch.__name__ = source
    return fetch


def add_trajectory(proj, resolved: ResolvedScene, source: str):
    reporter = _CallbackErrorOverlay(trajectory_source(_speasy_id(source), resolved))
    name = source.split("/")[-1]
    graph = proj.plot(reporter, labels=[name] * 3, graph_type=GraphType.ParametricCurve)
    graph = graph[1] if isinstance(graph, tuple) else graph
    reporter.attach(proj)
    proj.set_time_color_enabled(True)
    return graph


def _hold_extent(proj, extent: float) -> None:
    """simplify: SciQLopPlots 0.51.3 rescales a pane on each graph's first data whatever
    auto_scale says, and binds no setter for the axes it rescales, so the protected list is
    emptied directly (this also disables the rescale shortcut on scene panes). Upgrade path:
    a public set_axes_to_rescale or a 'no first-data rescale' option in SciQLopPlots."""
    for pane in range(proj.subplot_count()):
        sub = proj.subplot(pane)
        sub.set_auto_scale(False)
        sub.m_axes_to_rescale = []
        sub.x_axis().set_range(-extent, extent)
        sub.y_axis().set_range(-extent, extent)


def create_scene_plot(panel_impl, resolved: ResolvedScene):
    proj = _seeded_projection(panel_impl)
    proj.set_axis_labels(_axis_labels(resolved))
    _draw_body(proj, resolved)
    if resolved.scene.extent is not None:
        _hold_extent(proj, resolved.scene.extent)
    # The projection squares every pane; per-pane equal aspect would block coupled y-axis signals.
    proj.set_equal_aspect_ratio(True)
    return proj


def _key(qobject) -> int:
    return shiboken6.getCppPointer(qobject)[0]


def remember_scene_plot(proj, scene_plot) -> None:
    key = _key(proj)
    _SCENE_PLOTS[key] = scene_plot
    proj.destroyed.connect(lambda *_: _SCENE_PLOTS.pop(key, None))


def concrete_plot(plot):
    """``panel.plots()`` hands out SciQLopPlotInterfacePtr wrappers; the plot itself is behind ``data()``."""
    data = getattr(plot, "data", None)
    return data() if callable(data) else plot


def scene_plot_for(widget):
    """The ScenePlot showing *widget*: the projection itself or one of its panes; None otherwise."""
    widget = concrete_plot(widget)
    while widget is not None:
        found = _SCENE_PLOTS.get(_key(widget))
        if found is not None:
            return found
        widget = widget.parent()
    return None
