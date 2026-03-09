from typing import List
from PySide6.QtCore import Signal, QSize, Qt, QEvent
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy, QWidget, QGridLayout, QSpacerItem, QLineEdit
from SciQLop.core.ui import apply_size_policy, increase_font_size
from SciQLop.core.common import Maybe
from SciQLop.components import sciqlop_logging
from .card import Card

log = sciqlop_logging.getLogger(__name__)


class CardsCollection(QFrame):
    _cards: List[Card]
    show_detailed_description = Signal(QWidget)
    _last_row: int = 0
    _last_col: int = 0
    _columns: int = 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards = []
        self._filter_text = ""
        self._layout = QGridLayout()
        self._layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(self._layout)
        self.refresh_ui()

    def _card_width(self) -> int:
        if self._cards:
            return self._cards[0].maximumWidth()
        return 200

    def _compute_columns(self) -> int:
        margins = self._layout.contentsMargins()
        available = self.width() - margins.left() - margins.right()
        spacing = self._layout.horizontalSpacing()
        card_w = self._card_width()
        return max(1, (available + spacing) // (card_w + spacing))

    def _place_card(self, card: Card):
        self._layout.addWidget(card, self._last_row, self._last_col)
        self._last_col += 1
        if self._last_col == self._columns:
            self._last_col = 0
            self._last_row += 1

    def _reset_layout(self):
        log.debug(f"Resetting layout")
        self._last_row = 0
        self._last_col = 0
        item = self._layout.takeAt(0)
        while item is not None:
            if item.widget() is None:
                del item
            item = self._layout.takeAt(0)
        self._layout.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum), 0,
                             self._columns, -1, 1)

    def add_card(self, card: Card, connect_detail: bool = True):
        log.debug(f"Adding card {card}")
        self._cards.append(card)
        self._place_card(card)
        card.installEventFilter(self)
        if connect_detail:
            card.clicked.connect(lambda: self.show_detailed_description.emit(card))

    def _visible_cards(self):
        if not self._filter_text:
            return self._cards
        query = self._filter_text.lower()
        return [c for c in self._cards if query in c.filter_text().lower()]

    def filter_cards(self, text: str):
        self._filter_text = text
        self.refresh_ui()

    def refresh_ui(self):
        log.debug(f"Refreshing UI")
        self._columns = self._compute_columns()
        visible = self._visible_cards()
        self._reset_layout()
        for card in self._cards:
            if card in visible:
                card.show()
                card.invalidate_animation_cache()
                self._place_card(card)
            else:
                card.hide()

    def resizeEvent(self, event):
        new_columns = self._compute_columns()
        if new_columns != self._columns:
            self.refresh_ui()
        super().resizeEvent(event)

    def clear(self):
        log.debug(f"Clearing cards")
        self._cards = []
        self.refresh_ui()

    def minimumSizeHint(self) -> QSize:
        margins = self._layout.contentsMargins()
        min_w = self._card_width() + margins.left() + margins.right()
        # Only constrain width; let the layout compute the natural height
        return QSize(min_w, super().minimumSizeHint().height())

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress and isinstance(obj, Card):
            visible = self._visible_cards()
            if obj not in visible:
                return False
            idx = visible.index(obj)
            key = event.key()
            target = None
            if key == Qt.Key.Key_Right and idx + 1 < len(visible):
                target = visible[idx + 1]
            elif key == Qt.Key.Key_Left and idx - 1 >= 0:
                target = visible[idx - 1]
            elif key == Qt.Key.Key_Down and idx + self._columns < len(visible):
                target = visible[idx + self._columns]
            elif key == Qt.Key.Key_Up and idx - self._columns >= 0:
                target = visible[idx - self._columns]
            if target:
                target.setFocus()
                return True
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        if not self.childAt(event.position().toPoint()):
            list(map(lambda c: c.set_selected(False), self._cards))
            self.show_detailed_description.emit(None)
        super().mousePressEvent(event)


class WelcomeSection(QFrame):
    show_detailed_description = Signal(QWidget)

    def __init__(self, name: str, filterable: bool = False, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        header = QHBoxLayout()
        self._name_lbl = apply_size_policy(increase_font_size(QLabel(name), 1.2), QSizePolicy.Policy.Expanding,
                                           QSizePolicy.Policy.Maximum)
        header.addWidget(self._name_lbl)
        self._filter_collections: list[CardsCollection] = []
        if filterable:
            self._filter_input = QLineEdit()
            self._filter_input.setPlaceholderText("Filter...")
            self._filter_input.setClearButtonEnabled(True)
            self._filter_input.setMaximumWidth(200)
            self._filter_input.textChanged.connect(self._on_filter_changed)
            header.addWidget(self._filter_input)
        self._layout.addLayout(header)

    def add_filterable_collection(self, collection: CardsCollection):
        self._filter_collections.append(collection)

    def _on_filter_changed(self, text: str):
        for collection in self._filter_collections:
            collection.filter_cards(text)
