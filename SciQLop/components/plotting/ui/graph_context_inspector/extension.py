from PySide6.QtWidgets import QWidget

from SciQLopPlots import InspectorExtension

from .section import GraphContextSection


class GraphContextExtension(InspectorExtension):
    """Read-only inspector node for a graph's context envelope.

    Lives next to the existing KnobInspectorExtension; this one shows source
    identity (speasy uid / vp path / callback) plus 'Copy Python code' and
    'Show full metadata…' actions. Knob *editing* stays in
    KnobInspectorExtension — this extension only displays current values.

    State (graph ref, title) is read from Qt-side storage on every call —
    ``self.parent()`` and ``self.objectName()`` — so the extension keeps
    working after Shiboken recreates the Python wrapper from the surviving
    C++ object. Stashing them as Python instance attributes silently broke
    the section: the wrapper got GC'd alongside the graph wrapper, and the
    fresh wrapper PropertyDelegateBase saw had empty ``__dict__``.
    """

    def __init__(self, graph, parent=None, title: str = "Graph"):
        super().__init__(parent if parent is not None else graph)
        self.setObjectName(title)

    def section_title(self) -> str:
        return self.objectName()

    def priority(self) -> int:
        return 50

    def build_widget(self, parent: QWidget) -> QWidget:
        return GraphContextSection(self.parent(), parent=parent)
