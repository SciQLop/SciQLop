from tests.helpers import *
from PySide6.QtWidgets import QTreeView


class TestDragAndDropWorkflow:
    """Drop a product onto a plot panel via the registered DnD callback.

    Skips the OS-level mouse/QDrag handshake (which is racy under Xvfb and
    blocks the test event loop once QDrag.exec() opens its modal pump) and
    exercises the rest of the chain end-to-end: ProductsModel.mimeData()
    encodes the dragged index, the panel's ProductDnDCallback decodes it,
    looks up the product node, and dispatches to plot_product.
    """

    def test_drag_product_to_panel(self, qapp, main_window, qtbot, plot_panel, test_plugin):
        from SciQLopPlots import PlotType, ProductsModel

        tree: QTreeView = main_window.productTree.findChild(QTreeView)
        tree.expandAll()
        qtbot.wait(50)
        proxy = tree.model()
        proxy.setFilterFixedString("TestMultiComponent")
        qtbot.wait(50)
        proxy_index = proxy.index(0, 0, proxy.index(0, 0))
        assert proxy_index.isValid(), "filter did not match TestMultiComponent — is test_plugin loaded?"
        src_index = proxy.mapToSource(proxy_index)
        # Use ProductsModel.instance() rather than proxy.sourceModel(): the
        # latter returns a Python wrapper that takes ownership and deleteLaters
        # the singleton C++ object when it goes out of scope, which corrupts
        # subsequent tests that rely on the global ProductsModel.
        mime = ProductsModel.instance().mimeData([src_index])
        assert mime is not None and mime.formats(), "mimeData returned nothing for the product index"

        panel_impl = plot_panel._impl
        panel_impl.create_plot(0, PlotType.TimeSeries)
        qtbot.wait(50)
        target_plot = panel_impl.plots()[0]
        panel_impl._product_plot_callback.call(target_plot, mime)
        qtbot.wait(100)

        assert len(plot_panel.plots) > 0
