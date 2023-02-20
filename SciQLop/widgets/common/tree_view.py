from PySide6 import QtCore, QtWidgets, QtGui


class TreeView(QtWidgets.QTreeView):
    def __init__(self, parent=None):
        super(TreeView, self).__init__(parent)
        self.header().setVisible(False)
        self.setDragEnabled(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragOnly)
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self._expend_all_action = QtGui.QAction("Expand all")
        self._collapse_all_action = QtGui.QAction("Collapse all")
        self.addAction(self._expend_all_action)
        self.addAction(self._collapse_all_action)
        self.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
        self._expend_all_action.triggered.connect(self.expandAll)
        self._collapse_all_action.triggered.connect(self.collapseAll)
