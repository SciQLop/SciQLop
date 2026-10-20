"""How a variant's ghost curve looks next to the base graph it shadows."""
from PySide6.QtCore import Qt

STYLED_PROPERTY = "sqp_ghost_styled"


def _dash(component) -> None:
    pen = component.pen()
    pen.setStyle(Qt.PenStyle.DashLine)
    component.set_pen(pen)


def ghost_style(graph, base_graph, index: int) -> bool:
    """Each component dashed, in its base component's colour (its own past the base's count)
    lightened more for each later variant.

    The colours are set once, when both graphs have components (a graph has them only after its
    first data); later calls change nothing, so the ghost never fades further. Returns True once set.
    """
    if graph.property(STYLED_PROPERTY):
        return True
    base_colors = [c.color() for c in base_graph.components()]
    components = graph.components()
    for component in components:
        _dash(component)
    if not (base_colors and components):
        return False
    for i, component in enumerate(components):
        source = base_colors[i] if i < len(base_colors) else component.color()
        component.set_color(source.lighter(130 + 20 * index))
    graph.setProperty(STYLED_PROPERTY, True)
    return True
