"""Web transcript renderer: same public surface as `TranscriptView` (view.py),
rendered client-side in a QWebEngineView (markdown, highlighted code, LaTeX
math, collapsible tool groups) instead of QTextDocument. Selected by the
`transcript_renderer` setting; see chat_dock.py's `_make_transcript`.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, Set

from PySide6.QtCore import QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices

from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.web_channel_page import WebChannelPage

from .render_model import transcript_model
from .view import ChatMessage, _DEFAULT_ROLE_LABEL, _RENDER_INTERVAL_MS

log = getLogger(__name__)

_OPEN_LINK_SCHEMES = ("http://", "https://")


class TranscriptBridge(QObject):
    """QWebChannel-exposed backend. Owns none of the state: it reads and
    mutates it on the `WebTranscriptView` that created it, so Python stays
    the single source of truth (mirrors the native view keeping its own
    `_expanded`/`_tool_verbosity` rather than trusting the DOM)."""

    transcript_changed = Signal(str)

    def __init__(self, view: "WebTranscriptView", parent: Optional[QObject] = None):
        super().__init__(parent)
        self._view = view

    @Slot(str)
    def toggle(self, group_id: str) -> None:
        self._view._on_toggle(group_id)

    @Slot(str)
    def open_link(self, url: str) -> None:
        if url.startswith(_OPEN_LINK_SCHEMES):
            QDesktopServices.openUrl(QUrl(url))
        else:
            log.debug("ignoring non-http(s) link from the transcript: %r", url)

    @Slot(result=str)
    def current_state(self) -> str:
        return self._view._model_json()


class WebTranscriptView(WebChannelPage):
    resources_dir = os.path.join(os.path.dirname(__file__), "..", "resources", "web")
    template_name = "transcript.html.j2"

    def __init__(self, parent=None):
        self._role_labels: Dict[str, str] = dict(_DEFAULT_ROLE_LABEL)
        self._last_messages: List[ChatMessage] = []
        self._pending_messages: Optional[List[ChatMessage]] = None
        self._tool_verbosity = 1
        self._expanded: Set[str] = set()
        super().__init__("Agent Transcript", parent)
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(_RENDER_INTERVAL_MS)
        self._render_timer.timeout.connect(self._flush)

    def _create_backend(self) -> QObject:
        return TranscriptBridge(self)

    def set_tool_verbosity(self, level: int) -> None:
        level = max(1, min(3, int(level)))
        if level != self._tool_verbosity:
            self._tool_verbosity = level
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
        if self._pending_messages is None:
            return
        self._last_messages = self._pending_messages
        self._pending_messages = None
        self.backend.transcript_changed.emit(self._model_json())

    def _on_toggle(self, group_id: str) -> None:
        self._expanded.symmetric_difference_update({group_id})
        self.render_messages(self._last_messages)
        self.flush_now()

    def _model_json(self) -> str:
        model = transcript_model(
            self._last_messages, verbosity=self._tool_verbosity,
            expanded=self._expanded, role_labels=self._role_labels)
        return json.dumps(model)
