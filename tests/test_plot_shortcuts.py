"""M (autoscale), L (log scale) and H (hide selection) on every plot of the app.

SciQLopPlots 0.36 stopped binding these keys itself and left them to the host.
SciQLop only bound them on plots inside its panels, so standalone plots built by
plugins (CDF workbench preview, MSA fit inspector) lost them.

Under Xvfb the test window never becomes active, so Qt neither moves focus nor
emits focusChanged on a click: the tests emit focusChanged themselves and fire
the shortcut's activated signal. Routing a key to it is Qt's job.
"""
import numpy as np
from PySide6.QtCore import QPoint
from PySide6.QtGui import QShortcut
from SciQLopPlots import SciQLopPlot, SciQLopPlotRange

from SciQLop.components.plotting.ui.plot_shortcuts import enable_plot_shortcuts_everywhere

from .fixtures import *  # noqa: F401, F403


def _standalone_plot(qtbot):
    plot = SciQLopPlot()
    qtbot.addWidget(plot)
    plot.resize(400, 300)
    plot.show()
    qtbot.waitExposed(plot)
    return plot, plot.childAt(QPoint(200, 150))


def _shortcuts(plot):
    return {s.key().toString(): s for s in plot.findChildren(QShortcut)}


def test_focusing_a_standalone_plot_binds_m_to_autoscale(qtbot, qapp):
    enable_plot_shortcuts_everywhere(qapp)
    plot, canvas = _standalone_plot(qtbot)
    x = np.linspace(0.0, 10.0, 50)
    plot.line(x, np.ascontiguousarray(1e3 + np.sin(x)), ["a"])
    plot.y_axis().set_range(SciQLopPlotRange(-1.0, 1.0))

    qapp.focusChanged.emit(None, canvas)
    _shortcuts(plot)["M"].activated.emit()

    y = plot.y_axis().range()
    assert y.start() > 990 and y.stop() < 1010, (y.start(), y.stop())


def test_each_key_is_bound_once_however_often_the_plot_gets_focus(qtbot, qapp):
    enable_plot_shortcuts_everywhere(qapp)
    enable_plot_shortcuts_everywhere(qapp)
    plot, canvas = _standalone_plot(qtbot)
    for _ in range(3):
        qapp.focusChanged.emit(None, canvas)
    assert sorted(s.key().toString() for s in plot.findChildren(QShortcut)) == ["H", "L", "M"]


def test_panel_plots_keep_their_keys_bound_once(qtbot, qapp, plot_panel):
    enable_plot_shortcuts_everywhere(qapp)
    plot, _ = plot_panel.plot_data(np.arange(10.0), np.arange(10.0))
    impl = plot._get_impl_or_raise()
    qapp.focusChanged.emit(None, impl)
    assert sorted(s.key().toString() for s in impl.findChildren(QShortcut)) == ["H", "L", "M"]
