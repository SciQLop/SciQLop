import pytest

from SciQLop.core.extensions import owned_by


def _make_step(step_id="step", resolver=None, completion=None, **kwargs):
    from SciQLop.components.onboarding.backend.tour import TourStep
    return TourStep(
        step_id=step_id,
        title=f"{step_id} title",
        body=f"{step_id} body",
        resolver=resolver or (lambda main_window, context: None),
        completion=completion,
        **kwargs,
    )


def _make_tour(tour_id="fake_tour", steps=None):
    from SciQLop.components.onboarding.backend.tour import Tour
    return Tour(
        id=tour_id, title="Fake Tour", description="A fake tour for tests.",
        steps=[_make_step()] if steps is None else steps,
    )


@pytest.fixture(autouse=True)
def _clean_registry():
    from SciQLop.components.onboarding.backend import registry
    yield
    registry._forget_tour_for_tests("fake_tour")
    registry._forget_tour_for_tests("fake_tour_2")


def test_tour_step_is_frozen():
    step = _make_step()
    with pytest.raises(Exception):
        step.title = "changed"


def test_register_tour_then_get_tour_round_trips():
    from SciQLop.components.onboarding.backend import registry
    tour = _make_tour()
    registry.register_tour(tour)
    assert registry.get_tour("fake_tour") is tour


def test_get_tour_returns_none_for_unknown_id():
    from SciQLop.components.onboarding.backend import registry
    assert registry.get_tour("no_such_tour") is None


def test_the_same_owner_registering_a_tour_again_replaces_it():
    from SciQLop.components.onboarding.backend import registry
    registry.register_tour(_make_tour())
    second = _make_tour()
    registry.register_tour(second)
    assert registry.get_tour("fake_tour") is second


def test_another_owner_cannot_take_a_tour_id():
    from SciQLop.components.onboarding.backend import registry
    registry.register_tour(_make_tour())
    with owned_by("tour_thief"), pytest.raises(ValueError, match="already registered"):
        registry.register_tour(_make_tour())


def test_a_withdrawn_plugin_takes_its_tours_away_and_can_register_them_again():
    from SciQLop.components.onboarding.backend import registry
    with owned_by("tour_demo"):
        registry.register_tour(_make_tour())
    assert registry.TOURS.owner_of("fake_tour") == "tour_demo"
    registry.TOURS.remove_owner("tour_demo")
    assert registry.get_tour("fake_tour") is None
    with owned_by("tour_demo"):
        registry.register_tour(_make_tour())
    assert registry.get_tour("fake_tour") is not None


def test_a_tour_without_steps_cannot_be_built():
    with pytest.raises(ValueError, match="no steps"):
        _make_tour(steps=[])


def test_a_tour_registered_from_a_worker_thread_keeps_its_owner(qtbot, monkeypatch):
    from SciQLop.components.onboarding.backend import registry
    from .helpers import call_from_worker_thread

    def register():
        with owned_by("tour_demo"):
            registry.register_tour(_make_tour())

    call_from_worker_thread(qtbot, monkeypatch, register)
    assert registry.TOURS.owner_of("fake_tour") == "tour_demo"


def test_register_tour_rejects_empty_steps():
    from SciQLop.components.onboarding.backend import registry
    with pytest.raises(ValueError, match="no steps"):
        registry.register_tour(_make_tour(steps=[]))


def test_register_tour_rejects_duplicate_step_id():
    from SciQLop.components.onboarding.backend import registry
    with pytest.raises(ValueError, match="duplicate step_id"):
        registry.register_tour(_make_tour(steps=[
            _make_step("dup"), _make_step("dup"),
        ]))


def test_all_tours_reflects_registrations():
    from SciQLop.components.onboarding.backend import registry
    before = {t.id for t in registry.all_tours()}
    registry.register_tour(_make_tour("fake_tour"))
    registry.register_tour(_make_tour("fake_tour_2"))
    after = {t.id for t in registry.all_tours()}
    assert after - before == {"fake_tour", "fake_tour_2"}
