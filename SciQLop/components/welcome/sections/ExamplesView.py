from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QSizePolicy, QPushButton, QSpacerItem, QTextEdit
from SciQLop.components.welcome.card import Card, FixedSizeImageWidget
from SciQLop.core.ui import HLine
from SciQLop.components.welcome.section import WelcomeSection, CardsCollection
import os
from glob import glob

__HERE__ = os.path.dirname(__file__)

from SciQLop.components.workspaces.backend.example import Example
from SciQLop.components.workspaces.backend.workspaces_manager import WorkspaceManager, workspaces_manager_instance
from SciQLop.components.welcome.detailed_description.delegate import register_delegate


class ExampleCard(Card):
    def __init__(self, json_file: str, parent=None):
        super().__init__(parent)
        self._example = Example(json_file)
        self._refresh_ui()
        self.double_clicked.connect(self._open_example)

    def _open_example(self):
        manager = workspaces_manager_instance()
        ws_dir = manager.workspace.workspace_dir
        WorkspaceManager.add_example_to_workspace(self._example.directory, ws_dir)

    def _refresh_ui(self):
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self._layout.addWidget(FixedSizeImageWidget(self._example.image))
        self._layout.addWidget(HLine())
        self._layout.addWidget(QLabel(self._example.name))
        tags = QLabel(
            f"Tags: <a style=\"text-decoration:none\">{' '.join(self._example.tags)}</a>")
        font = tags.font()
        font.setPointSize(int(font.pointSize() * 0.8))
        tags.setFont(font)
        self._layout.addWidget(tags)

    def filter_text(self) -> str:
        return f"{self._example.name} {' '.join(self._example.tags)}"

    @property
    def example(self) -> Example:
        return self._example


@register_delegate(ExampleCard, title="Example details")
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
        self._open_button.clicked.connect(
            lambda: WorkspaceManager.add_example_to_workspace(
                example.example.directory,
                workspaces_manager_instance().workspace.workspace_dir,
            )
        )
        self._layout.addWidget(self._open_button)


class ExamplesView(WelcomeSection):

    def __init__(self, parent=None):
        super().__init__("Examples", filterable=True, parent=parent)
        self._examples_list = CardsCollection()
        self._examples_list.show_detailed_description.connect(self.show_detailed_description)
        self.add_filterable_collection(self._examples_list)
        # self._examples_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._layout.addWidget(self._examples_list)
        self._layout.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding))
        self.refresh_examples()

    def refresh_examples(self):
        self._examples_list.clear()
        list(map(self._add_example, glob(os.path.join(__HERE__, "../../../examples/*/*.json"))))

    def _add_example(self, json_file: str):
        ex = ExampleCard(json_file)
        self._examples_list.add_card(ex)
