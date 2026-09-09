from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import QMenu, QTreeView

from SciQLopPlots import ProductsModel, ProductsModelNodeType, PlotType

from SciQLop.components.plotting.ui.time_sync_panel import plot_product
from SciQLop.core.mime import decode_mime
from SciQLop.core.ui.tooltips import rich_tooltip
from SciQLop.components.sciqlop_logging import getLogger

log = getLogger(__name__)


def _source_index(proxy_index: QModelIndex) -> QModelIndex:
    """Unwrap proxy layers to get the source ProductsModel index."""
    model = proxy_index.model()
    idx = proxy_index
    while hasattr(model, 'mapToSource'):
        idx = model.mapToSource(idx)
        model = model.sourceModel()
    return idx


def _product_path_from_index(proxy_index: QModelIndex) -> list[str] | None:
    """Get the canonical product path using the same MIME encoding as drag & drop."""
    src_idx = _source_index(proxy_index)
    mime_data = ProductsModel.instance().mimeData([src_idx])
    if mime_data is None:
        return None
    products = decode_mime(mime_data)
    if products and len(products) > 0:
        return products[0]
    return None


def _is_plottable_index(proxy_index: QModelIndex) -> bool:
    path = _product_path_from_index(proxy_index)
    if path:
        node = ProductsModel.node(path)
        return node is not None and node.node_type() == ProductsModelNodeType.PARAMETER
    return False


def _build_plot_target_menu(menu: QMenu, product_path: list[str], main_window):
    panels = main_window.plot_panels()
    for panel_name in panels:
        panel = main_window.plot_panel(panel_name)
        if panel is None:
            continue
        panel_menu = menu.addMenu(panel_name)
        panel_menu.setToolTipsVisible(True)
        panel_menu.menuAction().setToolTip(rich_tooltip(
            panel_name, "Choose a plot in this panel."))
        plots = panel.plots()
        for i, plot_widget in enumerate(plots):
            graph_names = [g.name for g in plot_widget.plottables()]
            label = ", ".join(graph_names) if graph_names else f"Plot {i + 1}"
            plot_action = panel_menu.addAction(
                label, lambda p=plot_widget, pp=product_path: plot_product(p, pp))
            plot_action.setToolTip(rich_tooltip(
                label, "Add this product to this plot as a new curve."))
        panel_menu.addSeparator()
        new_plot = panel_menu.addAction(
            "+ New plot",
            lambda p=panel, pp=product_path: plot_product(
                p, pp, plot_type=PlotType.TimeSeries))
        new_plot.setToolTip(rich_tooltip(
            "New plot in this panel",
            "Add this product as a new plot in the panel."))

    menu.addSeparator()
    new_panel = menu.addAction(
        "+ New plot panel",
        lambda pp=product_path: _plot_in_new_panel(pp, main_window))
    new_panel.setToolTip(rich_tooltip(
        "New plot panel", "Open this product in a brand-new plot panel."))


def _plot_in_new_panel(product_path: list[str], main_window):
    panel = main_window.new_plot_panel()
    if panel is not None:
        plot_product(panel, product_path, plot_type=PlotType.TimeSeries)


def setup_product_context_menu(product_tree_view, main_window):
    """Connect a right-click context menu on the product tree that lets users
    pick which panel/plot to add the selected product to."""
    trees = product_tree_view.findChildren(QTreeView)
    tree: QTreeView = trees[0] if trees else None
    if tree is None:
        log.warning("Could not find QTreeView inside ProductsView")
        return

    tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    tree.customContextMenuRequested.connect(
        lambda pos: _on_context_menu(tree, pos, main_window))


def _on_context_menu(tree: QTreeView, pos, main_window):
    index = tree.indexAt(pos)
    if not index.isValid():
        return

    if not _is_plottable_index(index):
        _show_folder_context_menu(tree, pos)
        return

    product_path = _product_path_from_index(index)
    if not product_path:
        return

    menu = QMenu(tree)
    menu.setTitle("Plot in...")
    menu.setToolTipsVisible(True)
    _build_plot_target_menu(menu, product_path, main_window)
    menu.exec(tree.viewport().mapToGlobal(pos))


def _show_folder_context_menu(tree: QTreeView, pos):
    menu = QMenu(tree)
    action = menu.addAction("Pick a product inside this folder to plot it")
    action.setEnabled(False)
    menu.exec(tree.viewport().mapToGlobal(pos))
