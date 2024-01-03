from PySide6.QtCore import QObject, Signal, Slot, Property
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFormLayout, QComboBox, QFrame, QCheckBox
from typing import List, Optional
from SciQLop.widgets.common import Container
from SciQLop.widgets.settings_delegates import register_delegate
from SciQLop.widgets.plots.time_series_plot import TimeSeriesPlot
from SciQLopPlots import SciQLopPlot, QCPAxis, QCPAxisTickerLog, QCPAxisTicker, QCPAxisTickerFixed, QCPAxisTickerText


@register_delegate(QCPAxis)
class QCPAxisSettings(QWidget):
    refresh_plot = Signal()

    def __init__(self, axis: QCPAxis, allow_scale_type: bool = True):
        QWidget.__init__(self)
        self._axis = axis
        self._layout = QFormLayout()
        self.setLayout(self._layout)
        if allow_scale_type:
            scale_type = QComboBox()
            scale_type.addItems(["Linear", "Logarithmic"])
            scale_type.setCurrentText("Linear" if axis.scaleType() == QCPAxis.stLinear else "Logarithmic")
            self._layout.addRow("Scale type", scale_type)
            scale_type.currentTextChanged.connect(self._set_scale_type)
        self._show_axis = QCheckBox()
        self._layout.addRow("Show axis", self._show_axis)
        self._show_axis.setChecked(axis.visible())
        self._show_axis.toggled.connect(self._toggle_axis)

    @Slot(bool)
    def _toggle_axis(self, checked: bool):
        self._axis.setVisible(checked)
        self.refresh_plot.emit()

    @Slot(str)
    def _set_scale_type(self, scale_type: str):
        if scale_type == "Linear":
            self._axis.setScaleType(QCPAxis.stLinear)
            self._axis.setTicker(QCPAxisTicker())
            self.refresh_plot.emit()
        elif scale_type == "Logarithmic":
            self._axis.setScaleType(QCPAxis.stLogarithmic)
            self._axis.setTicker(QCPAxisTickerLog())
            self.refresh_plot.emit()


@register_delegate(TimeSeriesPlot)
class TimeSeriesPlotSettings(QWidget):
    def __init__(self, plot: TimeSeriesPlot):
        QWidget.__init__(self)
        self._plot = plot
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        x_axis_settings = QCPAxisSettings(plot.xAxis, allow_scale_type=False)
        self._layout.addWidget(Container("X axis", x_axis_settings))
        x_axis_settings.refresh_plot.connect(self._plot.replot)
        y_axis_settings = QCPAxisSettings(plot.yAxis)
        self._layout.addWidget(Container("Y axis", y_axis_settings))
        y_axis_settings.refresh_plot.connect(self._plot.replot)
