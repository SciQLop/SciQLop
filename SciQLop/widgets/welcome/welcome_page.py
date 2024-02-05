from PySide6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy, QHBoxLayout
from SciQLop.widgets.welcome.sections.ExamplesView import ExamplesView
from SciQLop.widgets.welcome.sections.quickstart import QuickStartSection
from SciQLop.widgets.welcome.sections.recent_workspaces import RecentWorkspaces
from .detailed_description.detailed_description import DetailedDescription
from .card import Card
from ..common import apply_size_policy

import os

__HERE__ = os.path.dirname(__file__)


class WelcomePage(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_card = None
        self.setWindowTitle("Welcome")
        self._sections_layout = QVBoxLayout()
        self._quick_start = apply_size_policy(QuickStartSection(), QSizePolicy.Policy.Expanding,
                                              QSizePolicy.Policy.Maximum)
        self._sections_layout.addWidget(self._quick_start)
        self._recent_workspaces = apply_size_policy(RecentWorkspaces(), QSizePolicy.Policy.Expanding,
                                                    QSizePolicy.Policy.Maximum)
        self._sections_layout.addWidget(self._recent_workspaces)
        self._examples = apply_size_policy(ExamplesView(), QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._sections_layout.addWidget(self._examples)
        self._layout = QHBoxLayout()
        self._layout.addLayout(self._sections_layout)
        self._detailed_description = DetailedDescription(self)
        self._detailed_description.hide()
        self._layout.addWidget(self._detailed_description)
        self.setLayout(self._layout)

        self._quick_start.show_detailed_description.connect(self._show_detailed_description)
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
