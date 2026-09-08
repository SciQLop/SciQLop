import shiboken6
from PySide6.QtCore import Qt, QAbstractItemModel, QModelIndex
from PySide6.QtWidgets import QTreeView, QWidget

from SciQLop.components.onboarding.backend.completions import _is_real_plot

# The products tree is rooted at a single "speasy" node; "final / prelim"
# is one AMDA-renamed node, not two.
EXAMPLE_PRODUCT_PATH = ["speasy", "amda", "Parameters", "ACE", "MFI", "final / prelim", "b_gse"]


def find_index_by_path(model: QAbstractItemModel, path: list[str],
                       parent: QModelIndex | None = None) -> QModelIndex | None:
    if not path:
        return parent
    parent = parent if parent is not None else QModelIndex()
    target = path[0].lower()
    for row in range(model.rowCount(parent)):
        idx = model.index(row, 0, parent)
        text = model.data(idx, Qt.ItemDataRole.DisplayRole)
        if isinstance(text, str) and text.lower() == target:
            return find_index_by_path(model, path[1:], idx)
    return None


def _live(widget):
    return widget if widget is not None and shiboken6.isValid(widget) else None


def _products_tree_view(main_window) -> QTreeView | None:
    trees = main_window.productTree.findChildren(QTreeView)
    return trees[0] if trees else None


def _panel_container(panel):
    """The PanelContainer wrapping a TimeSyncPanel (owner of its chrome row)."""
    panel = _live(panel)
    container = panel.parentWidget() if panel is not None else None
    return container if hasattr(container, "chrome_row") else None


def _expand_ancestors(tree: QTreeView, index: QModelIndex) -> None:
    chain = []
    parent = index.parent()
    while parent.isValid():
        chain.append(parent)
        parent = parent.parent()
    for ancestor in reversed(chain):
        tree.setExpanded(ancestor, True)


def resolve_add_panel_button(main_window, context) -> QWidget | None:
    dw = next((dw for dw in main_window.dock_manager.dockWidgets()
               if dw.widget() is main_window.welcome), None)
    area = dw.dockAreaWidget() if dw is not None else None
    return area.property("sciqlop_add_panel_button") if area is not None else None


def side_tab_resolver(dock_name: str):
    def _resolver(main_window, context) -> QWidget | None:
        dw = main_window.dock_manager.findDockWidget(dock_name)
        return dw.sideTabWidget() if dw is not None else None
    return _resolver


def in_dock(dock_name: str, resolver):
    """Open the auto-hide dock the target lives in before resolving it, so
    a step inside a side panel works even if the user skipped the
    "click to open it" step."""
    def _resolver(main_window, context):
        dw = main_window.dock_manager.findDockWidget(dock_name)
        if dw is None:
            return None
        if not dw.isVisible():
            dw.toggleView(True)
        return resolver(main_window, context)
    return _resolver


def skip_when_plotted(resolver):
    """Skip the step once the panel already shows something (the user
    plotted from the search box before reaching the drag step)."""
    def _resolver(main_window, context):
        panel = _live(context.get("create_panel"))
        if panel is not None and any(_is_real_plot(p) for p in panel.plots()):
            return None
        return resolver(main_window, context)
    return _resolver


def resolve_example_product(main_window, context):
    """The example product's row inside the tree, or the whole tree when
    that product isn't in the inventory (offline, provider disabled)."""
    tree = _products_tree_view(main_window)
    if tree is None or tree.model() is None:
        return None
    index = find_index_by_path(tree.model(), EXAMPLE_PRODUCT_PATH)
    if index is None:
        return tree
    _expand_ancestors(tree, index)
    tree.scrollTo(index)
    row = tree.visualRect(index)
    return (tree, row) if row.isValid() else tree


def resolve_panel_widget(main_window, context) -> QWidget | None:
    return _live(context.get("create_panel"))


def resolve_search_box(main_window, context) -> QWidget | None:
    overlay = getattr(_live(context.get("create_panel")), "search_overlay", None)
    return overlay.search_box if overlay is not None else None


def resolve_panel_chrome(main_window, context) -> QWidget | None:
    container = _panel_container(context.get("create_panel"))
    return container.chrome_row if container is not None else None


def resolve_catalog_chrome(main_window, context) -> QWidget | None:
    container = _panel_container(context.get("create_panel"))
    return container.catalog_chrome if container is not None else None


def resolve_catalog_tree(main_window, context) -> QTreeView | None:
    trees = main_window.catalogs_browser.findChildren(QTreeView)
    return trees[0] if trees else None
