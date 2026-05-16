"""Reproducer for the panel-delete-with-layer SIGSEGV.

User-reported gdb backtrace: Sbk_SciQLopPlotFunc_x_axis crashes inside
QWidget::sharedPainter() during InspectorExtensionWrapper destruction
triggered by SciQLopTimeSeriesPlot teardown.

Hypothesis: graph.destroyed (fired during plot teardown) invokes
_PlotHintsRegistry._drop → _recompute → apply_plot_hints →
plot.x_axis() on a half-destructed plot.

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
import numpy as np
from tests.fixtures import *  # main_window, qapp, sciqlop_resources, test_plugin

def test_repro(main_window, qapp, qtbot, test_plugin):
    from SciQLop.user_api.plot import create_plot_panel
    from SciQLop.user_api.layers.types import Marker
    from SciQLop.user_api.knobs import Knob
    from SciQLop.user_api.layers import Vector
    from typing import Annotated

    p = create_plot_panel()
    # User uses the ACE template — 4 plots, each with a vector graph.
    for _ in range(4):
        p.plot("TestPlugin/TestMultiComponent")
        qtbot.wait(40)

    def threshold_crossings(
        data: Vector,
        threshold: Annotated[float, Knob(widget="hline", min=-50.0, max=50.0,
                                          step=0.5, color="#e74c3c")] = 0.5,
    ):
        if data.values.size < 2:
            return []
        mag = data.values[:, -1]
        cr = np.where(np.diff(np.sign(mag - threshold)))[0]
        return [Marker(time=float(data.time[i]), value=threshold) for i in cr]

    renderer = p.add_layer(threshold_crossings, plot_index=0)
    qtbot.wait(300)

    qtbot.waitExposed(p._impl, timeout=2000)
    p._impl.repaint()
    qtbot.wait(100)

    if renderer._knob_state is not None:
        renderer._knob_state.set_value("threshold", 1.5)
        qtbot.wait(50)

    # Dock-close path: simulate clicking the (X) button on the tab —
    # this fires CDockWidgetTab.closeRequested which is wired internally
    # to the dock-area close machinery; goes through queued
    # QAction.trigger() rather than the direct programmatic close API.
    panel_name = p._impl.name
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
    d = tmp_path_factory.mktemp("layer_crash_repro")
    p = d / "test_inner_layer_crash.py"
    p.write_text(REPRO_BODY)
    return p


def test_panel_delete_with_layer_does_not_crash(inner_test_path):
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
        f"panel-delete SIGSEGV reproduced: returncode={result.returncode}\n"
        f"--- stdout ---\n{result.stdout[-4000:]}\n"
        f"--- stderr ---\n{result.stderr[-4000:]}"
    )
    assert "1 passed" in result.stdout or "passed" in result.stdout, (
        f"inner test did not report a pass: returncode={result.returncode}\n"
        f"--- stdout ---\n{result.stdout[-4000:]}\n"
        f"--- stderr ---\n{result.stderr[-4000:]}"
    )
