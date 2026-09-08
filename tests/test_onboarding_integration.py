from .fixtures import *


def _open_dock(main_window, name):
    main_window.dock_manager.findDockWidget(name).toggleView(True)


def _at(controller, qtbot, step_id):
    """Wait until `step_id` is shown: the index moves synchronously, the
    step (and its completion hook-up) is entered on the next loop turn."""
    qtbot.waitUntil(lambda: controller._current_step().step_id == step_id, timeout=3000)
    qtbot.waitUntil(controller._coach_mark.isVisible, timeout=3000)


def test_getting_started_walks_end_to_end_headless(main_window, qtbot):
    """Drives the real, registered tour through every step: the two
    action steps completable headlessly (create a panel, open a dock) are
    completed for real, the rest are advanced with Next."""
    from SciQLop.components.onboarding.backend.settings import OnboardingSettings
    from SciQLop.components.onboarding.backend.targets import resolve_add_panel_button
    from SciQLop.components.onboarding.backend.registry import register_builtin_tours
    from SciQLop.components.onboarding.ui.tour_controller import run_tour

    with OnboardingSettings() as s:
        s.completed_tours = {}
    register_builtin_tours()
    controller = run_tour(main_window, "getting_started")
    mark = controller._coach_mark

    def at(step_id):
        _at(controller, qtbot, step_id)

    def next_():
        mark.next_clicked.emit()

    try:
        at("welcome")
        next_()
        at("create_panel")
        resolve_add_panel_button(main_window, {}).click()
        at("search_products")
        next_()
        at("open_products")
        _open_dock(main_window, "Products")
        at("plot_product")
        next_()
        at("navigate")
        next_()
        at("add_more_data")
        next_()
        at("properties")
        next_()
        at("open_catalogs")
        _open_dock(main_window, "Catalog Browser")
        at("catalog_sources")
        next_()
        at("overlay_catalog")
        next_()
        at("edit_events")
        next_()
        at("settings")
        next_()
        at("finish")
        assert mark.bubble._next_button.text() == "Done"
        next_()
        qtbot.waitUntil(lambda: controller.is_finished, timeout=3000)
        assert OnboardingSettings().completed_tours.get("getting_started") is True
    finally:
        if not controller.is_finished:
            controller.abort()
        for name in main_window.plot_panels():
            main_window.remove_panel(main_window.plot_panel(name))


def test_plotting_from_the_search_box_at_step_three_does_not_end_the_tour(main_window, qtbot):
    """Live report: picking a product in the empty panel's search box
    closed the tour as if it were done. Selecting a product deletes the
    search overlay (the spotlighted widget); the tour must carry on."""
    from SciQLop.components.onboarding.backend.settings import OnboardingSettings
    from SciQLop.components.onboarding.backend.targets import resolve_add_panel_button
    from SciQLop.components.onboarding.backend.registry import register_builtin_tours
    from SciQLop.components.onboarding.ui.tour_controller import run_tour

    with OnboardingSettings() as s:
        s.completed_tours = {}
    register_builtin_tours()
    controller = run_tour(main_window, "getting_started")
    mark = controller._coach_mark
    try:
        _at(controller, qtbot, "welcome")
        mark.next_clicked.emit()
        _at(controller, qtbot, "create_panel")
        resolve_add_panel_button(main_window, {}).click()
        _at(controller, qtbot, "search_products")
        panel = controller._context["create_panel"]

        panel._dismiss_search_overlay()  # what plot_product() triggers via plot_added
        qtbot.waitUntil(lambda: mark._target is None, timeout=3000)

        assert controller.is_finished is False
        assert mark.bubble.isVisible()
        assert controller._current_step().step_id == "search_products"
    finally:
        if not controller.is_finished:
            controller.abort()
        for name in main_window.plot_panels():
            main_window.remove_panel(main_window.plot_panel(name))
