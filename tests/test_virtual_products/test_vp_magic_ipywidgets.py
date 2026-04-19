"""Verifies %%vp --debug displays ipywidgets for knobs when a kernel is live."""
import sys
import types

import pytest

from tests.fixtures import *  # noqa: F401,F403


@pytest.fixture(autouse=True)
def _clean_registry():
    from SciQLop.user_api.virtual_products.registry import _registry
    _registry._entries.clear()
    yield
    _registry._entries.clear()


def _install_fake_ipywidgets(monkeypatch):
    fake = types.ModuleType("ipywidgets")

    class _Widget:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
            self._observers = []

        def observe(self, fn, names="value"):
            self._observers.append((fn, names))

    for cls_name in ("IntSlider", "FloatSlider", "Checkbox", "Dropdown", "Text"):
        setattr(fake, cls_name, type(cls_name, (_Widget,), {}))

    class HBox(_Widget):
        def __init__(self, children=()):
            super().__init__(children=children)

    fake.HBox = HBox
    monkeypatch.setitem(sys.modules, "ipywidgets", fake)
    return fake


def test_debug_displays_ipywidgets_when_kernel_present(qtbot, qapp, main_window,
                                                      monkeypatch):
    fake = _install_fake_ipywidgets(monkeypatch)

    from SciQLop.user_api.virtual_products import ipywidgets_binding
    monkeypatch.setattr(ipywidgets_binding, "_has_widget_comm", lambda: True)

    displayed = []
    import IPython.display as _disp
    monkeypatch.setattr(_disp, "display", lambda obj: displayed.append(obj))

    from SciQLop.user_api.virtual_products.magic import vp_magic
    cell = (
        "from typing import Annotated\n"
        "from SciQLop.user_api.knobs import Knob\n"
        "def my_vp(start: float, stop: float,\n"
        "          fft: Annotated[int, Knob(min=64, max=4096)] = 256) -> Scalar:\n"
        "    import numpy as np\n"
        "    n = 8\n"
        "    return np.linspace(start, stop, n), np.zeros(n) + fft\n"
    )
    vp_magic("--debug --start 0 --stop 10", cell)
    qtbot.wait(100)

    assert displayed, "expected at least one ipywidget HBox to be displayed"
    box = displayed[-1]
    assert isinstance(box, fake.HBox)
    assert box.children, "HBox should have widget children for knobs"
