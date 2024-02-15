from glob import glob
import os
from typing import List
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QSizePolicy, QWidget
from SciQLop.widgets.common import HLine, apply_size_policy, increase_font_size
from SciQLop.widgets.common.flow_layout import FlowLayout
from .delegate import make_delegate_for


class DetailedDescription(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout()
        self._description_widget = None
        self.setLayout(self._layout)
        self._layout.addWidget(
            apply_size_policy(increase_font_size(QLabel("Detailed description"), 1.2), QSizePolicy.Policy.Preferred,
                              QSizePolicy.Policy.Maximum))
        self._layout.addWidget(apply_size_policy(HLine(), QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum))

    @Slot(QWidget)
    def show_description(self, widget: QWidget):
        if self._description_widget:
            self._layout.removeWidget(self._description_widget)
            self._description_widget.deleteLater()
        if widget:
            self._description_widget = make_delegate_for(widget)
            if self._description_widget:
                self._layout.addWidget(self._description_widget)
                self.show()
