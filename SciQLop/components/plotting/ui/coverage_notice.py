"""Offer to jump to a product's data when the panel window lies wholly outside
its coverage -- the Speasy proxy plot page's "Go to first/last data" note."""
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QToolButton

from SciQLop.core import TimeRange

_STYLE = ("QFrame#CoverageNotice { background: palette(window);"
          " border: 1px solid palette(mid); border-radius: 1ex; }")
_MARGIN_EX = 1


def out_of_coverage(coverage: Optional[TimeRange],
                    window: TimeRange) -> Optional[Tuple[str, TimeRange]]:
    """None when they overlap or the coverage is unknown, else the side the
    window is on and the window of the same length at the nearest edge."""
    if coverage is None:
        return None
    width = window.stop() - window.start()
    if window.start() >= coverage.stop():
        return "after", TimeRange(coverage.stop() - width, coverage.stop())
    if window.stop() <= coverage.start():
        return "before", TimeRange(coverage.start(), coverage.start() + width)
    return None


def _utc_day(t: float) -> str:
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d")


class CoverageNotice(QFrame):
    """Non-modal, top-centred over the panel; gone once the window moves."""

    def __init__(self, panel, name: str, coverage: TimeRange, side: str, jump: TimeRange):
        super().__init__(panel.viewport())
        self.setObjectName("CoverageNotice")
        self.setStyleSheet(_STYLE)
        layout = QHBoxLayout(self)
        layout.addWidget(QLabel(
            f"No data here: {name} covers {_utc_day(coverage.start())} → {_utc_day(coverage.stop())}"))
        self.jump_button = QPushButton("Go to last data" if side == "after" else "Go to first data")
        self.jump_button.clicked.connect(lambda: panel.set_time_axis_range(jump))
        layout.addWidget(self.jump_button)
        close = QToolButton()
        close.setText("✕")
        close.setAutoRaise(True)
        close.clicked.connect(self.close)
        layout.addWidget(close)
        panel.time_range_changed.connect(self.close)
        self.parentWidget().installEventFilter(self)
        self.adjustSize()
        self._place()
        self.show()
        self.raise_()

    def _place(self):
        parent = self.parentWidget()
        margin = self.fontMetrics().xHeight() * _MARGIN_EX
        self.move(max(0, (parent.width() - self.width()) // 2), margin)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Resize:
            self._place()
        return False


def _replace_notices(panel) -> None:
    for old in panel.findChildren(CoverageNotice):
        old.close()
        old.deleteLater()


def offer_jump_to_data(panel, product: List[str]) -> Optional[CoverageNotice]:
    from SciQLopPlots import ProductsModel
    from SciQLop.components.plotting.backend.data_provider import providers

    node = ProductsModel.node(product)
    provider = providers.get(node.provider()) if node is not None else None
    if provider is None:
        return None
    coverage = provider.coverage(node)
    out = out_of_coverage(coverage, panel.time_range)
    if out is None:
        return None
    _replace_notices(panel)
    return CoverageNotice(panel, node.name(), coverage, *out)
