from tests.helpers import *
import os
import pytest
from PySide6.QtWidgets import QTreeView
from PySide6.QtCore import Qt


class TestDragAndDropWorkflow:
    """Open product tree, drag a product onto a plot panel."""

    @pytest.mark.xfail(
        reason="Drag-and-drop simulation is unreliable and test_plugin is disabled by default",
        strict=False,
    )
    @pytest.mark.skipif(
        "GITHUB_ACTIONS" in os.environ,
        reason="Drag and drop does not work in GitHub Actions",
    )
    def test_drag_product_to_panel(self, qapp, main_window, qtbot, plot_panel):
        from PySide6QtAds import ads

        b = main_window.dock_manager.autoHideSideBar(ads.SideBarLocation.SideBarLeft).tab(0)
        qtbot.mouseClick(b, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, b.rect().center())
        qtbot.wait(100)

        tree: QTreeView = main_window.productTree.findChild(QTreeView)
        tree.expandAll()
        qtbot.wait(100)
        model = tree.model()
        model.setFilterFixedString("TestMultiComponent")
        qtbot.wait(100)
        index = model.index(0, 0, model.index(0, 0))
        drag_and_drop(qapp, qtbot, tree, index, plot_panel._impl)
        for _ in range(10):
            qtbot.wait(10)
        assert len(plot_panel.plots) > 0
