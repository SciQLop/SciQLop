from glob import glob
import os
from typing import List
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QSizePolicy
from ..common import HLine, apply_size_policy, increase_font_size
from ..common.flow_layout import FlowLayout
from .card import Card


class CardsCollection(QFrame):
    _cards: List[Card] = []

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = FlowLayout(margin=10, hspacing=10, vspacing=10)
        self.setLayout(self._layout)
        self.refresh_ui()

    def add_card(self, card: Card):
        self._cards.append(card)
        self._layout.addWidget(card)

    def refresh_ui(self):
        self._layout.clear()
        for card in self._cards:
            self._layout.addWidget(card)

    def clear(self):
        self._cards.clear()
        self.refresh_ui()


class WelcomeSection(QFrame):
    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f".{self.__class__.__name__}{{border: 1px solid black; border-radius: 2px;}}")
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self._layout.addWidget(apply_size_policy(increase_font_size(QLabel(name), 1.2), QSizePolicy.Policy.Preferred,
                                                 QSizePolicy.Policy.Maximum))
        self._layout.addWidget(apply_size_policy(HLine(), QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum))
