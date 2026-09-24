import numpy as np

from tests.fixtures import *  # noqa: F401,F403
from SciQLop.user_api.data_types import Colored, VPTypeInfo
from SciQLop.user_api.virtual_products.magic import _infer_type_from_data, _inject_type_names
from SciQLop.user_api.virtual_products.registry import VPRegistry


def test_colored_name_is_injected_for_annotations():
    ns = {}
    _inject_type_names(ns)
    assert ns["Colored"] is Colored


def test_unannotated_colored_result_is_inferred_as_coloured_inner_type():
    t = np.linspace(0.0, 1.0, 4)
    info = _infer_type_from_data(Colored((t, np.zeros((4, 3))), color=t))
    assert info == VPTypeInfo("vector", None, colored=True)


def test_redeclaring_as_colored_is_a_new_registration():
    reg = VPRegistry()
    f = lambda start, stop: None
    reg.register("vp", f, "vector", None)
    entry = reg.register("vp", f, "vector", None, colored=True)
    assert entry.signature_changed is True and entry.colored is True


def test_same_declaration_is_hot_swapped():
    reg = VPRegistry()
    f = lambda start, stop: None
    reg.register("vp", f, "vector", None, colored=True)
    assert reg.register("vp", f, "vector", None, colored=True).signature_changed is False


def test_vp_magic_registers_a_colored_vp_from_a_string_annotation(qtbot, qapp, main_window):
    from SciQLop.user_api.virtual_products.magic import vp_magic
    from SciQLop.components.plotting.backend.data_provider import providers
    cell = (
        "from __future__ import annotations\n"
        "def colored_vp(start: float, stop: float) -> Colored[Vector['X', 'Y', 'Z']]:\n"
        "    import numpy as np\n"
        "    t = np.linspace(start, stop, 8)\n"
        "    return Colored((t, np.zeros((8, 3))), color=t)\n"
    )
    _func, _args, info = vp_magic("--start 0 --stop 10", cell, local_ns={})
    assert info.colored is True and info.labels == ["X", "Y", "Z"]
    provider = next(p for p in providers.values()
                    if getattr(getattr(p, "_callback", None), "callback", None) is _func)
    assert provider.color_axis(None) is not None


def test_vp_magic_reads_a_plain_string_annotation(qtbot, qapp, main_window):
    """Under `from __future__ import annotations` the annotation is a string; it
    used to be ignored, so the type was guessed from the data and labels were lost."""
    from SciQLop.user_api.virtual_products.magic import vp_magic
    cell = (
        "from __future__ import annotations\n"
        "def plain_str_vp(start: float, stop: float) -> Vector['Bx', 'By', 'Bz']:\n"
        "    import numpy as np\n"
        "    t = np.linspace(start, stop, 8)\n"
        "    return t, np.zeros((8, 3))\n"
    )
    _func, _args, info = vp_magic("--start 0 --stop 10", cell, local_ns={})
    assert info.labels == ["Bx", "By", "Bz"]
