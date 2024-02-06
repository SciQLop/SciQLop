from PySide6.QtCore import QObject, Signal, Slot, Property, QModelIndex, QPersistentModelIndex, Qt, QSize, QRect
from PySide6.QtWidgets import QWidget, QFormLayout, QLabel, QFrame, QComboBox, QStyledItemDelegate, \
    QStyleOptionViewItem, QStyle
from PySide6.QtGui import QPainter
from typing import Dict, Callable, Any, Optional, Union
from SciQLop.widgets.settings_delegates import register_delegate
from SciQLopPlots import QCPColorGradient, QCPRange
from .colormap_graph import ColorMapGraph
from ...common import expand_size


class ColorGradientPreview(QStyledItemDelegate):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent=parent)
        self._h_margin = 5
        self._v_margin = 5

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: Union[QModelIndex, QPersistentModelIndex]):
        if index.isValid():
            data = index.data(Qt.UserRole)
            if isinstance(data, QCPColorGradient.GradientPreset):
                gradient = QCPColorGradient(data)
                sh = self._gradient_size_hint()
                tx = self._text_size_hint(index.data())
                rect: QRect = option.rect
                if option.state & QStyle.StateFlag.State_Selected == QStyle.StateFlag.State_Selected:
                    painter.fillRect(rect, option.palette.highlight())
                rect.adjust(+5, 0, -5, 0)
                painter.save()
                painter.translate(rect.x(), rect.y() + tx.height())
                if option.state & QStyle.StateFlag.State_Selected == QStyle.StateFlag.State_Selected:
                    painter.setPen(option.palette.highlightedText().color())
                painter.drawText(0, 0, index.data())
                painter.restore()
                painter.resetTransform()
                painter.save()
                painter.translate(rect.x() + tx.width() + self._h_margin, rect.y())
                width = rect.width() - tx.width() - self._h_margin - self._h_margin
                for i in range(width):
                    painter.setPen(gradient.color(i / width, QCPRange(0, 1)))
                    painter.drawLine(i, 0, i, sh.height())
                painter.restore()
            else:
                super().paint(painter, option, index)
        else:
            super().paint(painter, option, index)

    def _text_size_hint(self, text: str) -> QSize:
        return expand_size(self.parent().fontMetrics().size(0, text), self._h_margin, self._v_margin)

    def _gradient_size_hint(self) -> QSize:
        return expand_size(self._text_size_hint("00000000"), self._h_margin, self._v_margin)

    def sizeHint(self, option: QStyleOptionViewItem, index: Union[QModelIndex, QPersistentModelIndex]) -> QSize:
        text = self._text_size_hint(index.data())
        return QSize(text.width() + self._gradient_size_hint().width(), self._gradient_size_hint().height())


class ColorGradientChooser(QComboBox):
    refresh_plot = Signal()

    def __init__(self, graph: ColorMapGraph, parent: Optional[QWidget] = None):
        super().__init__(parent=parent)
        self._graph = graph
        self.addItem("current", QCPColorGradient(graph.scale))
        for name in QCPColorGradient.GradientPreset.__dict__:
            if name.startswith("gp"):
                self.addItem(name, getattr(QCPColorGradient.GradientPreset, name))
        self.setCurrentText("current")
        self.setItemDelegate(ColorGradientPreview(self))
        self.currentTextChanged.connect(self._set_gradient)

    @Slot(str)
    def _set_gradient(self, gradient_name: str):
        if gradient_name != "current":
            self._graph.set_gradient(QCPColorGradient(getattr(QCPColorGradient.GradientPreset, gradient_name)))


@register_delegate(ColorMapGraph)
class ColormapGraphSettings(QWidget):
    def __init__(self, plot: ColorMapGraph):
        QWidget.__init__(self)
        self._plot = plot
        self._layout = QFormLayout()
        self.setLayout(self._layout)
        gradient_chooser = ColorGradientChooser(plot)
        self._layout.addRow("Color gradient", gradient_chooser)
        gradient_chooser.refresh_plot.connect(self._plot.replot)
