from PySide6.QtWidgets import QFrame, QVBoxLayout, QSizePolicy
from .ExamplesView import ExamplesView
from .quickstart import QuickStartSection
from .recent_workspaces import RecentWorkspaces
from ..common import apply_size_policy
import os

__HERE__ = os.path.dirname(__file__)


class WelcomePage(QFrame):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome")
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self._layout.addWidget(
            apply_size_policy(QuickStartSection(), QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum))
        self._layout.addWidget(apply_size_policy(RecentWorkspaces(), QSizePolicy.Policy.Expanding,
                                                 QSizePolicy.Policy.Maximum))
        self._layout.addWidget(apply_size_policy(ExamplesView(), QSizePolicy.Policy.Expanding,
                                                 QSizePolicy.Policy.Expanding))
