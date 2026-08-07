"""Graphic primitives must work on plots obtained through ANY public path.

Fuzzing report 2026-06-12 issue #1: plots enumerated via ``panel.plots`` hold a
``SciQLopPlotInterfacePtr`` (Shiboken smart-pointer wrapper) as ``_impl``, and
the C++ item constructors only accept the dereferenced object — so every
primitive (Text, Ellipse, CurvedLine, Pixmap, HorizontalLine, add_hline)
failed with a NameError on those plots, while plots returned directly by
``plot_data`` (concrete impl) worked. Wrappers now dereference the Ptr at
construction so both paths behave identically.
"""
from .fixtures import *  # noqa: F401,F403 — qapp/main_window/plot_panel fixtures
import numpy as np
import pytest
from SciQLop.user_api.plot import VerticalLine, StraightLine, RectangularSpan, HorizontalSpan


@pytest.fixture
def direct_plot(plot_panel):
    from SciQLop.user_api.plot import PlotType

    x = np.linspace(0.0, 100.0, 50)
    plot, _graph = plot_panel.plot_data(x, np.sin(x), plot_type=PlotType.TimeSeries)
    return plot


@pytest.fixture
def enumerated_plot(plot_panel, direct_plot):
    return plot_panel.plots[0]


@pytest.fixture(params=["direct", "enumerated"])
def any_plot(request, direct_plot, enumerated_plot):
    return direct_plot if request.param == "direct" else enumerated_plot


def _png_bytes() -> bytes:
    from PySide6.QtCore import QBuffer
    from PySide6.QtGui import QImage

    image = QImage(4, 4, QImage.Format.Format_RGB32)
    image.fill(0xFF0000)
    buffer = QBuffer()
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def test_enumerated_plot_impl_is_concrete(enumerated_plot):
    from SciQLopPlots import SciQLopPlot

    assert isinstance(enumerated_plot._impl, SciQLopPlot)


def test_text(any_plot):
    from SciQLop.user_api.plot import Text

    item = Text(any_plot, "hello", 0.5, 0.5)
    assert item.text == "hello"


def test_ellipse(any_plot):
    from SciQLop.user_api.plot import Ellipse

    item = Ellipse(any_plot, 1.0, 1.0, 2.0, 2.0)
    assert item.position == (2.0, 2.0)  # position == bounding-box center


def test_curved_line(any_plot):
    from SciQLop.user_api.plot import CurvedLine

    item = CurvedLine(any_plot, (0.0, 0.0), (10.0, 10.0))
    assert item.start == (0.0, 0.0)


def test_pixmap(any_plot):
    from SciQLop.user_api.plot import Pixmap

    item = Pixmap(any_plot, 0.0, 0.0, 4.0, 4.0, _png_bytes())
    assert item.position is not None


def test_horizontal_line(any_plot):
    from SciQLop.user_api.plot import HorizontalLine

    item = HorizontalLine(any_plot, 0.5)
    assert item.value == 0.5


def test_add_hline(any_plot):
    from SciQLop.user_api.plot._graphic_primitives import HorizontalLine

    assert isinstance(any_plot.add_hline(1.0), HorizontalLine)


def test_vertical_line_can_be_added_and_removed(any_plot):
    line = VerticalLine(any_plot, 5.0)
    assert line is not None
    line.remove()


def test_straight_line_can_be_added_and_removed(any_plot):
    line = StraightLine(any_plot, 0.0, 0.0, 9.0, 9.0)
    assert line is not None
    line.remove()


def test_rectangular_span_can_be_added_and_removed(any_plot):
    span = RectangularSpan(any_plot, 2.0, 2.0, 7.0, 7.0)
    assert span is not None
    span.remove()


def test_horizontal_span_can_be_added_and_removed(any_plot):
    span = HorizontalSpan(any_plot, 2.0, 7.0)
    assert span is not None
    span.remove()
