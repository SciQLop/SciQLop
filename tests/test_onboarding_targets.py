from unittest.mock import MagicMock
from PySide6.QtCore import Qt


def _fake_model(tree: dict):
    """A minimal QAbstractItemModel-like mock from a nested dict."""
    model = MagicMock()

    def _children_of(parent):
        node = tree if parent is None or not parent.isValid() else getattr(parent, "_node", tree)
        return list(node.items())

    def index(row, col, parent):
        children = _children_of(parent)
        idx = MagicMock()
        idx.isValid.return_value = True
        idx._node = children[row][1] if row < len(children) else None
        idx._name = children[row][0] if row < len(children) else None
        return idx

    model.index.side_effect = index
    model.rowCount.side_effect = lambda parent: len(_children_of(parent))
    model.data.side_effect = lambda idx, role: idx._name if role == Qt.ItemDataRole.DisplayRole else None
    return model


def test_find_index_by_path_found():
    from SciQLop.components.onboarding.backend.targets import find_index_by_path
    result = find_index_by_path(_fake_model({"cda": {"MMS": {"MMS1": {}}}}), ["cda", "MMS", "MMS1"])
    assert result is not None and result._name == "MMS1"


def test_find_index_by_path_not_found():
    from SciQLop.components.onboarding.backend.targets import find_index_by_path
    assert find_index_by_path(_fake_model({"cda": {"MMS": {}}}), ["cda", "AMDA", "x"]) is None


def test_find_index_by_path_case_insensitive():
    from SciQLop.components.onboarding.backend.targets import find_index_by_path
    result = find_index_by_path(_fake_model({"CDA": {"mms": {}}}), ["cda", "MMS"])
    assert result is not None and result._name == "mms"


def test_example_product_path_matches_the_speasy_rooted_ace_mfi_node():
    from SciQLop.components.onboarding.backend.targets import find_index_by_path, EXAMPLE_PRODUCT_PATH
    model = _fake_model({"speasy": {"amda": {"Parameters": {"ACE": {"MFI": {
        "final / prelim": {"b_gse": {}}}}}}}})
    result = find_index_by_path(model, EXAMPLE_PRODUCT_PATH)
    assert result is not None and result._name == "b_gse"


from .fixtures import *


def test_resolve_add_panel_button_returns_the_welcome_areas_button(main_window):
    from SciQLop.components.onboarding.backend.targets import resolve_add_panel_button
    from PySide6.QtWidgets import QToolButton
    assert isinstance(resolve_add_panel_button(main_window, {}), QToolButton)


def test_resolve_example_product_returns_the_row_when_present(main_window, qtbot):
    from SciQLop.components.onboarding.backend.targets import resolve_example_product
    from PySide6.QtWidgets import QTreeView
    dw = main_window.dock_manager.findDockWidget("Products")
    dw.toggleView(True)
    qtbot.waitUntil(dw.isVisible, timeout=1000)
    qtbot.wait(100)
    target = resolve_example_product(main_window, {})
    if isinstance(target, tuple):
        tree, rect = target
        assert isinstance(tree, QTreeView) and rect.isValid()
    else:
        assert isinstance(target, QTreeView)


def test_resolve_example_product_falls_back_to_the_whole_tree(main_window, monkeypatch):
    from SciQLop.components.onboarding.backend import targets
    from PySide6.QtWidgets import QTreeView
    monkeypatch.setattr(targets, "EXAMPLE_PRODUCT_PATH", ["speasy", "no", "such", "product"])
    assert isinstance(targets.resolve_example_product(main_window, {}), QTreeView)


def test_in_dock_opens_a_closed_side_dock_before_resolving(main_window, qtbot):
    from SciQLop.components.onboarding.backend.targets import in_dock
    dw = main_window.dock_manager.findDockWidget("Catalog Browser")
    dw.autoHideDockContainer().collapseView(True)
    qtbot.waitUntil(lambda: not dw.isVisible(), timeout=1000)

    from SciQLop.components.onboarding.backend.targets import resolve_catalog_tree
    tree = in_dock("Catalog Browser", resolve_catalog_tree)(main_window, {})
    assert tree is resolve_catalog_tree(main_window, {})
    assert tree.isVisible(), "the inner widget must be showable right after resolving"
    assert dw.isVisible()


def test_in_dock_returns_none_for_an_unknown_dock(main_window):
    from SciQLop.components.onboarding.backend.targets import in_dock
    assert in_dock("No Such Dock", lambda mw, ctx: object())(main_window, {}) is None


def test_resolve_panel_widget_reads_panel_from_context(main_window):
    from SciQLop.components.onboarding.backend.targets import resolve_panel_widget
    assert resolve_panel_widget(main_window, {}) is None
    panel = main_window.new_plot_panel()
    try:
        assert resolve_panel_widget(main_window, {"create_panel": panel}) is panel
    finally:
        main_window.remove_panel(panel)


def test_panel_targets_resolve_the_search_box_chrome_and_catalog_controls(main_window, qtbot):
    from SciQLop.components.onboarding.backend import targets
    from PySide6.QtWidgets import QLineEdit
    panel = main_window.new_plot_panel()
    context = {"create_panel": panel}
    try:
        assert isinstance(targets.resolve_search_box(main_window, context), QLineEdit)
        chrome = targets.resolve_panel_chrome(main_window, context)
        assert chrome is panel.parentWidget().chrome_row
        assert targets.resolve_catalog_chrome(main_window, context) is panel.parentWidget().catalog_chrome
    finally:
        main_window.remove_panel(panel)


def test_panel_targets_are_none_without_a_panel(main_window):
    from SciQLop.components.onboarding.backend import targets
    assert targets.resolve_search_box(main_window, {}) is None
    assert targets.resolve_panel_chrome(main_window, {}) is None
    assert targets.resolve_catalog_chrome(main_window, {}) is None


def test_panel_targets_survive_a_deleted_panel(main_window, qtbot):
    import shiboken6
    from SciQLop.components.onboarding.backend import targets
    panel = main_window.new_plot_panel()
    context = {"create_panel": panel}
    main_window.remove_panel(panel)
    qtbot.waitUntil(lambda: not shiboken6.isValid(panel), timeout=2000)
    assert targets.resolve_panel_widget(main_window, context) is None
    assert targets.resolve_search_box(main_window, context) is None
    assert targets.resolve_panel_chrome(main_window, context) is None


def test_side_tab_resolver(main_window):
    from SciQLop.components.onboarding.backend.targets import side_tab_resolver
    assert side_tab_resolver("No Such Dock")(main_window, {}) is None
    dw = main_window.dock_manager.findDockWidget("Products")
    assert side_tab_resolver("Products")(main_window, {}) is dw.sideTabWidget()


def test_resolve_catalog_tree_finds_a_tree_view(main_window):
    from SciQLop.components.onboarding.backend.targets import resolve_catalog_tree
    from PySide6.QtWidgets import QTreeView
    assert isinstance(resolve_catalog_tree(main_window, {}), QTreeView)


def test_unless_dock_visible_skips_when_the_panel_is_already_open(main_window, qtbot):
    """A user who opened the Products panel while reading the previous
    tip must not be told to open it (a click would close it) -- the step
    is pointless, skip it."""
    from SciQLop.components.onboarding.backend.targets import unless_dock_visible, side_tab_resolver
    dw = main_window.dock_manager.findDockWidget("Products")
    resolver = unless_dock_visible("Products", side_tab_resolver("Products"))

    dw.toggleView(True)
    qtbot.waitUntil(dw.isVisible, timeout=1000)
    assert resolver(main_window, {}) is None

    dw.autoHideDockContainer().collapseView(True)
    qtbot.waitUntil(lambda: not dw.isVisible(), timeout=1000)
    assert resolver(main_window, {}) is dw.sideTabWidget()


def test_resolve_search_box_gives_the_box_keyboard_focus(main_window, qtbot):
    """The tip asks the user to type: typing must work right away."""
    from SciQLop.components.onboarding.backend import targets
    panel = main_window.new_plot_panel()
    try:
        qtbot.waitUntil(panel.isVisible, timeout=1000)
        box = targets.resolve_search_box(main_window, {"create_panel": panel})
        assert main_window.focusWidget() is box
    finally:
        main_window.remove_panel(panel)
