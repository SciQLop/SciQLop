from .fixtures import *
from .helpers import drag_and_drop
import pytest
from pytestqt import qt_compat
from pytestqt.qt_compat import qt_api
from PySide6.QtWidgets import QTreeView
from PySide6.QtCore import Qt
from PySide6.QtCore import QEvent, QVariantAnimation, QCoreApplication
from PySide6.QtGui import QMouseEvent


def show_product_tree(qtbot, main_window):
    from PySide6QtAds import ads
    b = main_window.dock_manager.autoHideSideBar(ads.SideBarLocation.SideBarLeft).tab(0)
    qtbot.mouseClick(b, Qt.MouseButton.LeftButton, Qt.NoModifier, b.rect().center())
    qtbot.wait(1)


def test_drag_and_drop(qtbot, qapp, main_window, plot_panel):
    show_product_tree(qtbot, main_window)
    tree: QTreeView = next(filter(lambda c: isinstance(c, QTreeView), main_window.productTree.children()))
    tree.expandAll()
    qtbot.wait(1)
    model = tree.model()
    index = model.index(0, 0, model.index(0, 0))
    rect = tree.visualRect(index)
    drag_and_drop(qapp, qtbot, tree, index, plot_panel._impl)
    for i in range(10):
        qtbot.wait(1000)
    assert len(plot_panel.plots) > 0
