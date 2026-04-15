"""Tests for apply_plot_hints against a mock plot object.

We don't need a real SciQLopPlot here — the contract is "call the right
setters with the right values." A minimal mock captures that exactly and
keeps the test Qt-free.
"""
from unittest.mock import MagicMock

from SciQLop.core.plot_hints import AxisHints, PlotHints, apply_plot_hints


def _make_plot():
    plot = MagicMock()
    # Each axis getter returns a fresh MagicMock so set_label/set_log land there.
    plot.y_axis.return_value = MagicMock()
    plot.y2_axis.return_value = MagicMock()
    plot.z_axis.return_value = MagicMock()
    plot.x_axis.return_value = MagicMock()
    return plot


def test_empty_hints_is_noop():
    plot = _make_plot()
    apply_plot_hints(plot, PlotHints())
    plot.y_axis.return_value.set_label.assert_not_called()
    plot.y_axis.return_value.set_log.assert_not_called()
    plot.z_axis.return_value.set_label.assert_not_called()


def test_line_hints_sets_y():
    plot = _make_plot()
    hints = PlotHints(y=AxisHints(label="Bt", unit="nT", scale="linear"))
    apply_plot_hints(plot, hints)
    plot.y_axis.return_value.set_label.assert_called_once_with("Bt [nT]")
    plot.y_axis.return_value.set_log.assert_called_once_with(False)


def test_log_scale():
    plot = _make_plot()
    hints = PlotHints(y=AxisHints(unit="counts", scale="log"))
    apply_plot_hints(plot, hints)
    plot.y_axis.return_value.set_log.assert_called_once_with(True)
    plot.y_axis.return_value.set_label.assert_called_once_with("[counts]")


def test_spectrogram_hints_sets_y2_and_z():
    plot = _make_plot()
    hints = PlotHints(
        display_type="spectrogram",
        y2=AxisHints(label="Energy", unit="eV", scale="log"),
        z=AxisHints(label="flux", unit="1/(cm^2 s sr eV)", scale="log"),
    )
    apply_plot_hints(plot, hints)
    plot.y2_axis.return_value.set_label.assert_called_once_with("Energy [eV]")
    plot.y2_axis.return_value.set_log.assert_called_once_with(True)
    plot.z_axis.return_value.set_label.assert_called_once_with("flux [1/(cm^2 s sr eV)]")
    plot.z_axis.return_value.set_log.assert_called_once_with(True)


def test_none_plot_tolerated():
    apply_plot_hints(None, PlotHints(y=AxisHints(label="x")))


def test_scale_none_does_not_call_set_log():
    plot = _make_plot()
    hints = PlotHints(y=AxisHints(label="Bt"))
    apply_plot_hints(plot, hints)
    plot.y_axis.return_value.set_log.assert_not_called()


def test_missing_axis_getter_is_tolerated():
    plot = MagicMock(spec=["y_axis"])
    plot.y_axis.return_value = MagicMock()
    hints = PlotHints(
        y=AxisHints(label="Bt", scale="linear"),
        z=AxisHints(label="flux"),
    )
    apply_plot_hints(plot, hints)
    plot.y_axis.return_value.set_label.assert_called_once_with("Bt")
