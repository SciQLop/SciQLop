from PySide6 import QtCore, QtWidgets, QtGui

from SciQLop.backend.models import products
from SciQLop.widgets.common import TreeView


class ProductTree(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(ProductTree, self).__init__(parent)
        self._view = TreeView(self)
        self._view.setModel(products)
        self._view.setSortingEnabled(False)
        self._filter = QtWidgets.QLineEdit(self)
        self._filter.setClearButtonEnabled(True)
        self._filter.addAction(QtGui.QIcon(":/icons/zoom.png"), QtWidgets.QLineEdit.LeadingPosition)
        self._filter.setPlaceholderText("Search...")
        self._completer = QtWidgets.QCompleter(self)
        self._completer.setModel(products.completion_model)
        self._completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self._completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
        self._completer.setModelSorting(QtWidgets.QCompleter.CaseSensitivelySortedModel)
        self._filter.setCompleter(self._completer)
        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().addWidget(self._filter)
        self.layout().addWidget(self._view)
        self._filter.textChanged.connect(lambda: products.set_filter(self._filter.text()))
        self.setWindowTitle("Products")
