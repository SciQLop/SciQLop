from typing import Dict, Any, Sequence, List, Optional
from PySide6.QtCore import QObject, Signal, Slot, Property
from PySide6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy
from .inspector_tree import InspectorTree
from .properties_editor import PropertyEditor
from SciQLop.inspector.model import Model


class InspectorWidget(QWidget):
    def __init__(self, model: Model, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Inspector")
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self._inspector_tree = InspectorTree(model, self)
        self._property_editor = PropertyEditor(self)
        model.objects_selected.connect(self._property_editor.set_nodes)
        model.object_deleted.connect(self._property_editor.node_destroyed)
        self._layout.addWidget(self._inspector_tree)
        self._layout.addWidget(self._property_editor)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding))
        self.setMinimumWidth(200)
