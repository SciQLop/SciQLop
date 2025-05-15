from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QSizePolicy, QPushButton, QWidget, QSpacerItem, QTextEdit
from PySide6.QtCore import Signal, Property
from SciQLop.widgets.welcome.card import Card, FixedSizeImageWidget
from SciQLop.widgets.common.flow_layout import FlowLayout
from SciQLop.widgets.common import HLine
from SciQLop.widgets.welcome.section import WelcomeSection, CardsCollection
from typing import List
import os
from glob import glob

__HERE__ = os.path.dirname(__file__)

from SciQLop.backend.examples.example import Example
from SciQLop.backend.workspace import workspaces_manager_instance
from SciQLop.widgets.welcome.detailed_description.delegate import register_delegate


class ExampleCard(Card):
    def __init__(self, json_file: str, parent=None):
        super().__init__(parent)
        self._example = Example(json_file)
        self._refresh_ui()

    def _refresh_ui(self):
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self._layout.addWidget(FixedSizeImageWidget(self._example.image))
        self._layout.addWidget(HLine())
        self._layout.addWidget(QLabel(self._example.name))
        tags = QLabel(
            f"<font color=\"black\">Tags:</font> <font color=\"blue\">{' '.join(self._example.tags)}</font>")
        font = tags.font()
        font.setPointSize(int(font.pointSize() * 0.8))
        tags.setFont(font)
        self._layout.addWidget(tags)

    @property
    def example(self) -> Example:
        return self._example


@register_delegate(ExampleCard)
class ExampleDescriptionWidget(QFrame):

    def __init__(self, example: ExampleCard, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self._layout.addWidget(QLabel(f"Example: {example.example.name}"))
        self._description = QTextEdit()
        self._description.setReadOnly(True)
        self._description.setText(example.example.description)
        self._layout.addWidget(self._description)
        self._open_button = QPushButton("Open")
        self._open_button.clicked.connect(lambda: workspaces_manager_instance().load_example(example.example.directory))
        self._layout.addWidget(self._open_button)


class ExamplesView(WelcomeSection):

    def __init__(self, parent=None):
        super().__init__("Examples", parent)
        self._examples_list = CardsCollection()
        self._examples_list.show_detailed_description.connect(self.show_detailed_description)
        #self._examples_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._layout.addWidget(self._examples_list)
        self._layout.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding))
        self.refresh_examples()

    def refresh_examples(self):
        self._examples_list.clear()
        list(map(self._add_example, glob(os.path.join(__HERE__, "../../../examples/*/*.json"))))

    def _add_example(self, json_file: str):
        ex = ExampleCard(json_file)
        self._examples_list.add_card(ex)
