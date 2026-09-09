from .fixtures import *

STEP_IDS = [
    "welcome", "create_panel", "search_products", "open_products", "plot_product",
    "navigate", "add_more_data", "properties",
    "open_catalogs", "catalog_sources", "overlay_catalog", "edit_events",
    "settings", "finish",
]


def _steps():
    from SciQLop.components.onboarding.backend.getting_started import GETTING_STARTED
    return {s.step_id: s for s in GETTING_STARTED.steps}


def test_getting_started_steps_in_order():
    from SciQLop.components.onboarding.backend.getting_started import GETTING_STARTED
    assert [s.step_id for s in GETTING_STARTED.steps] == STEP_IDS


def test_intro_and_outro_are_centered_tips_without_target():
    by_id = _steps()
    assert by_id["welcome"].resolver is None
    assert by_id["finish"].resolver is None
    for step_id in STEP_IDS[1:-1]:
        assert by_id[step_id].resolver is not None, step_id


def test_action_steps_auto_advance_and_tips_do_not():
    by_id = _steps()
    action_steps = {"create_panel", "search_products", "open_products", "plot_product",
                    "open_catalogs"}
    for step_id, step in by_id.items():
        assert (step.completion is not None) == (step_id in action_steps), step_id


def test_every_body_mentions_what_the_user_can_do(main_window):
    """Each tip is short and names a concrete action or feature."""
    for step in _steps().values():
        words = step.body.split()
        assert 15 <= len(words) <= 60, (step.step_id, len(words))
        assert step.title and step.title[0].isupper()


def test_open_products_tip_matches_the_hover_to_open_side_bar():
    """The dock manager runs with AutoHideShowOnMouseOver: hovering the
    tab opens the dock and a click on an open one closes it, so telling
    the user only to click sends them the wrong way."""
    assert "Hover" in _steps()["open_products"].body


def test_plot_product_resolves_inside_the_products_dock(main_window, qtbot):
    from PySide6.QtWidgets import QTreeView
    dw = main_window.dock_manager.findDockWidget("Products")
    dw.autoHideDockContainer().collapseView(True)
    target = _steps()["plot_product"].resolver(main_window, {})
    widget = target[0] if isinstance(target, tuple) else target
    assert isinstance(widget, QTreeView)
    qtbot.waitUntil(dw.isVisible, timeout=1000)


def test_plot_product_is_skipped_once_the_panel_already_shows_something(main_window):
    """Plotting from the search box at the previous step makes the drag
    step pointless; it must not show up (nor flash) in that case."""
    from PySide6.QtCore import QObject

    class _FakePlot(QObject):
        def __init__(self):
            super().__init__()
            self.setObjectName("Plot")

    plot = _FakePlot()
    panel = type("FakePanel", (), {"plots": lambda self: [plot]})()
    context = {"create_panel": panel}
    assert _steps()["plot_product"].resolver(main_window, context) is None


def test_getting_started_is_registered_once():
    from SciQLop.components.onboarding.backend import registry
    from SciQLop.components.onboarding.backend.getting_started import GETTING_STARTED
    registry.register_builtin_tours()
    registry.register_builtin_tours()
    assert registry.get_tour("getting_started") is GETTING_STARTED
    assert {t.id for t in registry.all_tours()} >= {"getting_started"}


def test_builtin_tour_comes_back_after_a_registry_reset():
    from SciQLop.components.onboarding.backend import registry
    registry._reset_registry_for_tests()
    assert registry.get_tour("getting_started") is None
    registry.register_builtin_tours()
    assert registry.get_tour("getting_started") is not None


def test_side_panel_steps_auto_advance_only_when_the_next_step_continues_inside_that_panel():
    """Hover-open completes a dock step instantly; that is right when the
    next tip lives inside the panel (Products -> drag a product, Catalogs
    -> catalog tree) and wrong when it does not (Properties, Settings):
    the panel opens and the card has already moved on to something else."""
    by_id = _steps()
    assert by_id["open_products"].completion is not None
    assert by_id["open_catalogs"].completion is not None
    assert by_id["properties"].completion is None
    assert by_id["settings"].completion is None


def test_open_panel_steps_skip_themselves_when_their_panel_is_already_open(main_window, qtbot):
    by_id = _steps()
    for step_id, dock_name in (("open_products", "Products"), ("open_catalogs", "Catalogs")):
        dw = main_window.dock_manager.findDockWidget(dock_name)
        dw.toggleView(True)
        qtbot.waitUntil(dw.isVisible, timeout=1000)
        assert by_id[step_id].resolver(main_window, {}) is None, step_id
        dw.autoHideDockContainer().collapseView(True)
        qtbot.waitUntil(lambda: not dw.isVisible(), timeout=1000)
        assert by_id[step_id].resolver(main_window, {}) is dw.sideTabWidget(), step_id
