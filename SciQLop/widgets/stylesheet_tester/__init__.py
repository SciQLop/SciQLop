from PySide6.QtWidgets import QWidget, QComboBox, QPushButton, QLabel, QLineEdit, QGridLayout, QTabWidget, QTreeView, \
    QListView, QFileSystemModel, QMainWindow, QMenu, QCheckBox, QRadioButton, QSlider, QSpinBox, QDoubleSpinBox, \
    QProgressBar, QDial, QCalendarWidget, QDateEdit, QTimeEdit, QDateTimeEdit, QPlainTextEdit, QTextEdit, \
    QScrollArea, QSplitter, QStackedWidget, QToolBox, QTabBar, QToolButton, QToolBar, QStatusBar, QMenuBar

from PySide6.QtCore import QStringListModel

from SciQLop.backend.sciqlop_application import sciqlop_app, sciqlop_event_loop
from SciQLop import resources
import platform, os



class ControlsPan(QWidget):
    def __init__(self, parent=None):
        super(ControlsPan, self).__init__(parent)

        grid = QGridLayout()
        self.setLayout(grid)

        self.label = QLabel("This is a label")
        grid.addWidget(self.label, 0, 0)

        self.combo = QComboBox()
        self.combo.addItems(["item1", "item2", "item3"])
        grid.addWidget(self.combo, 0, 1)

        self.button = QPushButton("This is a button")
        grid.addWidget(self.button, 1, 0)

        self.disabled_button = QPushButton("This is a disabled button")
        self.disabled_button.setEnabled(False)
        grid.addWidget(self.disabled_button, 1, 1)

        self.edit = QLineEdit("This is a line edit")
        grid.addWidget(self.edit, 1, 2)

        self.checkbox = QCheckBox("This is a checkbox")
        grid.addWidget(self.checkbox, 2, 0)

        self.radio = QRadioButton("This is a radio button")
        grid.addWidget(self.radio, 2, 1)

        self.slider = QSlider()
        grid.addWidget(self.slider, 3, 0)

        self.spin = QSpinBox()
        grid.addWidget(self.spin, 3, 1)

        self.dspin = QDoubleSpinBox()
        grid.addWidget(self.dspin, 4, 0)

        self.progress = QProgressBar()
        self.progress.setValue(50)
        grid.addWidget(self.progress, 4, 1)

        self.dial = QDial()
        grid.addWidget(self.dial, 5, 0)


class ViewsPan(QWidget):
    def __init__(self, parent=None):
        super(ViewsPan, self).__init__(parent)

        grid = QGridLayout()
        self.setLayout(grid)

        self.tree = QTreeView()
        model = QFileSystemModel()
        model.setRootPath("/")
        self.tree.setModel(model)
        grid.addWidget(self.tree, 0, 0)

        self.list = QListView()
        self.list.setAlternatingRowColors(True)
        model = QStringListModel()
        model.setStringList(["item1", "item2", "item3"])
        self.list.setModel(model)
        grid.addWidget(self.list, 0, 1)


class WidgetGallery(QMainWindow):
    def __init__(self, parent=None):
        super(WidgetGallery, self).__init__(parent)
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.tab1 = ControlsPan()
        self.tabs.addTab(self.tab1, "Controls")
        self.tab2 = ViewsPan()
        self.tabs.addTab(self.tab2, "Views")
        self.menu = QMenu("Style")
        self.menuBar().addMenu(self.menu)
        self.menu.addAction("Reload stylesheets", self.load_stylesheet)

    def load_stylesheet(self):
        sciqlop_app().load_stylesheet()


def main():
    if platform.system() == 'Linux':
        os.environ['QT_QPA_PLATFORM'] = os.environ.get("SCIQLOP_QT_QPA_PLATFORM", 'xcb')
    app = sciqlop_app()
    loop = sciqlop_event_loop()
    main_window = WidgetGallery()
    main_window.show()
    loop.exec()


if __name__ == '__main__':
    main()
