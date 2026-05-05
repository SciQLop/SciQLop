from PySide6.QtWidgets import QWidget

from SciQLopPlots import InspectorExtension

from .section import GraphContextSection


class GraphContextExtension(InspectorExtension):
    """Read-only inspector node for a graph's context envelope.

    Lives next to the existing KnobInspectorExtension; this one shows source
    identity (speasy uid / vp path / callback) plus 'Copy Python code' and
    'Show full metadata…' actions. Knob *editing* stays in
    KnobInspectorExtension — this extension only displays current values.
    """

    def __init__(self, graph, parent=None, title: str = "Graph"):
        super().__init__(parent)
        self.setObjectName(title)
        self._graph = graph
        self._title = title

    def section_title(self) -> str:
        return self._title

    def priority(self) -> int:
        return 50

    def build_widget(self, parent: QWidget) -> QWidget:
        return GraphContextSection(self._graph, parent=parent)
