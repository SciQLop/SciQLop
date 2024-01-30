from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QSizePolicy
from PySide6.QtCore import Signal
from .card import Card, ImageWidget
from ..common.flow_layout import FlowLayout
from ..common import HLine
from .section import WelcomeSection
from typing import List
import os
from glob import glob

__HERE__ = os.path.dirname(__file__)

from ...backend.examples.example import Example
from ...backend.workspace import workspaces_manager_instance


class ExampleCard(Card):
    open_example = Signal(str)

    def __init__(self, json_file: str, parent=None):
        super().__init__(parent)
        self._example = Example(json_file)
        self.clicked.connect(lambda: self.open_example.emit(self._example.path))
        self._refresh_ui()

    def _refresh_ui(self):
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        if not self._example.is_valid:
            self._layout.addWidget(QLabel(f"Error: {self._example.json_file} not found"))
        else:
            self._layout.addWidget(ImageWidget(self._example.image))
            self._layout.addWidget(HLine())
            self._layout.addWidget(QLabel(self._example.name))
            tags = QLabel(
                f"<font color=\"black\">Tags:</font> <font color=\"blue\">{' '.join(self._example.tags)}</font>")
            font = tags.font()
            font.setPointSize(int(font.pointSize() * 0.8))
            tags.setFont(font)
            self._layout.addWidget(tags)


class ExamplesList(QFrame):
    _cards: List[ExampleCard] = []

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = FlowLayout(margin=10, hspacing=10, vspacing=10)
        self.setLayout(self._layout)
        self.refresh_ui()

    @staticmethod
    def find_examples() -> List[str]:
        examples = glob(os.path.join(__HERE__, "../../examples/*/*.json"))
        return examples

    def _register_example(self, json_file: str):
        ex = ExampleCard(json_file)
        self._cards.append(ex)
        ex.open_example.connect(workspaces_manager_instance().load_example)

    def load_examples(self):
        list(map(self._register_example, self.find_examples()))

    def refresh_ui(self):
        self.load_examples()
        self._layout.clear()
        for card in self._cards:
            self._layout.addWidget(card)


class ExamplesView(WelcomeSection):
    def __init__(self, parent=None):
        super().__init__("Examples", parent)
        self._examples_list = ExamplesList()
        self._examples_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._layout.addWidget(self._examples_list)
