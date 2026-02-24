from PySide6.QtCore import Slot
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListView, QLineEdit, QPushButton, QHBoxLayout
from PySide6.QtGui import QIcon, Qt


class SettingsCategories(QListView):
    def __init__(self, parent=None):
        super().__init__(parent)

class SettingsLeftPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filter settings...")
        self.layout.addWidget(self.filter)
        self.categories_list = QListView()
        self.categories_list.setMaximumWidth(200)
        self.layout.addWidget(self.categories_list)

class SettingsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.title = QLabel("Settings")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.title)

        self.categories_list = QListView()
        self.categories_list.setMaximumWidth(200)
        self.layout.addWidget(self.categories_list)
