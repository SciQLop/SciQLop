"""Planetary scenes: bodies, boundary models and the scenes that combine them.

Register your own from a plugin's ``load(main_window)``; plot one with ``panel.plot_scene(name)``.
"""
from SciQLop.components.scenes.boundary import Boundary, Plane, RadialBoundary
from SciQLop.components.scenes.frames import FrameError
from SciQLop.components.scenes.model import Body, Scene
from SciQLop.components.scenes.registry import BODIES, BOUNDARIES, SCENES, NotRegistered
from SciQLop.user_api.threading import on_main_thread

__all__ = ["Body", "Scene", "Plane", "Boundary", "RadialBoundary", "FrameError", "NotRegistered",
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
    return BOUNDARIES.register(model, replace)


@on_main_thread
def register_scene(scene: Scene, replace: bool = False) -> Scene:
    return SCENES.register(scene, replace)
