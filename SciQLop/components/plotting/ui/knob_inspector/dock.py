from typing import Optional

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from SciQLop.components.plotting.ui.knob_inspector.section import KnobsSection


class KnobInspectorDock(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Parameters")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._placeholder = QLabel("No graph selected.")
        layout.addWidget(self._placeholder)
        self._section: Optional[KnobsSection] = None

    def set_graph(self, graph) -> None:
        self.clear()
        state = getattr(graph, "_knob_state", None)
        if state is None or not state.specs:
            self._placeholder.setText("This graph has no parameters.")
            return
        self._placeholder.setVisible(False)
        self._section = KnobsSection(state, parent=self)
        self.layout().addWidget(self._section)

    def clear(self) -> None:
        if self._section is not None:
            self._section.setParent(None)
            self._section.deleteLater()
            self._section = None
        self._placeholder.setVisible(True)
        self._placeholder.setText("No graph selected.")

    def current_section(self) -> Optional[KnobsSection]:
        return self._section
