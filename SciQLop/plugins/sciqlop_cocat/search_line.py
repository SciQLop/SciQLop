"""One line of CoCat search text: underlines a wrong part, completes the word at the cursor, never
takes a second line. Kept for the CoCat search box of the event table (cocat-rs 0.12 brings its
colouring and completion data); tested on its own until then."""
from __future__ import annotations

from PySide6.QtCore import QStringListModel, Qt
from PySide6.QtGui import QColor, QKeyEvent, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QCompleter, QPlainTextEdit, QTextEdit


def _underline() -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
    fmt.setUnderlineColor(QColor("#d0453a"))
    return fmt


class SearchLine(QPlainTextEdit):
    """One line of search text: underlines a wrong part, completes the word at the cursor, and never
    takes a second line."""

    def __init__(self, words: list[str], parent=None):
        super().__init__(parent)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTabChangesFocus(True)
        self.setPlaceholderText("tag:shock confidence:>=0.7")
        margins = 2 * (self.document().documentMargin() + self.frameWidth())
        self.setFixedHeight(int(self.fontMetrics().lineSpacing() + margins))
        self.completer = QCompleter(QStringListModel(words, self), self)  # parented, or Python collects it
        self.completer.setWidget(self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.activated.connect(self.accept_completion)

    def completion_words(self) -> list[str]:
        return self.completer.model().stringList()

    def underline(self, start: int | None, length: int = 0) -> None:
        if start is None:
            return self.setExtraSelections([])
        selection = QTextEdit.ExtraSelection()
        selection.cursor = QTextCursor(self.document())
        end = min(start + length, len(self.toPlainText()))
        selection.cursor.setPosition(min(start, end))
        selection.cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        selection.format = _underline()
        self.setExtraSelections([selection])

    def _word_at_cursor(self) -> str:
        text = self.toPlainText()[:self.textCursor().position()]
        return text[len(text.rstrip().rsplit(" ", 1)[0]) if " " in text.strip() else 0:].lstrip()

    def complete_now(self) -> None:
        prefix = self._word_at_cursor()
        if not prefix:
            return self.completer.popup().hide()
        self.completer.setCompletionPrefix(prefix)
        rect = self.cursorRect()
        rect.setWidth(self.completer.popup().sizeHintForColumn(0) + 24)
        self.completer.complete(rect)

    def accept_completion(self, word: str) -> None:
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor,
                            len(self.completer.completionPrefix()))
        cursor.insertText(word)
        self.setTextCursor(cursor)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        popup_keys = (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Escape, Qt.Key.Key_Tab)
        if self.completer.popup().isVisible() and event.key() in popup_keys:
            return event.ignore()  # the completer takes them
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            return event.accept()
        super().keyPressEvent(event)
        if event.text().strip():
            self.complete_now()
