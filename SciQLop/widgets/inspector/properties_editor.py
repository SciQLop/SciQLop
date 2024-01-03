from typing import List, Optional
from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QWidget, QFormLayout, QLabel
from SciQLop.widgets.settings_delegates import delegate_for


class PropertyEditor(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Properties Editor")
        self._layout = QFormLayout()
        self.setLayout(self._layout)
        self._current_nodes: List[QObject] = []

    @Slot(list)
    def set_nodes(self, nodes: List[QObject]):
        self._current_nodes = nodes
        self._clear()
        if len(nodes) == 1:
            node = nodes[0]
            self._layout.addWidget(QLabel(f"Properties of {node.name}"))
            delegate = delegate_for(node)
            if delegate is not None:
                self._layout.addRow(delegate(node))
            elif hasattr(node, 'settings_widget'):
                self._layout.addRow(node.settings_widget)
            elif hasattr(node, '_sciqlop_attributes_'):
                for prop in node._sciqlop_attributes_:
                    self._layout.addRow(prop, QLabel(str(getattr(node, prop))))

    @Slot()
    def node_destroyed(self, node: QObject):
        if node in self._current_nodes:
            self._current_nodes.remove(node)
            self.set_nodes(self._current_nodes)

    def _clear(self):
        while self._layout.count() > 0:
            self._layout.takeAt(0).widget().deleteLater()
