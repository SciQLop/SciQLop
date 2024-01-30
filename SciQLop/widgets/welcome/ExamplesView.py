from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget, QLabel, QSizePolicy
from PySide6.QtCore import Slot, Signal
from .card import Card, ImageWidget
from ..common.flow_layout import FlowLayout
from ...backend.common.dataclasses import from_json, to_json
from ..common import HLine
from .section import WelcomeSection
from dataclasses import dataclass, field
from typing import List
import os
import json
from glob import glob

__HERE__ = os.path.dirname(__file__)


class Example:
    @dataclass
    class ExampleSpec:
        name: str = field(default_factory=str)
        description: str = field(default_factory=str)
        image: str = field(default_factory=str)
        tags: List[str] = field(default_factory=list)
        notebook: str = field(default_factory=str)
        valid: bool = False

        def __init__(self, json_file: str):
            from_json(self, open(json_file, 'r').read())
            if self.name is None:
                self.valid = False
            else:
                self.valid = True

    def __init__(self, json_file: str):
        self._example_spec = Example.ExampleSpec(json_file)
        self._json_file = json_file
        self._path = os.path.dirname(json_file)

    @property
    def name(self):
        return self._example_spec.name

    @property
    def description(self):
        return self._example_spec.description

    @property
    def image(self):
        return os.path.join(self._path, self._example_spec.image)

    @property
    def path(self):
        return self._path

    @property
    def json_file(self):
        return self._json_file

    @property
    def tags(self):
        return self._example_spec.tags

    @property
    def is_valid(self):
        return self._example_spec.valid

    @property
    def notebook(self):
        return os.path.join(self._path, self._example_spec.notebook)


class ExampleCard(Card):
    open_example = Signal(str)

    def __init__(self, json_file: str, parent=None):
        super().__init__(parent)
        self._example = Example(json_file)
        self.clicked.connect(lambda: self.open_example.emit(self._example.notebook))
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

    def find_examples(self) -> List[str]:
        examples = glob(os.path.join(__HERE__, "../../examples/*/*.json"))
        return examples

    def load_examples(self):
        examples = self.find_examples()
        self._cards = [ExampleCard(example) for example in examples]

    def add_card(self, card: ExampleCard):
        self._cards.append(card)
        self._layout.addWidget(card)

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
