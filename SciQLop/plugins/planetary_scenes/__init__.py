"""Built-in planetary scenes: Earth, Mars and Mercury boundary models. `activate` contributes them through the scenes extension points."""
import astropy.units as u

from SciQLop.components.scenes.model import Body, Scene
from SciQLop.components.scenes.registry import BODIES, BOUNDARIES, SCENES

from .models import (Jelinek2012BowShock, Shue1998, Vignes2000BowShock, Vignes2000MPB,
                     Winslow2013BowShock, Winslow2013Magnetopause)

BODIES_DATA = (
    Body("earth", 6371.2 * u.km, "Earth", "R_E"),
    Body("mars", 3389.5 * u.km, "Mars", "R_M"),
    Body("mercury", 2440.0 * u.km, "Mercury", "R_M"),
)
MODELS = (Shue1998(), Jelinek2012BowShock(), Vignes2000BowShock(), Vignes2000MPB(),
          Winslow2013Magnetopause(), Winslow2013BowShock())
SCENES_DATA = (
    Scene("Earth environment", "earth", "GSM", {"magnetopause": "shue1998", "bow_shock": "jelinek2012"},
          extent=30),
    Scene("Mars environment", "mars", "MSO", {"mpb": "vignes2000_mpb", "bow_shock": "vignes2000_bs"},
          extent=4),
    Scene("Mercury environment", "mercury", "MESO",
          {"magnetopause": "winslow2013_mp", "bow_shock": "winslow2013_bs"}, extent=5),
)


def register_all(replace: bool = False) -> None:
    for registry, items in ((BODIES, BODIES_DATA), (BOUNDARIES, MODELS), (SCENES, SCENES_DATA)):
        for item in items:
            registry.register(item, replace)


CONTRIBUTIONS = (("sciqlop.scenes.bodies", BODIES_DATA), ("sciqlop.scenes.boundaries", MODELS),
                 ("sciqlop.scenes.scenes", SCENES_DATA))


def activate(ctx):
    for ep_id, items in CONTRIBUTIONS:
        for item in items:
            ctx.contribute(ep_id, item, replace=True)
