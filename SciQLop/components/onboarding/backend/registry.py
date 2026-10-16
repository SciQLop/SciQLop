"""Guided tours: the sciqlop.tours extension point (Tier 3 spec §3.2). `register_tour` contributes under the
current owner, so a withdrawn plugin's tours leave with it."""
from SciQLop.components.onboarding.backend.tour import Tour
from SciQLop.core.extensions import ExtensionPoint, current_owner, declare, owned_by
from SciQLop.core.name_follower import CORE_OWNER
from SciQLop.user_api.threading import on_main_thread

TOURS = declare(ExtensionPoint("sciqlop.tours", Tour, what="tour", doc="Guided tours by id."))


def register_tour(tour: Tour) -> None:
    """From any thread; the owner is the caller's, captured before the call moves to the main thread."""
    _contribute_tour(tour, current_owner())


@on_main_thread
def _contribute_tour(tour: Tour, owner: str) -> None:
    TOURS.contribute(tour, owner=owner)


def get_tour(tour_id: str) -> Tour | None:
    return TOURS.find(tour_id)


def all_tours() -> list[Tour]:
    return TOURS.list()


def register_builtin_tours() -> None:
    from SciQLop.components.onboarding.backend.getting_started import GETTING_STARTED
    if get_tour(GETTING_STARTED.id) is None:
        with owned_by(CORE_OWNER):
            register_tour(GETTING_STARTED)


def _forget_tour_for_tests(tour_id: str) -> None:
    if tour_id in TOURS:
        TOURS.remove(tour_id)


def _reset_registry_for_tests() -> None:
    for tour_id in TOURS.keys():
        TOURS.remove(tour_id)
