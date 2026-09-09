from .fixtures import *
import pytest


def test_tools_menu_has_take_a_tour_action(main_window):
    actions = [a.text() for a in main_window.toolsMenu.actions()]
    assert "Take a tour…" in actions


def test_maybe_run_onboarding_tour_skips_when_getting_started_completed(main_window, qtbot):
    from SciQLop.components.onboarding.backend.settings import OnboardingSettings

    with OnboardingSettings() as s:
        s.completed_tours = {"getting_started": True}

    main_window._onboarding_controller = None
    main_window._maybe_run_onboarding_tour(None)
    qtbot.wait(200)
    assert main_window._onboarding_controller is None


def test_maybe_run_onboarding_tour_starts_when_not_completed(main_window, qtbot):
    from SciQLop.components.onboarding.backend.settings import OnboardingSettings

    with OnboardingSettings() as s:
        s.completed_tours = {}

    main_window._onboarding_controller = None
    main_window._maybe_run_onboarding_tour(None)
    qtbot.waitUntil(lambda: main_window._onboarding_controller is not None, timeout=1000)
    assert main_window._onboarding_controller._tour.id == "getting_started"
    main_window._onboarding_controller.abort()


def test_starting_a_tour_while_one_runs_restarts_it(main_window, qtbot):
    """Tools -> Take a Tour while a tour is running: the old run is
    aborted and a fresh one starts, never two controllers at once."""
    from SciQLop.components.onboarding.backend.settings import OnboardingSettings

    with OnboardingSettings() as s:
        s.completed_tours = {}

    main_window._onboarding_controller = None
    try:
        main_window._start_tour("getting_started")
        first_controller = main_window._onboarding_controller

        main_window._start_tour("getting_started")
        second_controller = main_window._onboarding_controller

        assert second_controller is not first_controller
        assert first_controller.is_finished
        assert not second_controller.is_finished
    finally:
        if main_window._onboarding_controller is not None:
            main_window._onboarding_controller.abort()


def test_start_tour_with_unknown_id_does_not_crash(main_window):
    main_window._onboarding_controller = None
    main_window._start_tour("no_such_tour")
    assert main_window._onboarding_controller is None


def test_take_a_tour_action_opens_the_picker(main_window):
    action = next(a for a in main_window.toolsMenu.actions() if a.text() == "Take a tour…")
    action.trigger()
    assert main_window._tour_picker.isVisible()
    main_window._tour_picker.close()


def test_opening_the_picker_twice_closes_the_first_one(main_window):
    main_window._open_tour_picker()
    first_picker = main_window._tour_picker

    main_window._open_tour_picker()
    second_picker = main_window._tour_picker

    assert second_picker is not first_picker
    assert second_picker.isVisible()
    assert not first_picker.isVisible()
    second_picker.close()


def test_take_a_tour_quickstart_shortcut_registered(main_window, qapp):
    assert "Take a tour" in qapp.quickstart_shortcuts


def test_take_a_tour_shortcut_opens_the_picker(main_window, qapp):
    shortcut = qapp.quickstart_shortcut("Take a tour")
    shortcut["callback"]()
    assert main_window._tour_picker.isVisible()
    main_window._tour_picker.close()
