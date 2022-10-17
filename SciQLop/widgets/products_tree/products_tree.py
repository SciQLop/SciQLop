from PySide6 import QtCore, QtWidgets
from SciQLop.backend import products
from .tree_view import TreeView


class ProductTree(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(ProductTree, self).__init__(parent)
        self._filter_timer = QtCore.QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._model_proxy = QtCore.QSortFilterProxyModel(self)
        self._model_proxy.setSourceModel(products)
        self._view = TreeView(self)
        self._view.setModel(self._model_proxy)
        self._model_proxy.setFilterRole(QtCore.Qt.UserRole)
        self._model_proxy.setRecursiveFilteringEnabled(True)
        self._model_proxy.setAutoAcceptChildRows(True)
        self._filter = QtWidgets.QLineEdit(self)
        self._completer = QtWidgets.QCompleter(self)
        self._completer.setModel(products.completion_model)
        self._completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self._filter.setCompleter(self._completer)
        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().addWidget(self._filter)
        self.layout().addWidget(self._view)
        self._filter.textChanged.connect(lambda text: self._filter_timer.start(1000))
        self._filter_timer.timeout.connect(lambda: self._model_proxy.setFilterFixedString(self._filter.text()))
