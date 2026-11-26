"""One line of CoCat search text, as the web app's search box: coloured by parts (cocat_rs.pieces),
completes the word at the cursor from the project's vocabulary (cocat_rs.complete/accept),
underlines a wrong part, never takes a second line. Each suggestion shows its kind (cocat-rs 0.12.5's
"detail": field, attribute, tag...) small and dimmed at the right of its row. Tab completes: the
highlighted suggestion (or the first) when the list is open; else the only one, or opens the list; with
nothing to complete it moves on, and Shift+Tab always moves back."""
from __future__ import annotations

import cocat_rs
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QKeyEvent, QPalette, QStandardItem, QStandardItemModel,
                           QSyntaxHighlighter, QTextCharFormat, QTextCursor)
from PySide6.QtWidgets import QCompleter, QPlainTextEdit, QStyle, QStyledItemDelegate, QTextEdit

# mid tones, readable on the light and the dark themes
TONES = {"field": QColor("#3d7fd6"), "op": QColor("#8a8a8a"), "value": QColor("#2e9e6a"),
         "keyword": QColor("#b0569e")}


def to_units(text: str, chars: int) -> int:
    """Qt's position (UTF-16 units) of cocat-rs's (characters): an emoji is two units, one character."""
    return len(text[:chars].encode("utf-16-le")) // 2


def to_chars(text: str, units: int) -> int:
    """cocat-rs's position (characters) of Qt's (UTF-16 units)."""
    return len(text.encode("utf-16-le")[:2 * units].decode("utf-16-le", "ignore"))


def _tone(name: str) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(TONES[name])
    return fmt


def _underline() -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
    fmt.setUnderlineColor(QColor("#d0453a"))
    return fmt


def coloured_spans(text: str) -> list[tuple[int, int, str]]:
    """(start, length, tone) for the parts of a search that are coloured."""
    spans, at = [], 0
    for piece in cocat_rs.pieces(text):
        if piece["kind"] == "keyword":
            spans.append((at, len(piece["text"]), "keyword"))
        elif piece["kind"] == "term":
            field, op = len(piece["field"]), len(piece["op"])
            spans += [(at, field, "field"), (at + field, op, "op"),
                      (at + field + op, len(piece["text"]) - field - op, "value")]
        at += len(piece["text"])
    return spans


DETAIL_ROLE = Qt.ItemDataRole.UserRole + 1
DETAIL_PADDING = 8


def _small(font: QFont) -> QFont:
    smaller = QFont(font)
    smaller.setPointSizeF(font.pointSizeF() * 0.85)
    return smaller


def _dimmed(colour: QColor) -> QColor:
    """The row's own text colour, faded: readable on the light and the dark themes, selected or not."""
    faded = QColor(colour)
    faded.setAlphaF(0.6)
    return faded


class _WithDetail(QStyledItemDelegate):
    """A suggestion's kind at the right of its row; the row's text stays what is inserted."""

    def paint(self, painter, option, index) -> None:
        super().paint(painter, option, index)
        detail = index.data(DETAIL_ROLE)
        if not detail:
            return
        selected = option.state & QStyle.StateFlag.State_Selected
        role = QPalette.ColorRole.HighlightedText if selected else QPalette.ColorRole.Text
        painter.save()
        painter.setFont(_small(option.font))
        painter.setPen(_dimmed(option.palette.color(role)))
        painter.drawText(option.rect.adjusted(0, 0, -DETAIL_PADDING, 0),
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, detail)
        painter.restore()

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        detail = index.data(DETAIL_ROLE)
        if detail:
            size.setWidth(size.width() + 2 * DETAIL_PADDING
                          + QFontMetrics(_small(option.font)).horizontalAdvance(detail))
        return size


def _suggestion_item(suggestion: dict) -> QStandardItem:
    item = QStandardItem(suggestion["insert"])
    item.setData(suggestion.get("detail"), DETAIL_ROLE)  # none before cocat-rs 0.12.5
    return item


class _Colours(QSyntaxHighlighter):
    def highlightBlock(self, text: str) -> None:
        for start, length, tone in coloured_spans(text):
            at = to_units(text, start)
            self.setFormat(at, to_units(text, start + length) - at, _tone(tone))


class SearchLine(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTabChangesFocus(True)
        margins = 2 * (self.document().documentMargin() + self.frameWidth())
        self.setFixedHeight(int(self.fontMetrics().lineSpacing() + margins))
        self._colours = _Colours(self.document())
        self._vocabulary: dict = {}
        self._completion: dict | None = None
        self.completer = QCompleter(QStandardItemModel(self), self)  # parented, or Python collects it
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.CompletionMode.UnfilteredPopupCompletion)
        self.completer.activated.connect(self.accept_completion)
        self.completer.popup().setItemDelegate(_WithDetail(self.completer.popup()))
        # after the completer's own filter, so this one runs first: the completer only hides on Tab
        self.completer.popup().installEventFilter(self)

    def set_vocabulary(self, vocabulary: dict) -> None:
        """What the project's searches can name (Project.vocabulary)."""
        self._vocabulary = vocabulary

    def completion_words(self) -> list[str]:
        model = self.completer.model()
        return [model.item(row).text() for row in range(model.rowCount())]

    def underline(self, start: int | None, length: int = 0) -> None:
        """A wave under [start, start + length), in characters; a mistake at the end (``tag:``) waves
        under the last character, or nothing would show."""
        text = self.toPlainText()
        if start is None or not text:
            return self.setExtraSelections([])
        start = min(start, len(text) - 1)
        end = max(start + 1, min(start + length, len(text)))
        selection = QTextEdit.ExtraSelection()
        selection.cursor = QTextCursor(self.document())
        selection.cursor.setPosition(to_units(text, start))
        selection.cursor.setPosition(to_units(text, end), QTextCursor.MoveMode.KeepAnchor)
        selection.format = _underline()
        self.setExtraSelections([selection])

    def _completion_here(self) -> dict | None:
        text = self.toPlainText()
        return cocat_rs.complete(text, to_chars(text, self.textCursor().position()), self._vocabulary)

    def complete_now(self) -> None:
        self._completion = self._completion_here()
        model = self.completer.model()
        model.setRowCount(0)
        if not self._completion:
            return self.completer.popup().hide()
        for suggestion in self._completion["suggestions"]:
            model.appendRow(_suggestion_item(suggestion))
        rect = self.cursorRect()
        rect.setWidth(self.completer.popup().sizeHintForColumn(0) + 24)
        self.completer.complete(rect)

    def accept_completion(self, insert: str) -> None:
        suggestion = next((s for s in (self._completion or {}).get("suggestions", ()) if s["insert"] == insert), None)
        if suggestion is None:
            return
        text, position = cocat_rs.accept(self.toPlainText(), self._completion, suggestion)
        self._completion = None
        self.setPlainText(text)
        cursor = self.textCursor()
        cursor.setPosition(to_units(text, position))
        self.setTextCursor(cursor)

    def event(self, event: QEvent) -> bool:
        """Tab before Qt's focus handling, which tabChangesFocus would apply first."""
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Tab \
                and not event.modifiers() & ~Qt.KeyboardModifier.KeypadModifier and self._complete_on_tab():
            return True
        return super().event(event)

    def eventFilter(self, watched, event: QEvent) -> bool:
        if watched is self.completer.popup() and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Tab:
                self._take_highlighted()
                return True
            if event.key() == Qt.Key.Key_Backtab:
                self.completer.popup().hide()
                self.focusPreviousChild()
                return True
        return super().eventFilter(watched, event)

    def _complete_on_tab(self) -> bool:
        """The list open: take a suggestion. Else one suggestion for the word at the cursor: take it;
        several: open the list. False when there is no word to complete: the focus moves on."""
        if self.completer.popup().isVisible():
            self._take_highlighted()
            return True
        completion = self._completion_here()
        if not completion or completion["from"] == completion["to"] or not completion["suggestions"]:
            return False
        if len(completion["suggestions"]) > 1:
            self.complete_now()
            return True
        self._completion = completion
        self.accept_completion(completion["suggestions"][0]["insert"])
        return True

    def _take_highlighted(self) -> None:
        popup = self.completer.popup()
        highlighted = popup.currentIndex()
        words = self.completion_words()
        popup.hide()
        if words:
            self.accept_completion(highlighted.data() if highlighted.isValid() else words[0])

    def keyPressEvent(self, event: QKeyEvent) -> None:
        popup_keys = (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Escape, Qt.Key.Key_Tab)
        if self.completer.popup().isVisible() and event.key() in popup_keys:
            return event.ignore()  # the completer takes them
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            return event.accept()
        super().keyPressEvent(event)
        if event.text().strip():
            self.complete_now()
