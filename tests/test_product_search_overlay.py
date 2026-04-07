from unittest.mock import patch, MagicMock
import pytest

from PySide6.QtWidgets import QLineEdit, QListView, QLabel
from SciQLopPlots import ProductsModelNodeType


class TestProductSearchOverlayCreation:
    def test_overlay_has_search_box(self, qtbot):
        from SciQLop.components.plotting.ui.product_search_overlay import ProductSearchOverlay
        overlay = ProductSearchOverlay()
        qtbot.addWidget(overlay)
        line_edit = overlay.findChild(QLineEdit)
        assert line_edit is not None
        assert "Search products" in line_edit.placeholderText()

    def test_overlay_has_result_list(self, qtbot):
        from SciQLop.components.plotting.ui.product_search_overlay import ProductSearchOverlay
        overlay = ProductSearchOverlay()
        qtbot.addWidget(overlay)
        list_view = overlay.findChild(QListView)
        assert list_view is not None
        assert not list_view.isVisible()

    def test_overlay_has_label(self, qtbot):
        from SciQLop.components.plotting.ui.product_search_overlay import ProductSearchOverlay
        overlay = ProductSearchOverlay()
        qtbot.addWidget(overlay)
        labels = overlay.findChildren(QLabel)
        texts = [l.text() for l in labels]
        assert any("Add a product" in t for t in texts)

    def test_overlay_has_drop_zone(self, qtbot):
        from SciQLop.components.plotting.ui.product_search_overlay import ProductSearchOverlay
        overlay = ProductSearchOverlay()
        qtbot.addWidget(overlay)
        labels = overlay.findChildren(QLabel)
        texts = [l.text() for l in labels]
        assert any("Drop products here" in t for t in texts)


class TestProductSearchOverlaySelection:
    def test_clicking_parameter_emits_signal(self, qtbot):
        from SciQLop.components.plotting.ui.product_search_overlay import ProductSearchOverlay
        import SciQLop.components.plotting.ui.product_search_overlay as overlay_mod

        overlay = ProductSearchOverlay()
        qtbot.addWidget(overlay)

        signals = []
        overlay.product_selected.connect(lambda p: signals.append(p))

        mock_node = MagicMock()
        mock_node.node_type.return_value = ProductsModelNodeType.PARAMETER
        overlay._result_paths = [["amda", "MMS", "MMS1", "FGM", "mms1_b_gse"]]
        mock_index = MagicMock()
        mock_index.row.return_value = 0

        with patch.object(overlay_mod, "ProductsModel") as mock_model:
            mock_model.node.return_value = mock_node
            overlay._on_result_clicked(mock_index)

        assert len(signals) == 1
        assert signals[0] == ["amda", "MMS", "MMS1", "FGM", "mms1_b_gse"]

    def test_clicking_folder_does_not_emit(self, qtbot):
        from SciQLop.components.plotting.ui.product_search_overlay import ProductSearchOverlay
        import SciQLop.components.plotting.ui.product_search_overlay as overlay_mod

        overlay = ProductSearchOverlay()
        qtbot.addWidget(overlay)

        signals = []
        overlay.product_selected.connect(lambda p: signals.append(p))

        mock_node = MagicMock()
        mock_node.node_type.return_value = ProductsModelNodeType.FOLDER
        overlay._result_paths = [["amda", "MMS"]]
        mock_index = MagicMock()
        mock_index.row.return_value = 0

        with patch.object(overlay_mod, "ProductsModel") as mock_model:
            mock_model.node.return_value = mock_node
            overlay._on_result_clicked(mock_index)

        assert len(signals) == 0

    def test_out_of_range_click_ignored(self, qtbot):
        from SciQLop.components.plotting.ui.product_search_overlay import ProductSearchOverlay
        overlay = ProductSearchOverlay()
        qtbot.addWidget(overlay)

        signals = []
        overlay.product_selected.connect(lambda p: signals.append(p))
        overlay._result_paths = []
        mock_index = MagicMock()
        mock_index.row.return_value = 5

        overlay._on_result_clicked(mock_index)
        assert len(signals) == 0


class TestTimeSyncPanelOverlay:
    def test_new_panel_has_overlay(self, qtbot):
        from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
        from SciQLop.components.plotting.ui.product_search_overlay import ProductSearchOverlay
        panel = TimeSyncPanel(name="TestPanel")
        qtbot.addWidget(panel)
        panel.show()
        assert panel._search_overlay is not None
        assert isinstance(panel._search_overlay, ProductSearchOverlay)
        assert panel._search_overlay.isVisible()

    def test_overlay_hidden_after_plot_added(self, qtbot):
        from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
        from SciQLopPlots import PlotType
        panel = TimeSyncPanel(name="TestPanel2")
        qtbot.addWidget(panel)
        assert panel._search_overlay is not None

        panel.create_plot(0, PlotType.TimeSeries)

        qtbot.waitUntil(lambda: panel._search_overlay is None, timeout=1000)
        assert panel._search_overlay is None
