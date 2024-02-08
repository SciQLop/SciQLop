from PySide6 import QtCore, QtGui
from PySide6.QtWidgets import QTreeView, QAbstractScrollArea, QSizePolicy, QAbstractItemView


class TreeView(QTreeView):

    def __init__(self, parent=None):
        super(TreeView, self).__init__(parent)
        self.header().setVisible(False)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragOnly)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._expend_all_action = QtGui.QAction("Expand all")
        self._collapse_all_action = QtGui.QAction("Collapse all")
        self.addAction(self._expend_all_action)
        self.addAction(self._collapse_all_action)
        self.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
        self._expend_all_action.triggered.connect(self.expandAll)
        self._collapse_all_action.triggered.connect(self.collapseAll)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
