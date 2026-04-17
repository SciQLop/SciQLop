"""Generic multi-backend chat dock."""
from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .backend import AgentBackend, BackendContext
from .chat import ChatInput, ChatMessage, ImageBlock, TextBlock, TranscriptView
from .registry import available_backends, create_backend
from .tools import build_sciqlop_tools


@dataclass
class _AgentSession:
    backend: AgentBackend
    messages: List[ChatMessage] = field(default_factory=list)
    resume_id: Optional[str] = None


class AgentChatDock(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self._main_window = main_window
        self._tools = build_sciqlop_tools(main_window)
        self._tempdir = Path(tempfile.mkdtemp(prefix="sciqlop_agents_"))
        self._sessions: Dict[str, _AgentSession] = {}
        self._current: Optional[str] = None
        self._allow_writes = False
        self._turn_task: Optional[asyncio.Task] = None
        self._bg_tasks: set[asyncio.Task] = set()

        self._build_ui()
        self.refresh_backends()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        self._reset_btn = QPushButton("New session")
        self._reset_btn.clicked.connect(self._on_reset)
        header.addWidget(self._reset_btn)

        self._interactive: tuple = ()

        self._backend_combo = QComboBox()
        self._backend_combo.setToolTip("Select which agent backend to chat with.")
        self._backend_combo.currentIndexChanged.connect(self._on_backend_changed)
        header.addWidget(self._backend_combo)

        self._session_combo = QComboBox()
        self._session_combo.setMinimumWidth(220)
        self._session_combo.setToolTip("Resume a previous session for this backend.")
        self._session_combo.currentIndexChanged.connect(self._on_session_picked)
        header.addWidget(self._session_combo)

        self._model_combo = QComboBox()
        self._model_combo.currentIndexChanged.connect(self._on_model_changed)
        header.addWidget(self._model_combo)

        self._writes_toggle = QCheckBox("Allow write actions")
        self._writes_toggle.setToolTip(
            "When enabled, the agent can modify SciQLop state "
            "(set time range, create panels, exec Python, edit notebooks)."
        )
        self._writes_toggle.stateChanged.connect(self._on_writes_toggled)
        header.addWidget(self._writes_toggle)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: gray;")
        header.addWidget(self._status_label, 1)
        layout.addLayout(header)

        self._transcript = TranscriptView(self)
        layout.addWidget(self._transcript, 1)

        input_row = QHBoxLayout()
        self._input = ChatInput(self._tempdir / "pasted", self)
        self._input.setFixedHeight(90)
        input_row.addWidget(self._input, 1)

        self._send_btn = QPushButton("Send")
        self._send_btn.clicked.connect(self._on_send)
        input_row.addWidget(self._send_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setVisible(False)
        self._stop_btn.clicked.connect(self._on_stop)
        input_row.addWidget(self._stop_btn)
        layout.addLayout(input_row)

        QShortcut(QKeySequence("Ctrl+Return"), self._input, activated=self._on_send)
        QShortcut(QKeySequence("Ctrl+Enter"), self._input, activated=self._on_send)

        self._interactive = (
            self._input,
            self._send_btn,
            self._reset_btn,
            self._writes_toggle,
            self._session_combo,
            self._model_combo,
        )

    def refresh_backends(self) -> None:
        names = available_backends()
        current = self._current
        self._backend_combo.blockSignals(True)
        self._backend_combo.clear()
        for name in names:
            self._backend_combo.addItem(name, name)
        self._backend_combo.blockSignals(False)
        if not names:
            self._set_empty(
                "No agent backends registered. Install sciqlop_claude or a "
                "similar plugin to enable the chat."
            )
            return
        self._set_enabled()
        target = current if current in names else names[0]
        idx = names.index(target)
        self._backend_combo.setCurrentIndex(idx)
        self._on_backend_changed(idx)

    def _set_empty(self, reason: str) -> None:
        self._transcript.render_messages(
            [ChatMessage(role="error", blocks=[TextBlock(text=reason)], done=True)]
        )
        for w in self._interactive:
            w.setEnabled(False)

    def _set_enabled(self) -> None:
        for w in self._interactive:
            w.setEnabled(True)

    def _set_status(self, text: str) -> None:
        self._status_label.setText(text)

    def _on_backend_changed(self, index: int) -> None:
        name = self._backend_combo.itemData(index)
        if not name:
            return
        self._current = name
        session = self._sessions.get(name) or self._create_session(name)
        self._sessions[name] = session
        self._bind_to_session(session)

    def _create_session(self, name: str) -> _AgentSession:
        be_tempdir = self._tempdir / name / "tool_images"
        be_tempdir.mkdir(parents=True, exist_ok=True)
        ctx = BackendContext(
            main_window=self._main_window,
            tools=self._tools,
            tempdir=be_tempdir,
            confirm_cb=self._confirm_tool_call,
            allow_writes=self._allow_writes,
        )
        backend = create_backend(name, ctx)
        return _AgentSession(backend=backend)

    def _bind_to_session(self, session: _AgentSession) -> None:
        be = session.backend
        self._transcript.set_assistant_label(be.display_name)
        self._populate_models(be)
        self._populate_session_list(be)
        self._transcript.render_messages(session.messages)
        self._transcript.flush_now()
        self._spawn(self._refresh_completions())
        on_activated = getattr(be, "on_activated", None)
        if on_activated is not None:
            try:
                on_activated()
            except Exception:
                pass

    def reload_backend_models(self) -> None:
        """Re-read `model_choices` from the current backend and repopulate the
        dropdown. Plugins call this after an event that changes the model list
        (e.g. an auth flow that unlocks more models)."""
        if self._current is None:
            return
        session = self._sessions.get(self._current)
        if session is None:
            return
        self._populate_models(session.backend)

    def _populate_models(self, backend: AgentBackend) -> None:
        self._model_combo.blockSignals(True)
        self._model_combo.clear()
        for label, value in backend.model_choices:
            self._model_combo.addItem(label, value)
        self._model_combo.blockSignals(False)

    def _populate_session_list(self, backend: AgentBackend) -> None:
        self._session_combo.blockSignals(True)
        self._session_combo.clear()
        self._session_combo.setVisible(backend.supports_sessions)
        if backend.supports_sessions:
            self._session_combo.addItem("↻ Resume session…", None)
            for entry in backend.list_sessions():
                self._session_combo.addItem(entry.label, entry.id)
        self._session_combo.setCurrentIndex(0)
        self._session_combo.blockSignals(False)

    def _on_model_changed(self, index: int) -> None:
        if self._current is None:
            return
        value = self._model_combo.itemData(index)
        backend = self._sessions[self._current].backend
        self._spawn(backend.set_model(value))
        self._set_status(f"Model → {self._model_combo.currentText()}")

    def _on_writes_toggled(self, state: int) -> None:
        self._allow_writes = state == Qt.CheckState.Checked.value
        for session in self._sessions.values():
            session.backend.set_allow_writes(self._allow_writes)
        self._set_status(
            "Write actions enabled." if self._allow_writes else "Write actions disabled."
        )

    def _on_reset(self) -> None:
        if self._current is None:
            return
        session = self._sessions[self._current]
        session.messages = []
        session.resume_id = None
        self._purge_replay_tempdir(self._current)
        self._transcript.render_messages(session.messages)
        self._spawn(self._reset_backend(session))

    async def _reset_backend(self, session: _AgentSession) -> None:
        await session.backend.reset()
        self._populate_session_list(session.backend)

    def _on_session_picked(self, index: int) -> None:
        if self._current is None:
            return
        session_id = self._session_combo.itemData(index)
        if not session_id:
            return
        session = self._sessions[self._current]
        backend = session.backend
        if not backend.supports_sessions or session_id == session.resume_id:
            return
        session.resume_id = session_id
        self._purge_replay_tempdir(self._current)
        replay_dir = self._tempdir / self._current / "session_replay"
        session.messages = backend.load_session(session_id, replay_dir)
        self._transcript.render_messages(session.messages)
        self._transcript.flush_now()
        self._set_status(
            f"Resumed session {session_id[:8]} ({len(session.messages)} messages)"
        )
        self._spawn(backend.resume(session_id))

    def _purge_replay_tempdir(self, backend_name: str) -> None:
        shutil.rmtree(self._tempdir / backend_name / "session_replay", ignore_errors=True)

    def _on_send(self) -> None:
        if self._current is None:
            return
        body, image_paths = self._input.take_payload()
        if not body and not image_paths:
            return
        session = self._sessions[self._current]
        user_blocks: list = []
        if body:
            user_blocks.append(TextBlock(text=body))
        for path in image_paths:
            user_blocks.append(ImageBlock(path=path))
        session.messages.append(ChatMessage(role="user", blocks=user_blocks, done=True))
        self._transcript.render_messages(session.messages)
        self._turn_task = asyncio.ensure_future(
            self._run_turn(session, body, image_paths)
        )

    async def _run_turn(
        self, session: _AgentSession, prompt: str, image_paths: list
    ) -> None:
        self._set_running(True)
        self._set_status("Thinking…")
        assistant = ChatMessage(role="assistant", blocks=[], done=False)
        session.messages.append(assistant)
        try:
            async for block in session.backend.ask(prompt, image_paths=image_paths):
                self._append_block(assistant, block)
                if self._is_current(session):
                    self._transcript.render_messages(session.messages)
            assistant.done = True
            if self._is_current(session):
                self._transcript.render_messages(session.messages)
                self._transcript.flush_now()
            self._set_status("Ready.")
        except asyncio.CancelledError:
            session.messages.append(
                ChatMessage(
                    role="error",
                    blocks=[TextBlock(text="(cancelled)")],
                    done=True,
                )
            )
            self._transcript.render_messages(session.messages)
            self._set_status("Cancelled.")
            raise
        except Exception as e:
            session.messages.append(
                ChatMessage(
                    role="error",
                    blocks=[TextBlock(text=f"{type(e).__name__}: {e}")],
                    done=True,
                )
            )
            self._transcript.render_messages(session.messages)
            self._set_status("Error. See history.")
        finally:
            self._set_running(False)
            self._turn_task = None

    def _is_current(self, session: _AgentSession) -> bool:
        return (
            self._current is not None
            and self._sessions.get(self._current) is session
        )

    def _on_stop(self) -> None:
        if self._current is None or self._turn_task is None:
            return
        backend = self._sessions[self._current].backend
        self._spawn(backend.cancel())

    def _set_running(self, running: bool) -> None:
        self._send_btn.setVisible(not running)
        self._stop_btn.setVisible(running)

    @staticmethod
    def _append_block(message: ChatMessage, block) -> None:
        if isinstance(block, TextBlock):
            if message.blocks and isinstance(message.blocks[-1], TextBlock):
                message.blocks[-1].text += block.text
            else:
                message.blocks.append(TextBlock(text=block.text))
        elif isinstance(block, ImageBlock):
            message.blocks.append(block)

    async def _confirm_tool_call(self, tool_name: str, tool_input: dict) -> bool:
        box = QMessageBox(self)
        box.setWindowTitle(f"{self._current}: tool call")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText(f"Allow <b>{tool_name}</b>?")
        preview = json.dumps(tool_input, indent=2, default=str)
        if len(preview) > 2000:
            preview = preview[:2000] + "…"
        box.setDetailedText(preview)
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        box.setDefaultButton(QMessageBox.StandardButton.No)
        future: asyncio.Future = asyncio.Future()

        def _on_finished(_btn):
            if not future.done():
                future.set_result(
                    box.standardButton(box.clickedButton())
                    == QMessageBox.StandardButton.Yes
                )
            box.deleteLater()

        box.finished.connect(_on_finished)
        box.open()
        return await future

    async def _refresh_completions(self) -> None:
        if self._current is None:
            return
        backend = self._sessions[self._current].backend
        try:
            cmds = await backend.list_slash_commands()
        except Exception:
            cmds = []
        self._input.set_completions(cmds)

    def _spawn(self, coro) -> asyncio.Task:
        task = asyncio.ensure_future(coro)
        self._bg_tasks.add(task)
        task.add_done_callback(self._bg_tasks.discard)
        return task

    def closeEvent(self, event):
        shutil.rmtree(self._tempdir, ignore_errors=True)
        super().closeEvent(event)


_DOCK_ATTR = "_sciqlop_agent_dock"


def ensure_agent_dock(main_window) -> AgentChatDock:
    dock = getattr(main_window, _DOCK_ATTR, None)
    if dock is None:
        dock = AgentChatDock(main_window=main_window)
        setattr(main_window, _DOCK_ATTR, dock)
    else:
        dock.refresh_backends()
    return dock
