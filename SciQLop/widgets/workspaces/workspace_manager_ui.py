from PySide6.QtCore import QSize, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QApplication, QFormLayout, QTextBrowser, QLabel, QPushButton

from SciQLop.backend.workspace import WorkspaceManager, workspaces_manager_instance


class WorkspaceManagerUI(QWidget):
    jupyterlab_started = Signal(str)
    workspace_loaded = Signal(str)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        wm = workspaces_manager_instance()
        wm.jupyterlab_started.connect(self.jupyterlab_started)
        wm.workspace_loaded.connect(lambda w: self.workspace_loaded.emit(w.name))
        self.setWindowTitle("Workspace Manager")
        self.setup_ui()

    def setup_ui(self):
        pass

    def pushVariables(self, variable_dict):
        workspaces_manager_instance().push_variables(variable_dict)

    def start(self):
        workspaces_manager_instance().start()

    def quit(self):
        workspaces_manager_instance().quit()

    def new_qt_console(self):
        workspaces_manager_instance().new_qt_console()
