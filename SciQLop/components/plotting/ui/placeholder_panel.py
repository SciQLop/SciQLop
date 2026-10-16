"""A panel that stands in for one whose kind is not available; it keeps its tree so saving again loses nothing."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from SciQLop.core.panel_kinds import KIND_PROPERTY
from SciQLop.core.plot_kinds import plugin_of
from SciQLop.core.unique_names import auto_name, release_name

PLACEHOLDER_PANEL = "sciqlop.placeholder_panel"


def _message(kind: str) -> str:
    return f"This panel needs plugin {plugin_of(kind)!r} (panel kind {kind!r})."


class PlaceholderPanel(QWidget):
    """Tagged with KIND_PROPERTY so it docks, lists and closes like any panel; not a PANEL_KINDS contribution."""

    def __init__(self, root: dict, parent=None):
        super().__init__(parent)
        self.root = root
        self.missing_kind = root["kind"]
        self.setProperty(KIND_PROPERTY, PLACEHOLDER_PANEL)
        self._label = QLabel(_message(self.missing_kind), self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(self._label)

    def message(self) -> str:
        return self._label.text()


def open_placeholder(main_window, root: dict, name: str) -> PlaceholderPanel:
    from SciQLop.core.ui.panel_host import dock_panel
    name = auto_name(base="Panel", name=name)
    try:
        widget = PlaceholderPanel(root)
        widget.setObjectName(name)
        widget.setWindowTitle(name)
        dock_panel(main_window, widget, PLACEHOLDER_PANEL)
    except Exception:
        release_name(name)
        raise
    return widget
