"""A user_api object's raw `_impl` must not reach kernel-thread code unguarded.

Cells run on the jupyqt kernel thread; the wrapped SciQLopPlots/Qt objects live
on the GUI thread. `panel._get_impl_or_raise().catalog_manager.remove_catalog(c)`
from a cell deleted plot items under a replot and segfaulted (SciQLop#147).
Off the GUI thread, `_impl` is a MainThreadProxy, so such calls are marshaled.
"""
import threading

import numpy as np
import pytest

from SciQLop.components.catalogs.backend.overlay import CatalogOverlay
from SciQLop.user_api.threading import MainThreadProxy, init_invoker

from .fixtures import *  # noqa: F401, F403
from .test_catalog_overlay_api import overlay_panel, overlay_provider  # noqa: F401


@pytest.fixture
def invoker():
    """Install the same main-thread invoker KernelManager installs at runtime."""
    from jupyqt.qt.proxy import MainThreadInvoker
    from SciQLop.user_api import threading as sqp_threading
    previous = sqp_threading._invoker
    init_invoker(MainThreadInvoker())
    yield
    init_invoker(previous)


def _in_worker(qtbot, fn):
    box: dict = {}

    def run():
        try:
            box["result"] = fn()
        except BaseException as e:  # noqa: BLE001 — reported to the test
            box["error"] = e

    t = threading.Thread(target=run, name="fake-kernel-thread")
    t.start()
    qtbot.waitUntil(lambda: not t.is_alive(), timeout=5000)
    assert "error" not in box, box.get("error")
    return box["result"]


def test_impl_on_the_gui_thread_is_the_raw_object(overlay_panel):
    assert not isinstance(overlay_panel._get_impl_or_raise(), MainThreadProxy)


def test_impl_off_the_gui_thread_is_a_proxy(qtbot, invoker, overlay_panel):
    impl = _in_worker(qtbot, overlay_panel._get_impl_or_raise)
    assert isinstance(impl, MainThreadProxy)


def test_plot_and_graph_impls_are_proxied_off_the_gui_thread(qtbot, invoker, plot_panel):
    x = np.linspace(0, 1, 100)
    plot, graph = plot_panel.plot(x, x)
    impls = _in_worker(qtbot, lambda: (plot._impl, graph._impl))
    assert all(isinstance(i, MainThreadProxy) for i in impls)


def test_destroyed_impl_reads_none_off_the_gui_thread(qtbot, invoker, overlay_panel):
    overlay_panel._impl = None
    assert _in_worker(qtbot, lambda: overlay_panel._impl) is None


def test_removing_a_catalog_through_impl_runs_on_the_gui_thread(
        qtbot, invoker, overlay_provider, overlay_panel, monkeypatch):
    overlay_panel.add_catalog_overlay("OverlayTest//room1//events")
    catalog = overlay_provider.catalogs()[0]
    cleared_on = []
    original_clear = CatalogOverlay.clear

    def recording_clear(self):
        cleared_on.append(threading.current_thread().name)
        original_clear(self)

    monkeypatch.setattr(CatalogOverlay, "clear", recording_clear)
    _in_worker(qtbot, lambda: overlay_panel._get_impl_or_raise()
               .catalog_manager.remove_catalog(catalog))
    assert cleared_on == [threading.main_thread().name]
