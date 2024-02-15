from PySide6.QtWidgets import QFrame, QWidget, QSizePolicy, QLabel, QVBoxLayout
from PySide6.QtCore import QSize

from .tree_view import TreeView


class HLine(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)
        #self.setStyleSheet("background-color: #ccc;")


class Container(QFrame):
    def __init__(self, label: str, widget: QWidget):
        super().__init__()
        #self.setStyleSheet("Container { border: 1px solid black; border-radius: 2px; }")
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self._layout.addWidget(QLabel(label))
        self._layout.addWidget(widget)


def apply_size_policy(widget: QWidget, horizontal: QSizePolicy.Policy, vertical: QSizePolicy.Policy) -> QWidget:
    widget.setSizePolicy(horizontal, vertical)
    return widget


def expand_size(size: QSize, horizontal: int, vertical: int) -> QSize:
    return QSize(size.width() + (2 * horizontal), size.height() + (2 * vertical))


def increase_font_size(label: QLabel, factor: float = 1.2) -> QLabel:
    font = label.font()
    font.setPointSizeF(font.pointSizeF() * factor)
    label.setFont(font)
    return label
