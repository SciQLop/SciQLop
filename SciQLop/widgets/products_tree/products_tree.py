from PySide6 import QtCore, QtWidgets, QtGui

from SciQLop.backend import products
from .tree_view import TreeView


class ProductTree(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(ProductTree, self).__init__(parent)
        self._model_proxy = QtCore.QSortFilterProxyModel(self)
        self._model_proxy.setSourceModel(products)
        self._view = TreeView(self)
        self._view.setModel(self._model_proxy)
        self._model_proxy.setFilterRole(QtCore.Qt.UserRole)
        self._model_proxy.setRecursiveFilteringEnabled(True)
        self._model_proxy.setAutoAcceptChildRows(True)
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
        self._filter.editingFinished.connect(lambda: self._model_proxy.setFilterFixedString(self._filter.text()))
