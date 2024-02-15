from PySide6 import QtCore, QtGui
from PySide6.QtWidgets import QSizePolicy, QWidget, QLineEdit, QCompleter, QVBoxLayout

from SciQLop.backend.models import products
from SciQLop.backend.products_model.model import ProductsModel
from SciQLop.widgets.common import TreeView


class ProductTreeView(TreeView):
    def __init__(self, parent=None):
        super(ProductTreeView, self).__init__(parent)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() == QtCore.Qt.Key_Delete:
            self.delete_selected()
            event.accept()
        else:
            super(ProductTreeView, self).keyPressEvent(event)

    def model(self) -> ProductsModel:
        return super(ProductTreeView, self).model()

    def delete_selected(self):
        self.model().delete_indexes(self.selectedIndexes())


class ProductTree(QWidget):
    def __init__(self, parent=None):
        super(ProductTree, self).__init__(parent)
        self._view = ProductTreeView(self)
        # self._view.setSizeAdjustPolicy(QAbstractScrollArea.AdjustIgnored)
        self._view.setModel(products)
        self._view.setSortingEnabled(False)
        self._filter = QLineEdit(self)
        self._filter.setClearButtonEnabled(True)
        self._filter.addAction(QtGui.QIcon(":/icons/theme/search.png"), QLineEdit.LeadingPosition)
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
        self.setMinimumWidth(200)
