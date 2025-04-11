from .fixtures import *
import pytest
from pytestqt import qt_compat
from pytestqt.qt_compat import qt_api




def test_simple_vp(qtbot, qapp, main_window, simple_vp_callback, plot_panel):
    assert qapp is not None
    assert main_window is not None
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType
    from SciQLop.user_api.plot import TimeRange

    # Create a virtual product
    vp = create_virtual_product(
        path="test_vp",
        callback=simple_vp_callback,
        product_type=VirtualProductType.Scalar,
        labels=["vp"]
    )
    plot_panel.time_range = TimeRange(0., 10.)
    plt,graph = plot_panel.plot(vp)
    for i in range(10):
        qtbot.wait(10)
    x,y = graph.data
    assert len(x) > 0
    assert len(y) > 0
