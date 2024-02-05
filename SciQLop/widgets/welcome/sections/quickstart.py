from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget, QLabel, QSizePolicy
from PySide6.QtCore import Slot
from PySide6.QtGui import QPixmap, QIcon
from typing import List, Callable, Union
from SciQLop.widgets.welcome.card import Card, FixedSizeImageWidget
from SciQLop.widgets.common.flow_layout import FlowLayout
from SciQLop.widgets.common import HLine
from SciQLop.backend.sciqlop_application import sciqlop_app
from SciQLop.widgets.welcome.section import WelcomeSection, CardsCollection


class ShortcutCard(Card):
    def __init__(self, name: str, description: str, icon: QIcon, callback: Callable, parent=None):
        super().__init__(parent, width=100, height=120, tooltip=description)
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self._layout.addWidget(FixedSizeImageWidget(icon=icon, width=80, height=80))
        self._layout.addWidget(QLabel(name))
        self.clicked.connect(lambda: callback())


class Shortcuts(QFrame):
    _cards: List[ShortcutCard] = []

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = FlowLayout(margin=10, hspacing=10, vspacing=10)
        self.setLayout(self._layout)
        self.refresh_ui()

    def add_card(self, card: ShortcutCard):
        self._cards.append(card)
        self._layout.addWidget(card)

    def refresh_ui(self):
        self._layout.clear()
        for card in self._cards:
            self._layout.addWidget(card)


class QuickStartSection(WelcomeSection):
    def __init__(self, parent=None):
        super().__init__("Quick start", parent)
        self._shortcuts = CardsCollection()
        #self._shortcuts.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._layout.addWidget(self._shortcuts)
        list(map(self._add_shortcut, sciqlop_app().quickstart_shortcuts))
        sciqlop_app().quickstart_shortcuts_added.connect(self._add_shortcut)

    @Slot()
    def _add_shortcut(self, name: str):
        self.add_shortcut(**sciqlop_app().quickstart_shortcut(name))

    @Slot()
    def add_shortcut(self, name: str, description: str, icon: QIcon, callback: Callable):
        self._shortcuts.add_card(ShortcutCard(name, description, icon, callback))
