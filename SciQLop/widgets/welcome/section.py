from glob import glob
import os
from typing import List
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QSizePolicy, QWidget, QGridLayout, QBoxLayout, QSpacerItem
from ..common import apply_size_policy, increase_font_size
from SciQLop.backend.common import Maybe
from SciQLop.backend import sciqlop_logging
from .card import Card

log = sciqlop_logging.getLogger(__name__)

class CardsCollection(QFrame):
    _cards: List[Card]
    show_detailed_description = Signal(QWidget)
    _last_row: int = 0
    _last_col: int = 0
    _columns: int = 6

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards = []
        self._layout = QGridLayout()
        self._layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(self._layout)
        self.refresh_ui()

    def _place_card(self, card: Card):
        self._layout.addWidget(card, self._last_row, self._last_col)
        self._last_col += 1
        if self._last_col == self._columns:
            self._last_col = 0
            self._last_row += 1

    def _reset_layout(self):
        log.debug(f"Resetting layout")
        self._last_row = 0
        self._last_col = 0
        item = self._layout.takeAt(0)
        while item is not None:
            Maybe(item.widget()).deleteLater()
            del item
            item = self._layout.takeAt(0)
        self._layout.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum), 0,
                             self._columns, -1, 1)

    def add_card(self, card: Card):
        log.debug(f"Adding card {card}")
        self._cards.append(card)
        self._place_card(card)
        card.clicked.connect(lambda: self.show_detailed_description.emit(card))

    def refresh_ui(self):
        log.debug(f"Refreshing UI")
        self._reset_layout()
        for card in self._cards:
            self._place_card(card)

    def clear(self):
        log.debug(f"Clearing cards")
        self._cards = []
        self.refresh_ui()

    def mousePressEvent(self, event):
        if not self.childAt(event.position().toPoint()):
            list(map(lambda c: c.set_selected(False), self._cards))
            self.show_detailed_description.emit(None)
        super().mousePressEvent(event)


class WelcomeSection(QFrame):
    show_detailed_description = Signal(QWidget)

    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self._name_lbl = apply_size_policy(increase_font_size(QLabel(name), 1.2), QSizePolicy.Policy.Expanding,
                                           QSizePolicy.Policy.Maximum)
        self._layout.addWidget(self._name_lbl)
        #self._layout.addWidget(apply_size_policy(HLine(), QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum))
