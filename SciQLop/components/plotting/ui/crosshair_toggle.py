from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QToolButton

from SciQLop.core.ui import Metrics
from SciQLop.components.theming import theme_adapted_icon


class CrosshairToggle(QToolButton):
    """Single-button checkable toggle for the per-panel crosshair + hover tooltip.

    Emits the inherited :pyattr:`toggled(bool)` signal. Icon and tooltip swap
    between on/off so the state is readable at a glance.

    Uses ``QToolButton`` rather than ``QPushButton`` so the icon respects
    ``iconSize`` exactly on macOS — the native macOS push-button bezel adds
    chrome around the content rect and visually clipped/oversized the icon
    relative to the button.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(True)
        self.setAutoRaise(True)
        self.setIconSize(QSize(Metrics.ex(2), Metrics.ex(2)))
        self.setFixedSize(Metrics.em(2.5), Metrics.em(2.5))
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.toggled.connect(self._refresh_appearance)
        self._refresh_appearance()

    def _refresh_appearance(self, *_):
        on = self.isChecked()
        self.setIcon(theme_adapted_icon("my_location" if on else "location_disabled"))
        state = "on" if on else "off"
        self.setToolTip(f"Crosshair and hover tooltip: {state} (Ctrl+Shift+H)")
