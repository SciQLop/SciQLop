"""Where guides are shown: the Guides window (Help > Guides, the palette's "Guide: …" commands) and
`GuideButton`, a small "?" that opens the guide of a context."""
import shiboken6
from PySide6.QtCore import QByteArray, QEvent, QSize, Qt
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QToolButton, QVBoxLayout, QWidget

from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.ui import Metrics
from SciQLop.core.ui.tooltips import rich_tooltip

from .qt_svg import for_qt, palette_tokens
from .registry import GUIDES, Guide, all_guides, get_guide, guide_for

log = getLogger(__name__)
_ASPECT = 430 / 720      # every guide is drawn in a 720 x 430 box


class GuidePlayer(QSvgWidget):
    """Plays one guide in the colours of the current theme."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._guide: Guide | None = None
        self.renderer().setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self.setMinimumSize(Metrics.em(36), round(Metrics.em(36) * _ASPECT))

    def sizeHint(self) -> QSize:
        return QSize(Metrics.em(54), round(Metrics.em(54) * _ASPECT))

    def play(self, guide: Guide) -> None:
        self._guide = guide
        try:
            svg = for_qt(guide.path.read_text(encoding="utf-8"), palette_tokens(self.palette()))
        except (OSError, KeyError) as e:
            log.error(f"Cannot show guide {guide.id}: {e}")
            svg = "<svg xmlns='http://www.w3.org/2000/svg'/>"
        self.load(QByteArray(svg.encode("utf-8")))

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange and self._guide is not None:
            self.play(self._guide)


class GuidesWindow(QDialog):
    """The list of guides and the one being played."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Guides")
        self.list = QListWidget(self)
        self.list.setFixedWidth(Metrics.em(20))
        self.title = QLabel(self)
        font = self.title.font()
        font.setBold(True)
        font.setPointSizeF(font.pointSizeF() * 1.25)
        self.title.setFont(font)
        self.player = GuidePlayer(self)
        self.caption = QLabel(self)
        self.caption.setWordWrap(True)

        right = QVBoxLayout()
        right.addWidget(self.title)
        right.addWidget(self.player, 1)
        right.addWidget(self.caption)
        layout = QHBoxLayout(self)
        layout.addWidget(self.list)
        layout.addLayout(right, 1)

        self.list.currentItemChanged.connect(self._on_picked)
        GUIDES.signals.added.connect(self._refresh)
        GUIDES.signals.removed.connect(self._refresh)
        self._refresh()

    def _refresh(self, *_) -> None:
        current = self.current_guide_id()
        self.list.blockSignals(True)
        self.list.clear()
        for guide in all_guides():
            item = QListWidgetItem(guide.title, self.list)
            item.setData(Qt.ItemDataRole.UserRole, guide.id)
        self.list.blockSignals(False)
        self.show_guide(current if current and get_guide(current) else None)

    def current_guide_id(self) -> str | None:
        item = self.list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def show_guide(self, guide_id: str | None = None) -> None:
        """`guide_id` None: the first guide."""
        for row in range(self.list.count()):
            if guide_id in (None, self.list.item(row).data(Qt.ItemDataRole.UserRole)):
                self.list.setCurrentRow(row)
                return

    def _on_picked(self, item, _previous=None) -> None:
        guide = get_guide(item.data(Qt.ItemDataRole.UserRole)) if item is not None else None
        if guide is None:
            return
        self.title.setText(guide.title)
        self.caption.setText(guide.caption)
        self.player.play(guide)


def show_guides(parent: QWidget, guide_id: str | None = None) -> GuidesWindow:
    """Open the Guides window of `parent`'s window (one per window), on `guide_id` when given."""
    host = parent.window()
    window = getattr(host, "_guides_window", None)
    if window is None or not shiboken6.isValid(window):
        window = host._guides_window = GuidesWindow(host)
    if guide_id is not None or window.current_guide_id() is None:
        window.show_guide(guide_id)
    window.show()
    window.raise_()
    return window


class GuideButton(QToolButton):
    """A "?" that opens the guide registered for `context`; hidden while no guide covers it.
    Core contexts: panel.empty, panel.time_range, panel.drop, catalog.mode.view / .jump / .edit,
    catalog.events.edit. A plugin names its own (prefixed with its name) and registers a guide for it."""

    def __init__(self, context: str, parent=None, text: str = "?"):
        super().__init__(parent)
        self.setText(text)
        self.setAutoRaise(True)
        self.clicked.connect(self._open)
        GUIDES.signals.added.connect(self._sync)
        GUIDES.signals.removed.connect(self._sync)
        self.context = context
        self._sync()

    def set_context(self, context: str) -> None:
        self.context = context
        self._sync()

    def _sync(self, *_) -> None:
        guide = guide_for(self.context)
        self.setVisible(guide is not None)
        if guide is not None:
            self.setToolTip(rich_tooltip("Show me how", guide.title))

    def _open(self) -> None:
        guide = guide_for(self.context)
        if guide is not None:
            show_guides(self, guide.id)
