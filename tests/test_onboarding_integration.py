from .fixtures import *


def _open_dock(main_window, name):
    main_window.dock_manager.findDockWidget(name).toggleView(True)


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
        qtbot.waitUntil(lambda: controller._current_step().step_id == step_id, timeout=3000)
        qtbot.waitUntil(mark.isVisible, timeout=3000)

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
