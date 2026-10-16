"""The scene section of a scene plot's inspector: the frame it is drawn in."""
from PySide6.QtWidgets import QComboBox, QFormLayout, QWidget

from .scene_plot import frames_of


def frame_picker(scene_plot, parent: QWidget) -> QWidget:
    widget = QWidget(parent)
    combo = QComboBox(widget)
    combo.addItems(frames_of(scene_plot._resolved))
    combo.setCurrentText(scene_plot.scene.frame)
    combo.currentTextChanged.connect(scene_plot.set_frame)
    layout = QFormLayout(widget)
    layout.addRow("Frame", combo)
    return widget
