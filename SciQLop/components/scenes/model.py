import dataclasses
from dataclasses import dataclass, field
from typing import Literal, Mapping, Optional, Union

import astropy.units as u

from .boundary import Boundary
from .frames import FrameError, frame_centres, normalise_frame
from .registry import BODIES, BOUNDARIES, SCENES


@dataclass(frozen=True)
class Body:
    name: str
    radius: u.Quantity
    threedview: str          # 3DView body name, also the `center` of its frames
    symbol: str              # unit label, e.g. "R_E"


@dataclass(frozen=True)
class Scene:
    name: str
    body: str
    frame: str
    boundaries: Mapping[str, Union[str, Boundary]] = field(default_factory=dict)
    summary: Literal["median", "mean"] = "median"
    envelope: bool = True
    extent: Optional[float] = None   # half-width of the view in body radii; None fits the data

    def with_boundary(self, kind: str, model: Union[str, Boundary]) -> "Scene":
        return dataclasses.replace(self, boundaries={**self.boundaries, kind: model})


@dataclass(frozen=True)
class ResolvedScene:
    scene: Scene
    body: Body
    boundaries: dict[str, Boundary]


def _model(ref) -> Boundary:
    return BOUNDARIES.get(ref) if isinstance(ref, str) else ref


def _check_frame(frame: str, body: Body) -> None:
    centre = frame_centres()[frame]
    if centre != body.threedview:
        raise FrameError(f"{frame} is centred on {centre}, not {body.threedview}")


def _check_body(model: Boundary, body: Body) -> None:
    if model.body != body.name:
        raise ValueError(f"{model.name!r} is a {model.body} model; this is a {body.name} scene")


def resolve(scene: Union[Scene, str]) -> ResolvedScene:
    scene = SCENES.get(scene) if isinstance(scene, str) else scene
    scene = dataclasses.replace(scene, frame=normalise_frame(scene.frame))
    body = BODIES.get(scene.body)
    _check_frame(scene.frame, body)
    models = {kind: _model(ref) for kind, ref in scene.boundaries.items()}
    for model in models.values():
        _check_body(model, body)
    return ResolvedScene(scene, body, models)
