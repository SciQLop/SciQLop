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
    QTextCursor,
    QTextDocument,
    QTextDocumentFragment,
    QTextImageFormat,
)
from PySide6.QtWidgets import QCompleter, QTextBrowser, QTextEdit


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
        "(Ctrl+V to paste images, / for commands)"
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
        return body, images
