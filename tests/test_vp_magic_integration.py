from .fixtures import *
import pytest
import numpy as np


VP_CELL_SCALAR = """
def sine_wave(start: float, stop: float) -> Scalar:
    import numpy as np
    x = np.linspace(start, stop, 100)
    return x, np.sin(x)
"""

VP_CELL_VECTOR = """
def field(start: float, stop: float) -> Vector["Bx", "By", "Bz"]:
    import numpy as np
    x = np.linspace(start, stop, 100)
    y = np.column_stack([np.sin(x), np.cos(x), np.zeros_like(x)])
    return x, y
"""

VP_CELL_NO_ANNOTATION = """
def mystery(start: float, stop: float):
    import numpy as np
    x = np.linspace(start, stop, 100)
    return x, np.sin(x)
"""


def test_vp_magic_registers_scalar(qtbot, qapp, main_window):
    from SciQLop.user_api.virtual_products.magic import _vp_magic_impl, _registry
    from SciQLop.user_api.plot import create_plot_panel, TimeRange

    _vp_magic_impl("", VP_CELL_SCALAR)

    panel = create_plot_panel()
    panel.time_range = TimeRange(0., 10.)
    from SciQLop.user_api.virtual_products import VirtualProductType
    entry = _registry.get("sine_wave")
    assert entry is not None
    assert entry.product_type == "scalar"


def test_vp_magic_registers_vector(qtbot, qapp, main_window):
    from SciQLop.user_api.virtual_products.magic import _vp_magic_impl, _registry

    _vp_magic_impl("", VP_CELL_VECTOR)

    entry = _registry.get("field")
    assert entry is not None
    assert entry.product_type == "vector"
    assert entry.labels == ["Bx", "By", "Bz"]


def test_vp_magic_rerun_swaps_callback(qtbot, qapp, main_window):
    from SciQLop.user_api.virtual_products.magic import _vp_magic_impl, _registry

    _vp_magic_impl("", VP_CELL_SCALAR)
    wrapper1 = _registry.get("sine_wave").wrapper

    _vp_magic_impl("", VP_CELL_SCALAR)
    wrapper2 = _registry.get("sine_wave").wrapper

    assert wrapper1 is wrapper2  # same wrapper, callback swapped


def test_vp_magic_infers_scalar_from_shape(qtbot, qapp, main_window):
    from SciQLop.user_api.virtual_products.magic import _vp_magic_impl, _registry

    _vp_magic_impl("--start 0 --stop 10", VP_CELL_NO_ANNOTATION)

    entry = _registry.get("mystery")
    assert entry is not None
    assert entry.product_type == "scalar"


def test_vp_magic_custom_path(qtbot, qapp, main_window):
    from SciQLop.user_api.virtual_products.magic import _vp_magic_impl, _registry

    _vp_magic_impl('--path "custom/path/sine"', VP_CELL_SCALAR)
    entry = _registry.get("sine_wave")
    assert entry is not None


def test_vp_magic_sees_user_namespace(qtbot, qapp, main_window):
    """Verify that the function can see variables from the user's namespace."""
    from SciQLop.user_api.virtual_products.magic import _vp_magic_impl, _registry

    user_ns = {"MY_CONST": 42}
    cell = """
def ns_test(start: float, stop: float) -> Scalar:
    import numpy as np
    x = np.linspace(start, stop, MY_CONST)
    return x, np.sin(x)
"""
    _vp_magic_impl("", cell, local_ns=user_ns)
    entry = _registry.get("ns_test")
    assert entry is not None
    # Verify the function actually used MY_CONST (42 points)
    data = entry.wrapper(0.0, 1.0)
    assert len(data[0]) == 42
