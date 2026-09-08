from .fixtures import *
import pytest


@pytest.fixture(autouse=True)
def _forget_fake_plugin_tour():
    yield
    from SciQLop.components.onboarding.backend import registry
    registry._forget_tour_for_tests("fake_plugin_tour")


def test_a_plugin_can_register_a_tour_through_the_public_api(main_window, qtbot):
    """Simulates exactly what an out-of-tree plugin's load(main_window)
    would do: import only the public onboarding surface, build a Tour with
    its own resolver, and register it. No SciQLop core file changes for
    this to work is the entire point of this test."""
    from SciQLop.components.onboarding import Tour, TourStep, register_tour
    from SciQLop.components.onboarding.backend.registry import get_tour, all_tours
    from SciQLop.components.onboarding.ui.tour_controller import run_tour

    def _fake_plugin_widget_resolver(mw, context):
        return mw.dock_manager.findDockWidget("Products").sideTabWidget()

    register_tour(Tour(
        id="fake_plugin_tour",
        title="Fake Plugin Tour",
        description="A tour a fake out-of-tree plugin registered.",
        steps=[TourStep(
            step_id="only_step", title="Fake step", body="Fake body.",
            resolver=_fake_plugin_widget_resolver,
        )],
    ))

    assert get_tour("fake_plugin_tour") is not None
    assert "fake_plugin_tour" in {t.id for t in all_tours()}

    controller = run_tour(main_window, "fake_plugin_tour")
    try:
        qtbot.waitUntil(lambda: controller._coach_mark.isVisible(), timeout=1000)
        assert controller._current_step().step_id == "only_step"
    finally:
        controller.abort()
