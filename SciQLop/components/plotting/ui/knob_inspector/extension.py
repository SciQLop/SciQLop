from PySide6.QtWidgets import QWidget, QLabel

from SciQLopPlots import InspectorExtension

from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
from SciQLop.components.plotting.ui.knob_inspector.section import KnobsSection


class KnobInspectorExtension(InspectorExtension):
    def __init__(self, state: GraphKnobState, parent=None, title: str = "Parameters"):
        super().__init__(parent)
        self.setObjectName(title)
        self._state = state
        self._title = title

    def section_title(self) -> str:
        return self._title

    def priority(self) -> int:
        return 100

    def build_widget(self, parent: QWidget) -> QWidget:
        return KnobsSection(self._state, parent=parent)


class LayerExtension(InspectorExtension):
    """Minimal extension for layers without knobs — just a tree node."""
    def __init__(self, parent=None, title: str = "Layer"):
        super().__init__(parent)
        self.setObjectName(title)
        self._title = title

    def section_title(self) -> str:
        return self._title

    def priority(self) -> int:
        return 100

    def build_widget(self, parent: QWidget) -> QWidget:
        return QLabel("No configurable parameters", parent)
