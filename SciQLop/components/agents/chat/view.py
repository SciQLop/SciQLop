"""Rich chat widgets: markdown transcript view and image-paste-capable input.

Agent-agnostic: the assistant label and input placeholder can be set by the
dock once it knows which backend is active.
"""
from __future__ import annotations

import uuid as _uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Literal, Union

from PySide6.QtCore import QMimeData, QStringListModel, Qt, QTimer, QUrl
from PySide6.QtGui import (
    QImage,
    QKeyEvent,
    QStandardItem,
    QStandardItemModel,
    QTextCursor,
    QTextDocument,
    QTextDocumentFragment,
    QTextImageFormat,
)
from PySide6.QtWidgets import (
    QCompleter,
    QLineEdit,
    QListView,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .history import PromptHistory


@dataclass
class TextBlock:
    text: str = ""


@dataclass
class ImageBlock:
    path: str


ContentBlock = Union[TextBlock, ImageBlock]


@dataclass
class ChatMessage:
    role: Literal["user", "assistant", "error"]
    blocks: List[ContentBlock] = field(default_factory=list)
    done: bool = False


_DEFAULT_ROLE_LABEL = {"user": "You", "assistant": "Assistant", "error": "Error"}
_ROLE_COLOR = {"user": "#3d6ab0", "assistant": "#2a7a3c", "error": "#a33"}

_RENDER_INTERVAL_MS = 80


class TranscriptView(QTextBrowser):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOpenExternalLinks(False)
        self.setOpenLinks(False)
        self.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self._image_max_width_px = 720
        self._role_labels = dict(_DEFAULT_ROLE_LABEL)
        self._pending_messages: List[ChatMessage] | None = None
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(_RENDER_INTERVAL_MS)
        self._render_timer.timeout.connect(self._flush)

    def set_assistant_label(self, label: str) -> None:
        self._role_labels["assistant"] = label or "Assistant"

    def render_messages(self, messages: List[ChatMessage]) -> None:
        self._pending_messages = messages
        if not self._render_timer.isActive():
            self._render_timer.start()

    def flush_now(self) -> None:
        self._render_timer.stop()
        self._flush()

    def _flush(self) -> None:
        messages = self._pending_messages
        if messages is None:
            return
        self._pending_messages = None
        doc = QTextDocument()
        doc.setDefaultStyleSheet(
            "h4 { margin-top: 14px; margin-bottom: 4px; }"
            "p { margin-top: 4px; margin-bottom: 4px; }"
            "pre { background: #eee; padding: 4px; }"
        )
        cursor = QTextCursor(doc)

        for i, msg in enumerate(messages):
            if i > 0:
                cursor.insertBlock()
            self._write_message(cursor, doc, msg)

        self.setDocument(doc)
        self._scroll_to_end()

    def _write_message(self, cursor: QTextCursor, doc: QTextDocument, msg: ChatMessage) -> None:
        label = self._role_labels.get(msg.role, msg.role)
        color = _ROLE_COLOR.get(msg.role, "#444")
        cursor.insertHtml(f'<h4 style="color:{color}">{label}</h4>')

        for block in msg.blocks:
            if isinstance(block, TextBlock):
                if block.text:
                    self._insert_markdown(cursor, block.text)
            elif isinstance(block, ImageBlock):
                self._insert_image(cursor, doc, block.path)

    @staticmethod
    def _insert_markdown(cursor: QTextCursor, markdown: str) -> None:
        scratch = QTextDocument()
        scratch.setMarkdown(markdown)
        cursor.insertBlock()
        cursor.insertFragment(QTextDocumentFragment(scratch))

    def _insert_image(self, cursor: QTextCursor, doc: QTextDocument, path: str) -> None:
        image = QImage(path)
        if image.isNull():
            cursor.insertHtml(f"<p><i>[missing image: {path}]</i></p>")
            return
        if image.width() > self._image_max_width_px:
            image = image.scaledToWidth(
                self._image_max_width_px, Qt.TransformationMode.SmoothTransformation
            )
        resource_url = QUrl(f"sciqlop-chat://{_uuid.uuid4().hex}")
        doc.addResource(QTextDocument.ResourceType.ImageResource, resource_url, image)
        fmt = QTextImageFormat()
        fmt.setName(resource_url.toString())
        cursor.insertBlock()
        cursor.insertImage(fmt)
        cursor.insertBlock()

    def _scroll_to_end(self) -> None:
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())


class ChatInput(QTextEdit):
    _DEFAULT_PLACEHOLDER = (
        "Ask about the current SciQLop state… "
        "(Ctrl+V to paste images, / for commands, ↑↓ history, Ctrl+R search)"
    )

    def __init__(self, tempdir: Path, parent=None):
        super().__init__(parent)
        self._tempdir = Path(tempdir)
        self._tempdir.mkdir(parents=True, exist_ok=True)
        self._pending_images: List[str] = []
        self.setPlaceholderText(self._DEFAULT_PLACEHOLDER)
        self.setAcceptRichText(False)

        self._completer_model = QStringListModel([], self)
        self._completer = QCompleter(self._completer_model, self)
        self._completer.setWidget(self)
        self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.activated.connect(self._insert_completion)

        self._history = PromptHistory()
        self._history_index = -1
        self._draft = ""

        self._search_popup: _HistorySearchPopup | None = None

    def set_completions(self, words: List[str]) -> None:
        self._completer_model.setStringList(sorted(set(words)))

    def _current_slash_token(self) -> str:
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        line = cursor.selectedText()
        stripped = line.lstrip()
        if not stripped.startswith("/"):
            return ""
        token = stripped.split(" ", 1)[0]
        return token

    def _insert_completion(self, completion: str) -> None:
        cursor = self.textCursor()
        token = self._current_slash_token()
        if not token:
            cursor.insertText(completion + " ")
            return
        for _ in range(len(token)):
            cursor.deletePreviousChar()
        cursor.insertText(completion + " ")
        self.setTextCursor(cursor)

    def _navigate_history(self, direction: int) -> bool:
        entries = self._history.entries()
        if not entries:
            return False
        if self._history_index == -1:
            self._draft = self.toPlainText()
        new_index = self._history_index + direction
        if new_index < -1:
            return False
        if new_index >= len(entries):
            return False
        self._history_index = new_index
        if new_index == -1:
            self.setPlainText(self._draft)
        else:
            self.setPlainText(entries[new_index])
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)
        return True

    def _open_history_search(self) -> None:
        if self._search_popup is None:
            self._search_popup = _HistorySearchPopup(self._history, self)
            self._search_popup.prompt_selected.connect(self._on_history_selected)
        self._search_popup.show_at(self)

    def _on_history_selected(self, prompt: str) -> None:
        self.setPlainText(prompt)
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)
        self.setFocus()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        popup = self._completer.popup()
        if popup and popup.isVisible():
            if event.key() in (
                Qt.Key.Key_Return,
                Qt.Key.Key_Enter,
                Qt.Key.Key_Tab,
                Qt.Key.Key_Escape,
                Qt.Key.Key_Up,
                Qt.Key.Key_Down,
            ):
                event.ignore()
                return

        # Ctrl+R → fuzzy history search
        if event.key() == Qt.Key.Key_R and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._open_history_search()
            return

        # Up/Down → history navigation (only when cursor is on first/last line)
        if event.key() == Qt.Key.Key_Up and self._cursor_on_first_line():
            if self._navigate_history(1):
                return
        if event.key() == Qt.Key.Key_Down and self._cursor_on_last_line():
            if self._navigate_history(-1):
                return

        super().keyPressEvent(event)
        token = self._current_slash_token()
        if len(token) >= 1 and self._completer_model.rowCount() > 0:
            self._completer.setCompletionPrefix(token)
            rect = self.cursorRect()
            rect.setWidth(
                self._completer.popup().sizeHintForColumn(0)
                + self._completer.popup().verticalScrollBar().sizeHint().width()
            )
            self._completer.complete(rect)
        else:
            if popup:
                popup.hide()

    def _cursor_on_first_line(self) -> bool:
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        return cursor.atStart()

    def _cursor_on_last_line(self) -> bool:
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.EndOfLine)
        return cursor.atEnd()

    def canInsertFromMimeData(self, source: QMimeData) -> bool:
        if source.hasImage() or source.hasUrls():
            return True
        return super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source: QMimeData) -> None:
        if source.hasImage():
            image = source.imageData()
            if isinstance(image, QImage) and not image.isNull():
                self._attach_image(image)
                return
        if source.hasUrls():
            handled = False
            for url in source.urls():
                if url.isLocalFile():
                    path = url.toLocalFile()
                    if self._looks_like_image(path):
                        image = QImage(path)
                        if not image.isNull():
                            self._attach_image(image)
                            handled = True
            if handled:
                return
        super().insertFromMimeData(source)

    def _attach_image(self, image: QImage) -> None:
        path = self._tempdir / f"paste_{_uuid.uuid4().hex}.png"
        if not image.save(str(path), "PNG"):
            return
        self._pending_images.append(str(path))
        cursor = self.textCursor()
        cursor.insertText(f"[image:{path.name}] ")
        self.setTextCursor(cursor)

    @staticmethod
    def _looks_like_image(path: str) -> bool:
        return Path(path).suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}

    def take_payload(self) -> tuple[str, List[str]]:
        body = self.toPlainText().strip()
        for path in self._pending_images:
            body = body.replace(f"[image:{Path(path).name}]", "").strip()
        images = list(self._pending_images)
        self._pending_images.clear()
        self.clear()
        self._history_index = -1
        self._draft = ""
        if body:
            self._history.add(body)
        return body, images


class _HistorySearchPopup(QWidget):
    """Overlay popup for fuzzy-searching prompt history (Ctrl+R)."""

    from PySide6.QtCore import Signal
    prompt_selected = Signal(str)

    def __init__(self, history: PromptHistory, parent: QWidget):
        super().__init__(parent, Qt.WindowType.Popup)
        self._history = history

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self._input = QLineEdit(self)
        self._input.setPlaceholderText("Search history…")
        self._input.textChanged.connect(self._on_query_changed)
        self._input.installEventFilter(self)
        layout.addWidget(self._input)

        self._list = QListView(self)
        self._model = QStandardItemModel(self)
        self._list.setModel(self._model)
        self._list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._list.clicked.connect(self._on_item_clicked)
        layout.addWidget(self._list)

        self.setMinimumWidth(400)
        self.setMaximumHeight(300)

    def show_at(self, anchor: QWidget) -> None:
        self._input.clear()
        self._refresh_results("")
        pos = anchor.mapToGlobal(anchor.rect().topLeft())
        pos.setY(pos.y() - self.sizeHint().height() - 4)
        self.move(pos)
        self.show()
        self._input.setFocus()

    def _on_query_changed(self, text: str) -> None:
        self._refresh_results(text)

    def _refresh_results(self, query: str) -> None:
        self._model.clear()
        for entry in self._history.search(query, limit=20):
            item = QStandardItem(_truncate(entry, 120))
            item.setData(entry, Qt.ItemDataRole.UserRole)
            item.setEditable(False)
            self._model.appendRow(item)

    def _on_item_clicked(self, index) -> None:
        prompt = index.data(Qt.ItemDataRole.UserRole)
        if prompt:
            self.prompt_selected.emit(prompt)
        self.hide()

    def eventFilter(self, obj, event) -> bool:
        if obj is self._input and isinstance(event, QKeyEvent):
            if event.key() == Qt.Key.Key_Escape:
                self.hide()
                return True
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                idx = self._list.currentIndex()
                if not idx.isValid() and self._model.rowCount() > 0:
                    idx = self._model.index(0, 0)
                if idx.isValid():
                    prompt = idx.data(Qt.ItemDataRole.UserRole)
                    if prompt:
                        self.prompt_selected.emit(prompt)
                self.hide()
                return True
            if event.key() == Qt.Key.Key_Down:
                idx = self._list.currentIndex()
                next_row = (idx.row() + 1) if idx.isValid() else 0
                if next_row < self._model.rowCount():
                    self._list.setCurrentIndex(self._model.index(next_row, 0))
                return True
            if event.key() == Qt.Key.Key_Up:
                idx = self._list.currentIndex()
                if idx.isValid() and idx.row() > 0:
                    self._list.setCurrentIndex(self._model.index(idx.row() - 1, 0))
                return True
        return super().eventFilter(obj, event)


def _truncate(text: str, max_len: int) -> str:
    single_line = text.replace("\n", " ").strip()
    if len(single_line) <= max_len:
        return single_line
    return single_line[:max_len - 1] + "…"
