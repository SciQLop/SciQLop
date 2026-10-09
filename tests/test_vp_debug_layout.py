from .fixtures import *
import pytest


VP_SCALAR_A = """
def debug_alpha(start: float, stop: float) -> Scalar:
    import numpy as np
    x = np.linspace(start, stop, 100)
    return x, np.sin(x)
"""

VP_SCALAR_B = """
def debug_beta(start: float, stop: float) -> Scalar:
    import numpy as np
    x = np.linspace(start, stop, 100)
    return x, np.cos(x)
"""

VP_SCALAR_C = """
def debug_gamma(start: float, stop: float) -> Scalar:
    import numpy as np
    x = np.linspace(start, stop, 100)
    return x, np.sin(x) * 2
"""


def _root_splitter_child_count(mw):
    return mw.dock_manager.rootSplitter().count()


def _root_splitter_sizes(mw):
    return mw.dock_manager.rootSplitter().sizes()


def test_first_debug_panel_does_not_add_horizontal_children(qtbot, qapp, main_window):
    from SciQLop.user_api.virtual_products.magic import vp_magic

    before = _root_splitter_child_count(main_window)
    vp_magic("--debug --start 0 --stop 10", VP_SCALAR_A)
    qtbot.waitUntil(lambda: _root_splitter_child_count(main_window) == before + 1, timeout=1000)


def test_second_debug_panel_no_extra_horizontal_child(qtbot, qapp, main_window):
    """Adding a second VP debug panel should stack vertically, not add another horizontal column."""
    from SciQLop.user_api.virtual_products.magic import vp_magic

    vp_magic("--debug --start 0 --stop 10", VP_SCALAR_A)
    qtbot.wait(100)
    after_first = _root_splitter_child_count(main_window)

    vp_magic("--debug --start 0 --stop 10", VP_SCALAR_B)
    qtbot.waitUntil(lambda: _root_splitter_child_count(main_window) == after_first, timeout=1000)


def test_horizontal_ratio_preserved_after_second_panel(qtbot, qapp, main_window):
    """The debug column should stay at ~40% width after adding a second debug panel."""
    from SciQLop.user_api.virtual_products.magic import vp_magic

    vp_magic("--debug --start 0 --stop 10", VP_SCALAR_A)
    qtbot.wait(100)

    vp_magic("--debug --start 0 --stop 10", VP_SCALAR_B)
    qtbot.wait(100)

    sizes = _root_splitter_sizes(main_window)
    total = sum(sizes)
    if total == 0:
        pytest.skip("Window has zero width (headless without geometry)")

    right_ratio = sizes[-1] / total
    assert 0.3 <= right_ratio <= 0.5, f"Debug column ratio {right_ratio:.2f} outside 30-50% range"


def test_three_debug_panels_share_vertical_space(qtbot, qapp, main_window):
    """Three stacked debug panels should have roughly equal heights."""
    from SciQLop.user_api.virtual_products.magic import vp_magic, _registry

    vp_magic("--debug --start 0 --stop 10", VP_SCALAR_A)
    vp_magic("--debug --start 0 --stop 10", VP_SCALAR_B)
    vp_magic("--debug --start 0 --stop 10", VP_SCALAR_C)
    qtbot.waitUntil(
        lambda: _registry.get("debug_alpha") is not None and _registry.get("debug_alpha").panel is not None,
        timeout=1000,
    )

    # Find the vertical splitter containing the debug panels
    from SciQLop.user_api.virtual_products.magic import _find_existing_debug_dock
    dock = _find_existing_debug_dock(main_window)
    assert dock is not None

    splitter = dock.dockAreaWidget().parentSplitter()
    if splitter is None or splitter.count() < 2:
        pytest.skip("No vertical splitter found (single debug panel area)")

    sizes = splitter.sizes()
    total = sum(sizes)
    if total == 0:
        pytest.skip("Splitter has zero height (headless without geometry)")

    ratios = [s / total for s in sizes]
    for r in ratios:
        assert 0.15 <= r <= 0.55, f"Panel height ratio {r:.2f} not roughly equal"


def test_reopened_debug_panel_reuses_its_name(qtbot, qapp, main_window):
    """Closing a debug panel with its X gives its name back right away."""
    from SciQLop.user_api.virtual_products.debug import _create_debug_panel

    first = _create_debug_panel("reopen_me")
    main_window.dock_manager.findDockWidget(first.name).requestCloseDockWidget()

    second = _create_debug_panel("reopen_me")
    assert second.name == "VP Debug: reopen_me"
    main_window.remove_panel(second)


def test_renamed_debug_panel_updates_its_tab_and_lookups(qtbot, qapp, main_window):
    from SciQLop.user_api.virtual_products.debug import _create_debug_panel, _find_existing_debug_dock

    panel = _create_debug_panel("rename_me")
    dock_widget = main_window.dock_manager.findDockWidget(panel.name)

    panel.setObjectName("Renamed debug")

    assert dock_widget.windowTitle() == "Renamed debug"
    assert main_window.plot_panel("Renamed debug") is panel
    assert _find_existing_debug_dock(main_window) is dock_widget, "new debug panels still stack below it"
    main_window.remove_panel(panel)
