from tests.fixtures import *
import pytest


@pytest.fixture(autouse=True)
def _clean_registry():
    from SciQLop.user_api.virtual_products.registry import _registry
    _registry._entries.clear()
    yield
    _registry._entries.clear()


def test_vp_magic_reports_knob_specs(qtbot, qapp, main_window):
    from SciQLop.user_api.virtual_products.magic import _vp_magic_impl, _registry
    from SciQLop.components.plotting.backend.data_provider import providers

    cell = (
        "from typing import Annotated\n"
        "from SciQLop.user_api.knobs import Knob\n"
        "def my_vp(start: float, stop: float,\n"
        "          fft: Annotated[int, Knob(min=64, max=4096, step=64)] = 256) -> Scalar:\n"
        "    import numpy as np\n"
        "    n = 8\n"
        "    return np.linspace(start, stop, n), np.zeros(n)\n"
    )
    _vp_magic_impl("", cell, local_ns={})
    entry = _registry.get("my_vp")
    assert entry is not None
    provider = next(p for p in providers.values()
                    if getattr(p, "_callback", None) is entry.wrapper)
    specs = provider.get_knobs("any")
    assert {s.name for s in specs} == {"fft"}


def test_vp_magic_reload_refreshes_knob_specs(qtbot, qapp, main_window):
    """Body-only reload (same signature, only Knob marker changed) must refresh specs."""
    from SciQLop.user_api.virtual_products.magic import _vp_magic_impl, _registry
    from SciQLop.components.plotting.backend.data_provider import providers

    cell_a = (
        "from typing import Annotated\n"
        "from SciQLop.user_api.knobs import Knob\n"
        "def my_vp(start: float, stop: float,\n"
        "          fft: Annotated[int, Knob(min=64, max=4096)] = 256) -> Scalar:\n"
        "    import numpy as np\n"
        "    n = 8\n"
        "    return np.linspace(start, stop, n), np.zeros(n)\n"
    )
    # Same signature (same kwarg name + default type), only Knob marker changed → body-only path
    cell_b = cell_a.replace("Knob(min=64, max=4096)", "Knob(min=128, max=8192, step=64)")
    _vp_magic_impl("", cell_a, local_ns={})
    entry_after_a = _registry.get("my_vp")
    provider = next(p for p in providers.values()
                    if getattr(p, "_callback", None) is entry_after_a.wrapper)
    specs_before = {s.name: s for s in provider.get_knobs("any")}
    assert specs_before["fft"].min == 64

    _vp_magic_impl("", cell_b, local_ns={})
    specs_after = {s.name: s for s in provider.get_knobs("any")}
    assert specs_after["fft"].min == 128
