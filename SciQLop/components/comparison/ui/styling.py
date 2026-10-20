"""How a variant's ghost curve looks next to the base graph it shadows."""
from PySide6.QtCore import Qt


def _dash(component) -> None:
    pen = component.pen()
    pen.setStyle(Qt.PenStyle.DashLine)
    component.set_pen(pen)


def ghost_style(graph, base_graph, index: int) -> bool:
    """Each component dashed, in its base component's colour lightened more for each later variant.

    Only the base's colours are lightened, so calling it again never fades the ghost further.
    Returns True once the colours came from the base (a graph has components only after its first data).
    """
    base_colors = [c.color() for c in base_graph.components()]
    components = graph.components()
    for i, component in enumerate(components):
        if i < len(base_colors):
            component.set_color(base_colors[i].lighter(130 + 20 * index))
        _dash(component)
    return bool(base_colors) and bool(components)
