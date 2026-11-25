"""One line of CoCat search text, as the web app's search box: coloured by parts (cocat_rs.pieces),
completes the word at the cursor from the project's vocabulary (cocat_rs.complete/accept),
underlines a wrong part, never takes a second line."""
from __future__ import annotations

import cocat_rs
from PySide6.QtCore import QStringListModel, Qt
from PySide6.QtGui import QColor, QKeyEvent, QSyntaxHighlighter, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QCompleter, QPlainTextEdit, QTextEdit

# mid tones, readable on the light and the dark themes
TONES = {"field": QColor("#3d7fd6"), "op": QColor("#8a8a8a"), "value": QColor("#2e9e6a"),
         "keyword": QColor("#b0569e")}


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


class _Colours(QSyntaxHighlighter):
    def highlightBlock(self, text: str) -> None:
        for start, length, tone in coloured_spans(text):
            self.setFormat(start, length, _tone(tone))


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
        self.completer = QCompleter(QStringListModel(self), self)  # parented, or Python collects it
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.CompletionMode.UnfilteredPopupCompletion)
        self.completer.activated.connect(self.accept_completion)

    def set_vocabulary(self, vocabulary: dict) -> None:
        """What the project's searches can name (Project.vocabulary)."""
        self._vocabulary = vocabulary

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

    def complete_now(self) -> None:
        self._completion = cocat_rs.complete(self.toPlainText(), self.textCursor().position(), self._vocabulary)
        if not self._completion:
            return self.completer.popup().hide()
        self.completer.model().setStringList([s["insert"] for s in self._completion["suggestions"]])
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
        cursor.setPosition(position)
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
