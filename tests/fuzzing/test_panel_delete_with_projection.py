"""Reproducer for the projection-panel-delete SIGSEGV.

User-reported gdb backtrace: Sbk_SciQLopPlotInterfaceFunc_y_axis jumps to
0x0 while a SciQLopNDProjectionCurvesFunction is destroyed during
SciQLopNDProjectionPlot teardown.

Root cause: graph.destroyed (fired while the projection plot is mid
~QWidget — its derived ~SciQLopNDProjectionPlot body has already run, so
the vtable is reset) invokes _PlotHintsRegistry._drop → _recompute →
apply_plot_hints → plot.y_axis(), dispatching through the dead vtable.

Sibling of test_panel_delete_with_layer (the x_axis/TimeSeries variant);
projection plots crash on the SAME registry path because their curves
function is a *direct* child of the plot.

Runs as a subprocess so SIGSEGV manifests as a non-zero returncode
rather than killing the parent test session.
"""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap

import pytest


REPRO_BODY = textwrap.dedent('''
"""Inner reproducer — uses the test fixtures (xcb, AA_UseDesktopOpenGL,
main_window, test_plugin)."""
from tests.fixtures import *  # main_window, qapp, sciqlop_resources, test_plugin

def test_repro(main_window, qapp, qtbot, test_plugin):
    from SciQLop.user_api.plot import create_plot_panel, PlotType, TimeRange

    p = create_plot_panel()
    plot, graph = p.plot("TestPlugin/TestMultiComponent",
                         plot_type=PlotType.Projection)
    p.time_range = TimeRange("2015-10-10", "2015-10-11")
    qtbot.wait(300)

    qtbot.waitExposed(p._impl, timeout=2000)
    p._impl.repaint()
    qtbot.wait(100)

    # Dock-close path: click the (X) on the tab, same as the user closing
    # the panel. Fires CDockWidgetTab.closeRequested → queued teardown.
    panel_name = p._impl.objectName()
    dw = main_window.dock_manager.findDockWidget(panel_name)
    assert dw is not None
    plots = p._impl.plots()
    destroyed = {"flag": False}
    plots[0].destroyed.connect(lambda *_: destroyed.__setitem__("flag", True))
    tab = dw.tabWidget()
    tab.closeRequested.emit()
    qtbot.waitUntil(lambda: destroyed["flag"], timeout=3000)
    qtbot.wait(300)
''')


@pytest.fixture(scope="module")
def inner_test_path(tmp_path_factory):
    d = tmp_path_factory.mktemp("projection_crash_repro")
    p = d / "test_inner_projection_crash.py"
    p.write_text(REPRO_BODY)
    return p


def test_panel_delete_with_projection_does_not_crash(inner_test_path):
    """Subprocess invocation. Treat SIGSEGV (the user's reported crash)
    as failure; tolerate other shutdown noise (SIGABRT etc. from Qt
    teardown happens after the test body completes and is unrelated)."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(inner_test_path),
         "--no-xvfb", "-x", "-q", "-s",
         "--rootdir", repo_root,
         "-p", "no:cacheprovider"],
        cwd=repo_root, capture_output=True, text=True, timeout=240,
    )
    sigsegv = result.returncode in (-11, 139)
    assert not sigsegv, (
        f"projection panel-delete SIGSEGV reproduced: returncode={result.returncode}\n"
        f"--- stdout ---\n{result.stdout[-4000:]}\n"
        f"--- stderr ---\n{result.stderr[-4000:]}"
    )
    assert "1 passed" in result.stdout or "passed" in result.stdout, (
        f"inner test did not report a pass: returncode={result.returncode}\n"
        f"--- stdout ---\n{result.stdout[-4000:]}\n"
        f"--- stderr ---\n{result.stderr[-4000:]}"
    )
