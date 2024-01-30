from PySide6.QtCore import QSize, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QApplication, QFormLayout, QTextBrowser, QLabel, QPushButton

from SciQLop.backend.workspace import WorkspaceManager as BackendWorkspaceManager


class WorkspaceManagerUI(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._workspace_manager = BackendWorkspaceManager()
        self.setWindowTitle("Workspace Manager")
        self.setup_ui()

    def setup_ui(self):
        pass

    def pushVariables(self, variable_dict):
        self._workspace_manager.push_variables(variable_dict)

    def start(self):
        self._workspace_manager.start()

    def quit(self):
        self._workspace_manager.quit()
