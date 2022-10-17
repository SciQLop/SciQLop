from PySide6 import QtCore
from SciQLopBindings import SciQLopCore, ProductsTree, MainWindow
from .console import Console
from .products_tree import ProductTree as PyProductTree


class SciQLopMainWindow(MainWindow):
    def __init__(self):
        MainWindow.__init__(self)
        self.productTree = ProductsTree(self)
        self.productTree.setMinimumWidth(100)
        self.py_product_tree = PyProductTree()
        self.addWidgetIntoDock(QtCore.Qt.LeftDockWidgetArea, self.productTree)
        self.addWidgetIntoDock(QtCore.Qt.LeftDockWidgetArea, self.py_product_tree)
        self.console = Console(parent=self, available_vars={"main_window": self},
                               custom_banner="SciQLop IPython Console ")
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.console)
        self.setWindowTitle("SciQLop")
