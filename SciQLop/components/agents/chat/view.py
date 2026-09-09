"""Rich chat widgets: markdown transcript view and image-paste-capable input.

Agent-agnostic: the assistant label and input placeholder can be set by the
dock once it knows which backend is active.
"""
from __future__ import annotations

import json as _json
import uuid as _uuid
from dataclasses import dataclass, field
from html import escape as _html_escape
from pathlib import Path
from typing import List, Literal, Optional, Union

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

from SciQLop.core.ui.shortcuts import native_shortcut_text
from .history import PromptHistory


@dataclass
class TextBlock:
    """Markdown text. ``complete=True`` marks a self-contained markdown unit
    (a whole assistant message); ``False`` marks a streaming delta that the
    dock may merge with the next one."""
    text: str = ""
    complete: bool = False


@dataclass
class ThinkingBlock:
    """Model thinking, rendered dimmed instead of as markdown."""
    text: str = ""
    complete: bool = False


@dataclass
class ImageBlock:
    path: str


@dataclass
class ToolActivityBlock:
    """One tool call the agent made. ``result`` is filled in when the matching
    tool_result arrives (correlated by ``tool_use_id``). ``id`` is stable across
    re-renders so the collapse state survives."""
    tool_name: str = ""
    tool_input: dict = field(default_factory=dict)
    result: Optional[str] = None
    tool_use_id: str = ""
    id: str = field(default_factory=lambda: _uuid.uuid4().hex)


ContentBlock = Union[TextBlock, ThinkingBlock, ImageBlock, ToolActivityBlock]


def _input_one_line(tool_input: dict, cap: int = 80) -> str:
    """A compact single-line preview of a tool call's arguments."""
    if not tool_input:
        return ""
    parts = []
    for k, v in tool_input.items():
        sval = v if isinstance(v, str) else _json.dumps(v, default=str)
        sval = " ".join(str(sval).split())
        parts.append(f"{k}={sval}")
    s = ", ".join(parts)
    return s if len(s) <= cap else s[: cap - 1] + "…"


def activity_group_html(blocks: List["ToolActivityBlock"], level: int,
                        expanded: bool, group_id: str, running: bool = False) -> str:
    """Render a run of tool calls as a collapsible dim block.

    Collapsed: a single summary line. Expanded: one line per call, with an input
    preview at level>=2 and a result summary at level>=3. ``level`` is 1-3."""
    n = len(blocks)
    arrow = "▾" if expanded else "▸"
    if running and blocks:
        head_text = f"● {_html_escape(blocks[-1].tool_name)}… ({n})"
    else:
        head_text = f"🔧 {n} step{'s' if n != 1 else ''}"
    head = (f'<p style="color:#888888;margin:2px 0">'
            f'<a href="toggle:{group_id}" style="color:#888888;text-decoration:none">'
            f'{head_text} {arrow}</a></p>')
    if not expanded:
        return head
    out = [head]
    for b in blocks:
        line = f"&nbsp;&nbsp;▸ {_html_escape(b.tool_name)}"
        if level >= 2:
            preview = _input_one_line(b.tool_input)
            if preview:
                line += f' · <span style="color:#9a9a9a">{_html_escape(preview)}</span>'
        out.append(f'<p style="color:#888888;margin:0 0 0 0">{line}</p>')
        if level >= 3 and b.result:
            res = b.result.strip()
            res = res if len(res) <= 200 else res[:199] + "…"
            out.append('<p style="color:#888888;margin:0">'
                       f'&nbsp;&nbsp;&nbsp;&nbsp;↳ {_html_escape(res)}</p>')
    return "".join(out)


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
        self._last_messages: List[ChatMessage] = []
        self._tool_verbosity = 1
        self._expanded: set[str] = set()
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(_RENDER_INTERVAL_MS)
        self._render_timer.timeout.connect(self._flush)
        self.anchorClicked.connect(self._on_anchor_clicked)

    def set_tool_verbosity(self, level: int) -> None:
        level = max(1, min(3, int(level)))
        if level != self._tool_verbosity:
            self._tool_verbosity = level
            self.render_messages(self._last_messages)

    def _on_anchor_clicked(self, url: QUrl) -> None:
        ref = url.toString()
        if ref.startswith("toggle:"):
            gid = ref[len("toggle:"):]
            self._expanded.symmetric_difference_update({gid})
            self.render_messages(self._last_messages)

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
        self._last_messages = messages
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

        blocks = msg.blocks
        running = not msg.done
        i = 0
        while i < len(blocks):
            block = blocks[i]
            if isinstance(block, ToolActivityBlock):
                run = []
                while i < len(blocks) and isinstance(blocks[i], ToolActivityBlock):
                    run.append(blocks[i])
                    i += 1
                group_id = run[0].id
                cursor.insertBlock()
                cursor.insertHtml(activity_group_html(
                    run, self._tool_verbosity, group_id in self._expanded,
                    group_id, running=running))
                continue
            if isinstance(block, TextBlock):
                if block.text:
                    self._insert_markdown(cursor, block.text)
            elif isinstance(block, ThinkingBlock):
                if block.text:
                    self._insert_thinking(cursor, block.text)
            elif isinstance(block, ImageBlock):
                self._insert_image(cursor, doc, block.path)
            i += 1

    @staticmethod
    def _insert_markdown(cursor: QTextCursor, markdown: str) -> None:
        scratch = QTextDocument()
        scratch.setMarkdown(markdown)
        # insertFragment merges the fragment's first block into the current
        # block, keeping the current block's format — so create the new block
        # with the fragment's first-block format instead of inheriting the
        # previous block's (e.g. the h4 role label's).
        first = scratch.firstBlock()
        cursor.insertBlock(first.blockFormat(), first.charFormat())
        cursor.insertFragment(QTextDocumentFragment(scratch))

    @staticmethod
    def _insert_thinking(cursor: QTextCursor, text: str) -> None:
        body = _html_escape(text.strip()).replace("\n", "<br/>")
        cursor.insertBlock()
        cursor.insertHtml(f'<p style="color:#888888"><i>{body}</i></p>')

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
        # Each flush rebuilds the document via setDocument(), which resets the
        # scroll to the top; the scrollbar's range is only recomputed on the next
        # layout pass, so a single setValue(maximum()) here reads a stale (too
        # small) maximum on a live widget and lands short of the newest message
        # ("scrolls up"). Scroll now (covers the synchronous case) and again on
        # the next event-loop cycle once layout has settled. The text cursor is
        # left untouched so a user's selection survives streaming updates.
        self._scroll_bottom_now()
        QTimer.singleShot(0, self._scroll_bottom_now)

    def _scroll_bottom_now(self) -> None:
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())


class ChatInput(QTextEdit):
    _DEFAULT_PLACEHOLDER = (
        "Ask about the current SciQLop state… "
        f"({native_shortcut_text('Ctrl+V')} to paste images, / for commands, "
        f"↑↓ history, {native_shortcut_text('Ctrl+R')} search)"
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
