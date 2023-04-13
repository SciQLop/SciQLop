from PySide6 import QtCore, QtGui
from PySide6.QtWidgets import QSizePolicy, QWidget, QLineEdit, QCompleter, QVBoxLayout

from SciQLop.backend.models import products
from SciQLop.widgets.common import TreeView


class ProductTree(QWidget):
    def __init__(self, parent=None):
        super(ProductTree, self).__init__(parent)
        self._view = TreeView(self)
        self._view.setModel(products)
        self._view.setSortingEnabled(False)
        self._filter = QLineEdit(self)
        self._filter.setClearButtonEnabled(True)
        self._filter.addAction(QtGui.QIcon(":/icons/zoom.png"), QLineEdit.LeadingPosition)
        self._filter.setPlaceholderText("Search...")
        self._completer = QCompleter(self)
        self._completer.setModel(products.completion_model)
        self._completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self._completer.setModelSorting(QCompleter.CaseSensitivelySortedModel)
        self._filter.setCompleter(self._completer)
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self._filter)
        self.layout().addWidget(self._view)
        self._filter.textChanged.connect(lambda: products.set_filter(self._filter.text()))
        self.setWindowTitle("Products")
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
