from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QSizePolicy
from ..common import HLine, apply_size_policy, increase_font_size


class WelcomeSection(QFrame):
    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f".{self.__class__.__name__}{{border: 1px solid black; border-radius: 2px;}}")
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self._layout.addWidget(apply_size_policy(increase_font_size(QLabel(name), 1.2), QSizePolicy.Policy.Preferred,
                                                 QSizePolicy.Policy.Maximum))
        self._layout.addWidget(apply_size_policy(HLine(), QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum))
