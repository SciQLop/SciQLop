"""Non-regression test for product browser right-click context menu.

The context menu was introduced in 32ba97c but never worked because
setup_product_context_menu used children() (direct only) instead of
findChildren() to locate the QTreeView inside ProductsView.
"""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeView


@pytest.fixture(scope="module")
def products_view(qapp):
    from SciQLopPlots import ProductsView
    pv = ProductsView(None)
    yield pv


def test_setup_finds_tree_view_and_sets_context_menu_policy(products_view):
    from SciQLop.components.products.product_context_menu import setup_product_context_menu

    setup_product_context_menu(products_view, main_window=None)

    trees = products_view.findChildren(QTreeView)
    assert len(trees) >= 1, "ProductsView should contain a QTreeView"

    tree = trees[0]
    assert tree.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu, (
        "QTreeView inside ProductsView should have CustomContextMenu policy "
        "after setup_product_context_menu runs"
    )
