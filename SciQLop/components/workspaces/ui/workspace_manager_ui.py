from PySide6.QtCore import QSize, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QApplication, QFormLayout, QTextBrowser, QLabel, QPushButton

from SciQLop.components.workspaces import WorkspaceManager, workspaces_manager_instance


class WorkspaceManagerUI(QWidget):
    workspace_loaded = Signal(str)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        wm = workspaces_manager_instance()
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

    def widget(self):
        return workspaces_manager_instance().widget()

    def open_in_browser(self):
        workspaces_manager_instance().open_in_browser()

    def wrap_qt(self, obj):
        return workspaces_manager_instance().wrap_qt(obj)
