from PySide6.QtWidgets import QVBoxLayout, QLabel, QSizePolicy, QWidget, QFrame, QPushButton, QFormLayout, QLineEdit, \
    QTextEdit
from PySide6.QtCore import QFileSystemWatcher, Slot, Signal, Property
from SciQLop.widgets.welcome.card import Card, FixedSizeImageWidget, ImageSelector
from SciQLop.backend.workspace import workspaces_manager_instance, WorkspaceSpecFile, WORKSPACES_DIR_CONFIG_ENTRY
from SciQLop.backend.common import ensure_dir_exists
from SciQLop.widgets.welcome.section import WelcomeSection, CardsCollection
from SciQLop.widgets.welcome.detailed_description.delegate import register_delegate
import os
import shutil


class WorkSpaceCard(Card):
    def __init__(self, workspace: WorkspaceSpecFile, parent=None):
        super().__init__(parent, width=160, height=180)
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self._thumbnail = FixedSizeImageWidget(image_path=str(os.path.join(workspace.directory, workspace.image)),
                                               width=140,
                                               height=140)
        self._layout.addWidget(self._thumbnail)
        self._name = QLabel(workspace.name)
        self._layout.addWidget(self._name)
        self._workspace = workspace
        self._refresh_tooltip()

    def _refresh_tooltip(self):
        self.tooltip = f"""
<b>{self._workspace.name}</b>
<br>
{self._workspace.description}
<br>
<i>Last used: {self._workspace.last_used}</i>
        """

    @property
    def workspace(self) -> WorkspaceSpecFile:
        return self._workspace

    @Property(str)
    def description(self):
        return self._workspace.description

    @description.setter
    def description(self, value):
        self._workspace.description = value
        self._refresh_tooltip()

    @property
    def name(self):
        return self._workspace.name

    @name.setter
    def name(self, value):
        self._workspace.name = value
        self._name.setText(value)
        self._refresh_tooltip()

    @Property(str)
    def image(self):
        return self._workspace.image

    @image.setter
    def image(self, value: str):
        if os.path.isfile(os.path.join(self._workspace.directory, self._workspace.image)):
            os.remove(os.path.join(self._workspace.directory, self._workspace.image))
        destination = str(os.path.join(self._workspace.directory, os.path.basename(value)))
        shutil.copy(value, destination)
        self._workspace.image = os.path.basename(value)
        self._thumbnail.set_image(destination)


@register_delegate(WorkSpaceCard)
class WorkspaceDescriptionWidget(QFrame):

    def __init__(self, workspace: WorkSpaceCard, parent=None):
        super().__init__(parent)
        self._workspace = workspace
        self._layout = QFormLayout()
        self.setLayout(self._layout)
        self._name = QLineEdit(workspace.workspace.name)
        self._name.textChanged.connect(lambda x: setattr(self._workspace, "name", x))
        self._layout.addRow(QLabel("Name"), self._name)
        self._layout.addRow(QLabel("Last used"), QLabel(workspace.workspace.last_used))
        self._layout.addRow(QLabel("Last modified"), QLabel(workspace.workspace.last_modified))
        self._image = ImageSelector(
            current_image=str(os.path.join(workspace.workspace.directory, workspace.workspace.image)))
        self._image.image_selected.connect(lambda x: setattr(self._workspace, "image", x))
        self._layout.addRow(QLabel("Image"), self._image)
        self._description = QTextEdit(workspace.workspace.description)
        self._description.textChanged.connect(lambda x: setattr(self._workspace, "description", x))
        self._layout.addRow(QLabel("Description"), self._description)
        self._open_button = QPushButton("Open workspace")
        self._open_button.setMinimumHeight(40)
        self._open_button.clicked.connect(
            lambda: workspaces_manager_instance().load_workspace(workspace.workspace))
        self._layout.addWidget(self._open_button)


class RecentWorkspaces(WelcomeSection):
    def __init__(self, parent=None):
        super().__init__("Recent workspaces", parent)
        self._workspaces = CardsCollection()
        self._workspaces.show_detailed_description.connect(self.show_detailed_description)
        # self._workspaces.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._layout.addWidget(self._workspaces)
        self.refresh_workspaces()
        self._watcher = QFileSystemWatcher()
        ensure_dir_exists(WORKSPACES_DIR_CONFIG_ENTRY.get())
        self._watcher.addPath(WORKSPACES_DIR_CONFIG_ENTRY.get())
        self._watcher.directoryChanged.connect(self.refresh_workspaces)

    @Slot()
    def refresh_workspaces(self):
        self._workspaces.clear()
        wm = workspaces_manager_instance()
        list(map(self._add_workspace, sorted(wm.list_workspaces(), key=lambda x: x.last_used, reverse=True)))

    def _add_workspace(self, workspace: WorkspaceSpecFile):
        card = WorkSpaceCard(workspace)
        # card.clicked.connect(lambda: workspaces_manager_instance().load_workspace(workspace))
        self._workspaces.add_card(card)
