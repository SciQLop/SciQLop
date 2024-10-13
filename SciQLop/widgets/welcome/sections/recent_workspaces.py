from PySide6.QtWidgets import QVBoxLayout, QLabel, QSizePolicy, QWidget, QFrame, QPushButton, QFormLayout, QLineEdit, \
    QTextEdit, QMessageBox
from PySide6.QtGui import QIcon
from PySide6.QtCore import QFileSystemWatcher, Slot, Signal, Property, QTimer, Qt
from SciQLop.widgets.welcome.card import Card, FixedSizeImageWidget, ImageSelector
from SciQLop.backend.workspace import workspaces_manager_instance, WorkspaceSpecFile, WORKSPACES_DIR_CONFIG_ENTRY
from SciQLop.backend.common import ensure_dir_exists
from SciQLop.backend import sciqlop_logging
from SciQLop.widgets.welcome.section import WelcomeSection, CardsCollection
from SciQLop.widgets.welcome.detailed_description.delegate import register_delegate
from typing import Optional
import os
import shutil
import humanize

log = sciqlop_logging.getLogger(__name__)

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
        self.setProperty("default_workspace", workspace.default_workspace)

    def _refresh_tooltip(self):
        self.tooltip = f"""
<b>{self._workspace.name}</b>
<br>
{self._workspace.description}
<br>
<i>Last used: {humanize.naturaldate(self._workspace.last_used)}</i>
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
        if os.path.isfile(os.path.join(self._workspace.directory, value)):
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
        self._workspace: Optional[WorkSpaceCard] = workspace
        self._layout = QFormLayout()
        self.setLayout(self._layout)
        self._name = QLineEdit(workspace.workspace.name)
        self._name.setEnabled(not workspace.workspace.default_workspace)
        self._name.textChanged.connect(lambda x: setattr(self._workspace, "name", x))
        self._layout.addRow(QLabel("Name"), self._name)
        self._layout.addRow(QLabel("Last used"), QLabel(humanize.naturaldate(workspace.workspace.last_used)))
        self._layout.addRow(QLabel("Last modified"), QLabel(humanize.naturaldate(workspace.workspace.last_modified)))
        self._image = ImageSelector(
            current_image=str(os.path.join(workspace.workspace.directory, workspace.workspace.image)))
        self._image.setEnabled(not workspace.workspace.default_workspace)
        self._image.image_selected.connect(lambda x: setattr(self._workspace, "image", x))
        self._layout.addRow(QLabel("Image"), self._image)
        self._description = QTextEdit(workspace.workspace.description)
        self._description.setEnabled(not workspace.workspace.default_workspace)
        self._description.textChanged.connect(lambda x: setattr(self._workspace, "description", x))
        self._layout.addRow(QLabel("Description"), self._description)
        if not workspaces_manager_instance().has_workspace:
            self._open_button = QPushButton("Open workspace")
            self._open_button.setIcon(QIcon("://icons/theme/folder_open.png"))
            self._open_button.setMinimumHeight(40)
            self._open_button.clicked.connect(self._open_workspace)
            self._layout.addWidget(self._open_button)
        self._duplicate_button = QPushButton("Duplicate workspace")
        self._duplicate_button.setIcon(QIcon("://icons/theme/folder_copy.png"))
        self._layout.addWidget(self._duplicate_button)
        self._duplicate_button.clicked.connect(self._duplicate_workspace)
        if not workspace.workspace.default_workspace:
            self._delete_button = QPushButton("Delete workspace")
            self._delete_button.setIcon(QIcon("://icons/theme/delete.png"))
            self._layout.addWidget(self._delete_button)
            self._delete_button.clicked.connect(self._delete_workspace)
            self._dialog = None

    def _open_workspace(self):
        workspaces_manager_instance().load_workspace(self._workspace.workspace)
        self._open_button.setEnabled(False)

    def _delete_workspace(self):
        if self._dialog:
            self._dialog.deleteLater()
            self._dialog = None
        dialog = QMessageBox()
        dialog.setText(f"Are you sure you want to delete the workspace {self._workspace.workspace.name}?")
        dialog.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        dialog.setDefaultButton(QMessageBox.StandardButton.No)
        dialog.finished.connect(self._do_delete)
        self._dialog = dialog
        dialog.open()

    def _duplicate_workspace(self):
        workspaces_manager_instance().duplicate_workspace(self._workspace.workspace.directory, background=True)

    @Slot(object)
    def _do_delete(self, button: QMessageBox.StandardButton = QMessageBox.StandardButton.No):
        if button == QMessageBox.StandardButton.Yes:
            directory = self._workspace.workspace.directory
            self._workspace = None
            workspaces_manager_instance().delete_workspace(directory)
        if self._dialog:
            self._dialog.close()
            self._dialog.deleteLater()
            self._dialog = None


class RecentWorkspaces(WelcomeSection):
    def __init__(self, parent=None):
        super().__init__("Recent workspaces", parent)
        self._workspaces = CardsCollection()
        self._workspaces.show_detailed_description.connect(self.show_detailed_description)
        self._layout.addWidget(self._workspaces)
        self.refresh_workspaces()
        self._watcher = QFileSystemWatcher()
        ensure_dir_exists(WORKSPACES_DIR_CONFIG_ENTRY.get())
        self._watcher.addPath(WORKSPACES_DIR_CONFIG_ENTRY.get())
        self._watcher.directoryChanged.connect(self.refresh_workspaces)

    @Slot()
    def refresh_workspaces(self):
        log.debug("Refreshing workspaces")
        self.show_detailed_description.emit(None)
        self._workspaces.clear()
        wm = workspaces_manager_instance()
        list(map(self._add_workspace, sorted(wm.list_workspaces(), key=lambda x: x.last_used, reverse=True)))

    def _add_workspace(self, workspace: WorkspaceSpecFile):
        card = WorkSpaceCard(workspace)
        self._workspaces.add_card(card)
