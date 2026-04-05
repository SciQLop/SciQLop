from .fixtures import *
import pytest
import numpy as np


VP_DEBUG_SCALAR = """
def debug_sine(start: float, stop: float) -> Scalar:
    import numpy as np
    x = np.linspace(start, stop, 100)
    return x, np.sin(x)
"""

VP_DEBUG_ERROR = """
def debug_broken(start: float, stop: float) -> Scalar:
    raise ValueError("intentional error")
"""


def test_debug_mode_opens_panel(qtbot, qapp, main_window):
    from SciQLop.user_api.virtual_products.magic import vp_magic, _registry

    vp_magic("--debug --start 0 --stop 10", VP_DEBUG_SCALAR)
    qtbot.wait(100)

    entry = _registry.get("debug_sine")
    assert entry is not None
    assert entry.panel is not None


def test_debug_mode_reuses_panel(qtbot, qapp, main_window):
    from SciQLop.user_api.virtual_products.magic import vp_magic, _registry

    vp_magic("--debug --start 0 --stop 10", VP_DEBUG_SCALAR)
    panel1 = _registry.get("debug_sine").panel

    vp_magic("--debug --start 0 --stop 10", VP_DEBUG_SCALAR)
    panel2 = _registry.get("debug_sine").panel

    assert panel1 is panel2


def test_debug_mode_shows_error_overlay(qtbot, qapp, main_window):
    from SciQLop.user_api.virtual_products.magic import vp_magic, _registry

    vp_magic("--debug --start 0 --stop 10", VP_DEBUG_ERROR)
    qtbot.wait(100)

    entry = _registry.get("debug_broken")
    assert entry is not None
    assert entry.panel is not None
    # The overlay should be visible with the error
    overlay = getattr(entry.panel, '_vp_overlay', None)
    assert overlay is not None
    assert overlay.isVisible()
    assert "ValueError" in overlay.text()
