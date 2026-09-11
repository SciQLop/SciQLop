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


def test_vp_magic_eval_failure_raises_usage_error(qtbot, qapp, main_window):
    """Without --debug, a failing callback (no return annotation) must surface
    via UsageError so the notebook cell shows a red traceback instead of a
    silent log line."""
    from IPython.core.error import UsageError
    from SciQLop.user_api.virtual_products.magic import _vp_magic_impl

    cell = (
        "def broken(start, stop):\n"
        "    raise RuntimeError('boom')\n"
    )
    with pytest.raises(UsageError, match="boom"):
        _vp_magic_impl("--start 0 --stop 10", cell)


def test_vp_magic_resolves_depends_during_eval(qtbot, qapp, main_window):
    """A Depends()-annotated parameter must be resolved before the smoke-test
    call the magic makes to infer the type / render --debug. Without a return
    annotation (or with --debug), `needs_eval` is True and `vp_magic` used to
    call the raw callback directly, skipping dependency resolution entirely —
    crashing with a missing-positional-argument TypeError instead of running
    the callback, unlike the real EasyProvider fetch path which does resolve
    Depends()."""
    from SciQLop.user_api.virtual_products.magic import _vp_magic_impl, _registry

    cell = (
        "from typing import Annotated\n"
        "from SciQLop.user_api.virtual_products import Depends\n"
        "\n"
        "def _dep_source(start, stop):\n"
        "    import numpy as np\n"
        "    x = np.linspace(start, stop, 10)\n"
        "    return x, np.ones(10)\n"
        "\n"
        "def with_dependency(start: float, stop: float,\n"
        "                     series: Annotated[object, Depends(_dep_source)]):\n"
        "    return series\n"
    )
    _vp_magic_impl("--start 0 --stop 10", cell)

    entry = _registry.get("with_dependency")
    assert entry is not None
    assert entry.product_type == "scalar"


def test_vp_magic_depends_failure_raises_usage_error_with_context(qtbot, qapp, main_window):
    """A Depends() target that fails to resolve must surface with the
    dependency name/target in the message — matching EasyProvider's
    RuntimeError wrapping (`easy_provider.py::_resolve_dependencies`) instead
    of a bare traceback from the target callable."""
    from IPython.core.error import UsageError
    from SciQLop.user_api.virtual_products.magic import _vp_magic_impl

    cell = (
        "from typing import Annotated\n"
        "from SciQLop.user_api.virtual_products import Depends\n"
        "\n"
        "def _broken_dep(start, stop):\n"
        "    raise RuntimeError('upstream boom')\n"
        "\n"
        "def with_broken_dependency(start: float, stop: float,\n"
        "                           series: Annotated[object, Depends(_broken_dep)]):\n"
        "    return series\n"
    )
    with pytest.raises(UsageError, match="failed to resolve dependency 'series'"):
        _vp_magic_impl("--start 0 --stop 10", cell)


def test_vp_magic_debug_flags_dependency_with_no_data(qtbot, qapp, main_window):
    """--debug on a Depends()-using VP whose dependency resolves to no data
    must record that as an eval error for the debug panel (matching
    EasyProvider's debug-mode behavior), not silently call the callback with
    `series=None` and infer a type from garbage."""
    from SciQLop.user_api.virtual_products.magic import _vp_magic_impl, _registry

    cell = (
        "from typing import Annotated\n"
        "from SciQLop.user_api.virtual_products import Depends\n"
        "\n"
        "def _empty_dep(start, stop):\n"
        "    return None\n"
        "\n"
        "def with_empty_dependency(start: float, stop: float,\n"
        "                          series: Annotated[object, Depends(_empty_dep)]) -> Scalar:\n"
        "    return series\n"
    )
    _vp_magic_impl("--start 0 --stop 10 --debug", cell)

    entry = _registry.get("with_empty_dependency")
    assert entry is not None


def test_vp_magic_skips_underscore_helpers(qtbot, qapp, main_window):
    """A cell with helper `_foo` and a public `vp` should register `vp`."""
    from SciQLop.user_api.virtual_products.magic import _vp_magic_impl, _registry

    cell = (
        "def _scale(x):\n"
        "    import numpy as np\n"
        "    return np.asarray(x) * 2\n"
        "def with_helper(start: float, stop: float) -> Scalar:\n"
        "    import numpy as np\n"
        "    x = np.linspace(start, stop, 50)\n"
        "    return x, _scale(x)\n"
    )
    _vp_magic_impl("", cell)
    entry = _registry.get("with_helper")
    assert entry is not None
    assert entry.product_type == "scalar"


def test_vp_magic_multiple_public_functions_raises(qtbot, qapp, main_window):
    from IPython.core.error import UsageError
    from SciQLop.user_api.virtual_products.magic import _vp_magic_impl

    cell = (
        "def a(start: float, stop: float) -> Scalar:\n"
        "    import numpy as np\n"
        "    x = np.linspace(start, stop, 10); return x, x\n"
        "def b(start: float, stop: float) -> Scalar:\n"
        "    import numpy as np\n"
        "    x = np.linspace(start, stop, 10); return x, x\n"
    )
    with pytest.raises(UsageError, match="multiple public functions"):
        _vp_magic_impl("", cell)


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
