"""A test that builds its own main window must not leave it reachable afterwards: the autouse
_release_gui_leftovers fixture puts back every process-wide holder of a window. The two tests run in file order."""
import gc
import weakref

from .fixtures import *  # noqa: F401,F403

_seen = {}


def test_a_test_builds_its_own_main_window(qapp, main_window):
    from SciQLop.core.kernel_namespace import KERNEL_NAMESPACE
    from SciQLop.core.ui.mainwindow import SciQLopMainWindow
    _seen["kernel_value"] = KERNEL_NAMESPACE.find("sciqlop.main_window").value
    _seen["window"] = weakref.ref(SciQLopMainWindow())


def test_that_window_is_released_after_the_test(qapp, main_window):
    from SciQLop.core.kernel_namespace import KERNEL_NAMESPACE
    gc.collect()
    assert _seen["window"]() is None
    assert KERNEL_NAMESPACE.find("sciqlop.main_window").value is _seen["kernel_value"]
    assert qapp.main_window is main_window
