"""Planetary scenes: bodies, boundary models and the scenes that combine them.

Register your own from a plugin's ``activate(ctx)`` (``load(main_window)`` is still supported);
plot one with ``panel.plot_scene(name)``.
"""
import dataclasses

from SciQLop.components.scenes import scene_plot as _scene_plot
from SciQLop.components.scenes.boundary import Boundary, Plane, RadialBoundary
from SciQLop.components.scenes.frames import FrameError
from SciQLop.components.scenes.model import Body, Scene, resolve
from SciQLop.components.scenes.registry import BODIES, BOUNDARIES, SCENES, NotRegistered
from SciQLop.user_api.plot._graphs import Graph, to_plottable
from SciQLop.user_api.plot._plots import ProjectionPlot
from SciQLop.user_api.plot._thread_safety import GuardedImpl
from SciQLop.user_api.threading import on_main_thread

__all__ = ["Body", "Scene", "Plane", "Boundary", "RadialBoundary", "FrameError", "NotRegistered", "ScenePlot",
           "register_body", "register_boundary", "register_scene",
           "list_bodies", "list_boundaries", "list_scenes"]

list_bodies = BODIES.list
list_boundaries = BOUNDARIES.list
list_scenes = SCENES.list


@on_main_thread
def register_body(body: Body, replace: bool = False) -> Body:
    return BODIES.register(body, replace)


@on_main_thread
def register_boundary(model: Boundary, replace: bool = False) -> Boundary:
    """Also lists the model in the products tree, under Models/<Body>/<kind>."""
    return BOUNDARIES.register(model, replace)


@on_main_thread
def register_scene(scene: Scene, replace: bool = False) -> Scene:
    """Also lists the scene in the products tree, under Scenes; drop it on a panel to plot it."""
    return SCENES.register(scene, replace)


class ScenePlot(GuardedImpl):
    """A projection plot showing a scene: its body, boundaries and trajectories, in one frame and unit."""

    def __init__(self, proj, resolved):
        self._impl = proj
        self._resolved = resolved
        self._boundary_graphs = {}
        self._trajectories: list[str] = []
        self._trajectory_curves: list[tuple] = []
        proj.destroyed.connect(self._on_destroyed)
        _scene_plot.remember_scene_plot(proj, self)

    def _on_destroyed(self):
        self._impl = None

    def _get_impl_or_raise(self):
        if self._impl is None:
            raise ValueError("The scene plot does not exist anymore.")
        return self._impl

    @property
    @on_main_thread
    def scene(self) -> Scene:
        return self._resolved.scene

    @property
    @on_main_thread
    def projection(self) -> ProjectionPlot:
        return ProjectionPlot(self._get_impl_or_raise())

    @on_main_thread
    def set_boundary(self, kind: str, model) -> None:
        """Add or swap the boundary of one kind, by registered name or object."""
        proj = self._get_impl_or_raise()
        resolved = resolve(self._resolved.scene.with_boundary(kind, model))
        if kind in self._boundary_graphs:
            _scene_plot.remove_boundary(proj, self._boundary_graphs.pop(kind))
        self._boundary_graphs[kind] = _scene_plot.add_boundary(proj, resolved, kind, resolved.boundaries[kind])
        self._resolved = resolved

    @on_main_thread
    def add_trajectory(self, source: str) -> Graph:
        """Draw a spacecraft orbit in the scene's frame and unit.

        source: a 3DView body name ("MMS1"), a speasy id, or a SciQLop product path ("speasy//...").
        Products must declare COORDINATE_SYSTEM and a position unit; others are refused on the plot."""
        curve = _scene_plot.add_trajectory(self._get_impl_or_raise(), self._resolved, source)
        self._trajectories.append(source)
        self._trajectory_curves.append(curve)
        return to_plottable(curve[0])

    @on_main_thread
    def set_frame(self, frame: str) -> None:
        """Redraw the scene, its boundaries and trajectories in another frame centred on its body
        (e.g. "GSE" or "SM" for an Earth scene); a frame centred elsewhere raises FrameError."""
        proj = self._get_impl_or_raise()
        self._resolved = resolve(dataclasses.replace(self._resolved.scene, frame=frame))
        self._redraw(proj)

    def _redraw(self, proj) -> None:
        for curves in self._boundary_graphs.values():
            _scene_plot.remove_boundary(proj, curves)
        for graph, reporter in self._trajectory_curves:
            _scene_plot.remove_trajectory(proj, graph, reporter)
        _scene_plot.relabel(proj, self._resolved)
        self._boundary_graphs = {kind: _scene_plot.add_boundary(proj, self._resolved, kind, model)
                                 for kind, model in self._resolved.boundaries.items()}
        self._trajectory_curves = [_scene_plot.add_trajectory(proj, self._resolved, source)
                                   for source in self._trajectories]
