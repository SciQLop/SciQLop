from PySide6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy, QHBoxLayout, QScrollArea, QFrame, QSplitter
from PySide6.QtCore import Qt
from SciQLop.components.welcome.sections.ExamplesView import ExamplesView
from SciQLop.components.welcome.sections.quickstart import QuickStartSection
from SciQLop.components.welcome.sections.recent_workspaces import RecentWorkspaces
from .detailed_description.detailed_description import DetailedDescription
from .card import Card
from SciQLop.core.ui import apply_size_policy

import os

__HERE__ = os.path.dirname(__file__)


class WelcomePage(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_card = None
        self.setWindowTitle("Welcome")

        sections_widget = QWidget()
        self._sections_layout = QVBoxLayout()
        sections_widget.setLayout(self._sections_layout)
        self._quick_start = apply_size_policy(QuickStartSection(), QSizePolicy.Policy.Expanding,
                                              QSizePolicy.Policy.Maximum)
        self._sections_layout.addWidget(self._quick_start)
        self._recent_workspaces = apply_size_policy(RecentWorkspaces(), QSizePolicy.Policy.Expanding,
                                                    QSizePolicy.Policy.Maximum)
        self._sections_layout.addWidget(self._recent_workspaces)
        self._examples = apply_size_policy(ExamplesView(), QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._sections_layout.addWidget(self._examples)

        self._scroll = QScrollArea()
        self._scroll.setWidget(sections_widget)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.addWidget(self._scroll)
        self._detailed_description = DetailedDescription(self)
        self._detailed_description.hide()
        self._splitter.addWidget(self._detailed_description)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 0)

        self._layout = QHBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addWidget(self._splitter)
        self.setLayout(self._layout)

        self._recent_workspaces.show_detailed_description.connect(self._show_detailed_description)
        self._examples.show_detailed_description.connect(self._show_detailed_description)

    def _unset_selected_card(self):
        if self._selected_card:
            self._selected_card.set_selected(False)
            self._selected_card = None

    def _set_selected_card(self, card: Card):
        self._unset_selected_card()
        if card:
            self._selected_card = card
            card.set_selected(True)

    def _show_detailed_description(self, card: Card):
        self._set_selected_card(card)
        if card:
            self._detailed_description.show_description(card)
        else:
            self._detailed_description.hide()
