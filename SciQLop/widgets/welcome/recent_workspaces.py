from PySide6.QtWidgets import QVBoxLayout, QLabel, QSizePolicy
from PySide6.QtCore import QFileSystemWatcher, Slot
from .card import Card, ImageWidget
from SciQLop.backend.workspace import workspaces_manager_instance, WorkspaceSpecFile, WORKSPACES_DIR_CONFIG_ENTRY
from .section import WelcomeSection, CardsCollection
import os


class WorkSpaceCard(Card):
    def __init__(self, name: str, description: str, image: str, last_used: str, parent=None):
        super().__init__(parent, width=100, height=120, tooltip=f"""
<b>{name}</b>
<br>
{description}
<br>
<i>Last used: {last_used}</i>
        """)
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self._layout.addWidget(ImageWidget(image_path=image, width=80, height=80))
        self._layout.addWidget(QLabel(name))


class RecentWorkspaces(WelcomeSection):
    def __init__(self, parent=None):
        super().__init__("Recent workspaces", parent)
        self._workspaces = CardsCollection()
        self._workspaces.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._layout.addWidget(self._workspaces)
        self.refresh_workspaces()
        self._watcher = QFileSystemWatcher()
        self._watcher.addPath(WORKSPACES_DIR_CONFIG_ENTRY.get())
        self._watcher.directoryChanged.connect(self.refresh_workspaces)

    @Slot(str)
    def refresh_workspaces(self):
        self._workspaces.clear()
        wm = workspaces_manager_instance()
        list(map(self._add_workspace, sorted(wm.list_workspaces(), key=lambda x: x.last_used, reverse=True)))

    def _add_workspace(self, workspace: WorkspaceSpecFile):
        card = WorkSpaceCard(
            workspace.name,
            workspace.description,
            str(os.path.join(workspace.directory, workspace.image)),
            workspace.last_used
        )
        card.clicked.connect(lambda: workspaces_manager_instance().load_workspace(workspace))
        self._workspaces.add_card(card)
