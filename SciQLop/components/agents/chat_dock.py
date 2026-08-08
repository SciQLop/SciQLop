"""Generic multi-backend chat dock."""
from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from SciQLop import __version__ as _SCIQLop_VERSION
from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.components.theming import get_icon

from .backend import AgentBackend, BackendContext
from .chat import (
    ChatInput,
    ChatMessage,
    ImageBlock,
    TextBlock,
    ThinkingBlock,
    ToolActivityBlock,
    TranscriptView,
)
from .chat.info_bar import ContextBreakdownPopup, SessionInfoBar
from .chat.popup_placement import place_popup
from .chat.session_panel import SessionListPanel
from .chat.sessions_view import grouped_sessions, all_groups, all_tags, claimed_ids
from .chat.settings_popup import AgentSettingsPopup
from .chat.usage_refresh import UsageRefresher
from .registry import available_backends, create_backend
from .settings import AgentChatSettings, AgentSessionMeta, AgentWriteMode
from .tools import build_sciqlop_tools

log = getLogger(__name__)


_AGENT_ALIGNMENT = (
    "You are an astrophysicist and expert Python developer assisting inside SciQLop.\n"
    "- Be concise, factual, and plain-spoken. Avoid marketing language.\n"
    "- Prefer the public API under SciQLop.user_api (plot, catalogs, themes, virtual_products).\n"
    "- Before writing code, call sciqlop_api_reference('<module>') for the relevant module.\n"
    "- SciQLop's public API changes between releases. Never assume an API limitation "
    "from earlier in this conversation; verify the current API with sciqlop_api_reference "
    "before claiming something is impossible.\n"
    "- Keep code examples minimal, correct, and idiomatic. Use real science intervals when possible.\n"
    "- Do not guess method names or internal module paths.\n"
)


@dataclass
class _AgentSession:
    backend: AgentBackend
    messages: List[ChatMessage] = field(default_factory=list)
    resume_id: Optional[str] = None
    alignment_sent: bool = False
    version_reminder: Optional[str] = None


class AgentChatDock(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Agents")
        self.setWindowIcon(get_icon("assistant"))
        self._main_window = main_window
        self._tools = build_sciqlop_tools(main_window)
        self._tempdir = Path(tempfile.mkdtemp(prefix="sciqlop_agents_"))
        self._sessions: Dict[str, _AgentSession] = {}
        self._current: Optional[str] = None
        self._write_mode = AgentChatSettings().write_mode
        self._session_filter = ""
        self._turn_task: Optional[asyncio.Task] = None
        self._bg_tasks: set[asyncio.Task] = set()
        self._pending_pane_width = 0
        self._pane_width_timer = QTimer(self)
        self._pane_width_timer.setSingleShot(True)
        self._pane_width_timer.setInterval(400)
        self._pane_width_timer.timeout.connect(self._persist_pane_width)
        self._breakdown_popup: Optional[ContextBreakdownPopup] = None
        self._load_task: Optional[asyncio.Task] = None
        self._resume_task: Optional[asyncio.Task] = None
        self._loop = asyncio.get_event_loop()
        self._usage_refresher = UsageRefresher(
            self._current_backend, self._apply_usage_snapshot)

        self._build_ui()
        self._set_writes_combo(self._write_mode)
        self._on_write_mode_changed(0)  # ensure badge text/style is set
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

        self._sessions_toggle = QPushButton("☰ Sessions")
        self._sessions_toggle.setCheckable(True)
        self._sessions_toggle.setToolTip("Show or hide the session list.")
        self._sessions_toggle.toggled.connect(self._on_sessions_toggled)
        header.addWidget(self._sessions_toggle)

        self._settings_popup = AgentSettingsPopup(self)
        self._settings_btn = QPushButton(get_icon("settings"), "")
        self._settings_btn.setToolTip("Model, effort, activity and export options.")
        self._settings_btn.clicked.connect(self._show_settings_popup)
        header.addWidget(self._settings_btn)

        # Aliases so the pre-existing wiring and `_interactive` keep working
        # unchanged now that the popup owns construction.
        self._model_combo = self._settings_popup.model_combo
        self._verbosity_combo = self._settings_popup.verbosity_combo
        self._writes_combo = self._settings_popup.writes_combo
        self._model_combo.currentIndexChanged.connect(self._on_model_changed)
        self._verbosity_combo.currentIndexChanged.connect(self._on_verbosity_changed)
        self._writes_combo.currentIndexChanged.connect(self._on_write_mode_changed)
        self._settings_popup.export_requested.connect(self._on_export)
        self._settings_popup.effort_changed.connect(self._on_effort_changed)

        self._writes_badge = QPushButton(self)
        self._writes_badge.setFlat(True)
        self._writes_badge.setCursor(Qt.CursorShape.PointingHandCursor)
        self._writes_badge.setToolTip(
            "Current write-permission mode. Click to open settings.")
        self._writes_badge.clicked.connect(self._show_settings_popup)
        header.addWidget(self._writes_badge)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: gray;")
        header.addWidget(self._status_label, 1)
        layout.addLayout(header)

        self._splitter = QSplitter(Qt.Orientation.Vertical, self)
        self._splitter.setChildrenCollapsible(False)

        self._transcript = TranscriptView(self._splitter)
        self._splitter.addWidget(self._transcript)
        self._init_tool_verbosity()

        input_panel = QWidget(self._splitter)
        input_column = QVBoxLayout(input_panel)
        input_column.setContentsMargins(0, 0, 0, 0)

        input_row_host = QWidget(input_panel)
        input_row = QHBoxLayout(input_row_host)
        input_row.setContentsMargins(0, 0, 0, 0)

        self._input = ChatInput(self._tempdir / "pasted", input_row_host)
        self._input.setMinimumHeight(60)
        input_row.addWidget(self._input, 1)

        self._send_btn = QPushButton("Send", input_row_host)
        self._send_btn.clicked.connect(self._on_send)
        input_row.addWidget(self._send_btn)

        self._stop_btn = QPushButton("Stop", input_row_host)
        self._stop_btn.setVisible(False)
        self._stop_btn.clicked.connect(self._on_stop)
        input_row.addWidget(self._stop_btn)

        input_column.addWidget(input_row_host)

        self._info_bar = SessionInfoBar(input_panel)
        self._info_bar.details_requested.connect(self._show_context_breakdown)
        input_column.addWidget(self._info_bar)

        self._splitter.addWidget(input_panel)

        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 0)
        self._splitter.setSizes([400, 90])
        self._session_panel = SessionListPanel()
        self._session_panel.session_selected.connect(self._on_session_selected)
        self._session_panel.rename_requested.connect(self._on_session_rename)
        self._session_panel.pin_toggle_requested.connect(self._on_session_pin)
        self._session_panel.filter_changed.connect(self._on_session_filter)
        self._session_panel.move_requested.connect(self._on_session_move)
        self._session_panel.tags_edit_requested.connect(self._on_session_tags)
        self._session_panel.session_delete_requested.connect(self._on_session_delete)
        self._session_panel.session_moved.connect(self._on_session_dropped)
        self._session_panel.group_rename_requested.connect(self._on_group_rename)
        self._session_panel.group_delete_requested.connect(self._on_group_delete)
        self._h_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._h_splitter.addWidget(self._session_panel)
        self._h_splitter.addWidget(self._splitter)
        self._h_splitter.setCollapsible(0, True)
        self._h_splitter.setStretchFactor(1, 1)
        self._h_splitter.splitterMoved.connect(self._on_splitter_moved)
        layout.addWidget(self._h_splitter, 1)
        self._restore_pane_state()

        QShortcut(QKeySequence("Ctrl+Return"), self._input, activated=self._on_send)
        QShortcut(QKeySequence("Ctrl+Enter"), self._input, activated=self._on_send)

        self._interactive = (
            self._input,
            self._send_btn,
            self._reset_btn,
            self._writes_combo,
            self._model_combo,
            self._sessions_toggle,
            self._writes_badge,
        )

    def _set_writes_combo(self, mode: str) -> None:
        index = self._writes_combo.findData(mode)
        if index >= 0:
            self._writes_combo.setCurrentIndex(index)

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
        # `available_backends()` is sorted, so falling straight to names[0]
        # always reopens on whichever backend sorts first rather than the one
        # actually in use — with several installed that is "Albert", which
        # implements none of the usage protocol, leaving the strip blank.
        remembered = AgentChatSettings().last_backend
        target = next((n for n in (current, remembered) if n in names), names[0])
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

    def _show_settings_popup(self) -> None:
        place_popup(self._settings_popup, self._settings_btn)

    def _show_context_breakdown(self) -> None:
        if self._breakdown_popup is None:
            self._breakdown_popup = ContextBreakdownPopup(self)
        self._breakdown_popup.set_snapshot(self._info_bar.snapshot)
        place_popup(self._breakdown_popup, self._info_bar.details_button)
        self._spawn(self._usage_refresher.refresh())

    def _on_effort_changed(self, effort: str) -> None:
        backend = self._current_backend()
        if backend is None:
            return
        with AgentChatSettings() as cfg:
            cfg.effort = {**cfg.effort, backend.display_name: effort}
        self._info_bar.set_effort(effort or None)
        self._push_effort(backend, effort or None)

    def _populate_effort(self, backend) -> None:
        values = ()
        reader = getattr(backend, "effort_values", None)
        if reader is not None:
            try:
                values = reader()
            except Exception:
                values = ()
        stored = AgentChatSettings().effort.get(backend.display_name) or None
        self._settings_popup.set_effort_values(values, stored)
        effort = self._settings_popup.current_effort()
        self._info_bar.set_effort(effort)
        if effort is not None:
            # the restored level is only real once the backend runs at it —
            # showing it in the strip without applying it would assert a state
            # the backend does not have.
            self._push_effort(backend, effort)

    def _push_effort(self, backend, effort: Optional[str]) -> None:
        setter = getattr(backend, "set_effort", None)
        if setter is not None:
            self._spawn(setter(effort))

    def _apply_usage_snapshot(self, snapshot) -> None:
        self._info_bar.set_snapshot(snapshot)
        if self._breakdown_popup is not None and self._breakdown_popup.isVisible():
            self._breakdown_popup.set_snapshot(snapshot)

    def _on_backend_changed(self, index: int) -> None:
        name = self._backend_combo.itemData(index)
        if not name:
            return
        self._current = name
        with AgentChatSettings() as cfg:
            cfg.last_backend = name
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
            write_mode=self._write_mode,
            ask_question_cb=self._ask_question,
        )
        backend = create_backend(name, ctx)
        return _AgentSession(backend=backend)

    def _clear_effort(self) -> None:
        """Drop the previous backend's effort levels from the shared popup.

        The repopulate is async (it awaits a registry refresh that can block for
        ~20s offline) and ⚙ stays reachable throughout, so leaving the old list
        up would let the user pick a level the new backend does not support.
        """
        self._settings_popup.set_effort_values((), None)
        self._info_bar.set_effort(None)

    def _bind_to_session(self, session: _AgentSession) -> None:
        be = session.backend
        self._clear_effort()
        self._transcript.set_assistant_label(be.display_name)
        self._populate_models(be)
        self._spawn(self._prepare_session(be))
        self._populate_session_list(be)
        self._transcript.render_messages(session.messages)
        self._transcript.flush_now()
        on_activated = getattr(be, "on_activated", None)
        if on_activated is not None:
            try:
                on_activated()
            except Exception:
                pass

    async def _prepare_session(self, backend) -> None:
        """Settle effort, then connect, then read usage — strictly in order.

        Effort can only be applied when the SDK client is created, so applying
        it drops any existing client. Run concurrently with the connect step
        that populates the strip, that teardown races the very connection the
        usage read depends on: the client comes up for the slash commands, the
        effort push tears it down, and the read finds nothing. Ordering the
        three removes the race rather than papering over it.
        """
        await self._refresh_capabilities_then_effort(backend)
        if backend is not self._current_backend():
            return
        await self._refresh_completions_then_usage()

    async def _refresh_capabilities_then_effort(self, backend) -> None:
        from .model_capabilities import ensure_registry_fresh

        await ensure_registry_fresh()
        if backend is not self._current_backend():
            return   # the user switched backend while the registry refreshed
        self._populate_effort(backend)

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
        self._session_panel.setVisible(
            backend.supports_sessions and self._sessions_toggle.isChecked())
        self._sessions_toggle.setEnabled(backend.supports_sessions)
        if not backend.supports_sessions:
            self._session_panel.set_groups([])
            return
        current_id = self._live_session_id(self._sessions.get(self._current))
        entries = backend.list_sessions()
        self._archive_claimed(backend, entries)
        groups = grouped_sessions(entries, AgentSessionMeta(),
                                  backend.display_name, self._session_filter,
                                  recent_limit=AgentChatSettings().recent_sessions)
        self._session_panel.set_groups(groups, current_id)

    def _on_model_changed(self, index: int) -> None:
        if self._current is None:
            return
        value = self._model_combo.itemData(index)
        backend = self._sessions[self._current].backend
        self._spawn(self._apply_model(backend, value))
        self._set_status(f"Model → {self._model_combo.currentText()}")

    async def _apply_model(self, backend, value) -> None:
        # effort levels are read back *after* the switch lands: `effort_values()`
        # answers for the model the backend currently holds, so repopulating
        # before the await would narrow the list against the previous model.
        await backend.set_model(value)
        if backend is not self._current_backend():
            return   # the user switched backend while the model switch landed
        self._populate_effort(backend)

    def _on_write_mode_changed(self, index: int) -> None:
        mode = self._writes_combo.currentData() or AgentWriteMode.CONFIRM
        self._write_mode = mode
        for session in self._sessions.values():
            backend = session.backend
            if hasattr(backend, "set_write_mode"):
                backend.set_write_mode(mode)
            elif hasattr(backend, "set_allow_writes"):
                # Older plugins: keep binary compatibility.
                backend.set_allow_writes(mode != AgentWriteMode.NONE)
        with AgentChatSettings() as cfg:
            cfg.write_mode = mode

        badge_texts = {
            AgentWriteMode.NONE: "Writes disabled",
            AgentWriteMode.CONFIRM: "Writes: confirm",
            AgentWriteMode.YOLO: "Yolo",
        }
        badge_styles = {
            AgentWriteMode.NONE: "color: #7f8c8d; border: 1px solid #7f8c8d; border-radius: 4px; padding: 2px 8px;",
            AgentWriteMode.CONFIRM: "color: #f39c12; border: 1px solid #f39c12; border-radius: 4px; padding: 2px 8px;",
            AgentWriteMode.YOLO: "color: #e74c3c; border: 1px solid #e74c3c; border-radius: 4px; padding: 2px 8px;",
        }
        self._writes_badge.setText(badge_texts.get(mode, f"Writes: {mode}"))
        self._writes_badge.setStyleSheet(badge_styles.get(mode, ""))

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

    def _on_session_selected(self, session_id: str) -> None:
        if self._current is None:
            return
        session = self._sessions[self._current]
        backend = session.backend
        if not backend.supports_sessions or session_id == session.resume_id:
            return
        session.resume_id = session_id
        self._purge_replay_tempdir(self._current)
        replay_dir = self._tempdir / self._current / "session_replay"
        self._set_status(f"Loading session {session_id[:8]}…")
        # Session replay can take seconds (it spawns an agent process). Keep it
        # off the Qt main thread so the GUI stays responsive and a later click
        # can supersede the still-running load.
        if self._load_task is not None and not self._load_task.done():
            self._load_task.cancel()
        self._load_task = self._spawn(
            self._load_session_then_render(backend, session_id, replay_dir, session))

    async def _load_session_then_render(
        self,
        backend: AgentBackend,
        session_id: str,
        replay_dir: Path,
        session: _AgentSession,
    ) -> None:
        """Replay a session off the main thread, then render and resume."""
        loader = getattr(backend, "async_load_session", None)
        try:
            if loader is not None:
                messages = await loader(session_id, replay_dir)
            else:
                messages = await self._loop.run_in_executor(
                    None, backend.load_session, session_id, replay_dir)
        except Exception as error:
            log.error("loading session %s failed: %r", session_id, error)
            return
        # Drop the result if the user switched away or clicked another session.
        if session is not self._sessions.get(self._current):
            return
        if session.resume_id != session_id:
            return
        session.messages = messages
        stored_version = AgentSessionMeta().get_sciqlop_version(
            backend.display_name, session_id)
        if stored_version and stored_version != _SCIQLop_VERSION:
            session.version_reminder = (
                f"Note: SciQLop was updated from {stored_version} to "
                f"{_SCIQLop_VERSION} since this session started. API capabilities "
                "may have changed; verify the current API with sciqlop_api_reference "
                "before assuming limitations.\n"
            )
        self._transcript.render_messages(messages)
        self._transcript.flush_now()
        self._set_status(
            f"Resumed session {session_id[:8]} ({len(messages)} messages)")
        # Now reconnect the live backend on the resumed session and refresh usage.
        if self._resume_task is not None and not self._resume_task.done():
            self._resume_task.cancel()
        self._resume_task = self._spawn(
            self._resume_then_refresh(backend, session_id))

    async def _resume_then_refresh(self, backend, session_id: str) -> None:
        """Resume, then rebuild the strip for the session just loaded.

        `resume()` drops the client so the next connect attaches to the resumed
        session. Nothing reconnected or re-read usage afterwards, so the strip
        kept whatever the previous session had left there — and if that was
        nothing, opening a session left it blank for good.
        """
        self._info_bar.set_snapshot(None)     # the old session's figures are gone
        try:
            await backend.resume(session_id)
        except Exception as error:
            log.error("resuming %s failed: %r", session_id, error)
            return
        if backend is not self._current_backend():
            return
        await self._refresh_completions_then_usage()

    def _on_session_rename(self, session_id: str) -> None:
        session = self._sessions.get(self._current)
        if session is None:
            return
        meta = AgentSessionMeta()
        current = meta.get(session.backend.display_name, session_id).name
        name, ok = QInputDialog.getText(self, "Rename session", "Name:", text=current)
        if ok:
            meta.set_name(session.backend.display_name, session_id, name.strip())
            self._populate_session_list(session.backend)

    def _on_session_pin(self, session_id: str) -> None:
        session = self._sessions.get(self._current)
        if session is None:
            return
        meta = AgentSessionMeta()
        cur = meta.get(session.backend.display_name, session_id).pinned
        meta.set_pinned(session.backend.display_name, session_id, not cur)
        self._populate_session_list(session.backend)

    def _current_backend(self):
        session = self._sessions.get(self._current)
        return session.backend if session else None

    def _on_session_filter(self, text: str) -> None:
        self._session_filter = text
        be = self._current_backend()
        if be is not None:
            self._populate_session_list(be)

    def _on_session_dropped(self, session_id: str, group: str) -> None:
        be = self._current_backend()
        if be is None:
            return
        AgentSessionMeta().set_group(be.display_name, session_id, group)
        self._populate_session_list(be)

    def _on_session_move(self, session_id: str) -> None:
        be = self._current_backend()
        if be is None:
            return
        meta = AgentSessionMeta()
        groups = all_groups(be.list_sessions(), meta, be.display_name)
        current = meta.get(be.display_name, session_id).group
        choices = groups + [""] if "" not in groups else groups
        idx = choices.index(current) if current in choices else 0
        name, ok = QInputDialog.getItem(
            self, "Move to group", "Group (blank = Ungrouped):", choices, idx, True)
        if ok:
            meta.set_group(be.display_name, session_id, name.strip())
            self._populate_session_list(be)

    def _on_session_tags(self, session_id: str) -> None:
        be = self._current_backend()
        if be is None:
            return
        meta = AgentSessionMeta()
        current = meta.get(be.display_name, session_id).tags
        known = all_tags(be.list_sessions(), meta, be.display_name)
        text = self._prompt_tags(", ".join(current), known)
        if text is None:
            return
        tags = []
        for raw in text.split(","):
            t = raw.strip()
            if t and t not in tags:
                tags.append(t)
        meta.set_tags(be.display_name, session_id, tags)
        self._populate_session_list(be)

    def _prompt_tags(self, current: str, known: list):
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QLineEdit, QDialogButtonBox, QCompleter, QLabel)
        dlg = QDialog(self)
        dlg.setWindowTitle("Edit tags")
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel("Comma-separated tags:"))
        line = QLineEdit(current)
        completer = QCompleter(known, dlg)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        line.setCompleter(completer)

        def _token(text):
            completer.setCompletionPrefix(text.split(",")[-1].strip())

        def _accept(choice):
            parts = line.text().split(",")
            parts[-1] = " " + choice
            line.setText(", ".join(p.strip() for p in parts if p.strip()))

        line.textEdited.connect(_token)
        completer.activated.connect(_accept)
        v.addWidget(line)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        v.addWidget(buttons)
        return line.text() if dlg.exec() else None

    def _on_group_rename(self, old: str) -> None:
        be = self._current_backend()
        if be is None:
            return
        new, ok = QInputDialog.getText(self, "Rename group", "New name:", text=old)
        if ok:
            AgentSessionMeta().rename_group(be.display_name, old, new.strip())
            self._populate_session_list(be)

    def _on_group_delete(self, group: str) -> None:
        be = self._current_backend()
        if be is None:
            return
        if QMessageBox.question(
                self, "Delete group",
                f"Ungroup all sessions in '{group}'? (sessions are kept)"
        ) == QMessageBox.StandardButton.Yes:
            AgentSessionMeta().delete_group(be.display_name, group)
            self._populate_session_list(be)

    def _on_session_delete(self, session_id: str) -> None:
        be = self._current_backend()
        if be is None:
            return
        delete = getattr(be, "delete_session", None)
        if delete is None:
            self._set_status(f"{be.display_name} cannot delete sessions")
            return
        if self._live_session_id(self._sessions.get(self._current)) == session_id:
            self._set_status("Cannot delete the session you are in")
            return
        name = AgentSessionMeta().get(be.display_name, session_id).name or session_id
        if QMessageBox.question(
                self, "Delete session",
                f"Delete '{name}' for good? Its transcript and archived copy "
                "are erased and cannot be recovered."
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            delete(session_id)
        except Exception as error:
            log.warning("deleting session %s failed: %r", session_id, error)
        AgentSessionMeta().forget(be.display_name, session_id)
        self._populate_session_list(be)

    def _live_session_id(self, session: Optional[_AgentSession]) -> Optional[str]:
        """Which session is being written to — the backend knows better than the
        dock, which only learns an id when the user resumes one explicitly."""
        if session is None:
            return None
        reported = getattr(session.backend, "current_session_id", None)
        try:
            return (reported() if reported is not None else None) or session.resume_id
        except Exception as error:
            log.warning("backend could not report its session: %r", error)
            return session.resume_id

    def _archive_claimed(self, backend: AgentBackend, entries) -> None:
        """Ask the backend to keep the sessions the user claimed. Best effort:
        a failure here must never break rendering the list."""
        archive = getattr(backend, "archive_sessions", None)
        if archive is None:
            return
        try:
            archive(claimed_ids(entries, AgentSessionMeta(), backend.display_name))
        except Exception as error:
            log.warning("archiving sessions failed: %r", error)

    def _on_sessions_toggled(self, checked: bool) -> None:
        self._session_panel.setVisible(
            checked and self._current_supports_sessions())
        with AgentChatSettings() as cfg:
            cfg.sessions_pane_visible = checked

    def _on_splitter_moved(self, *_args) -> None:
        sizes = self._h_splitter.sizes()
        if sizes and sizes[0] > 0:
            self._pending_pane_width = int(sizes[0])
            self._pane_width_timer.start()

    def _persist_pane_width(self) -> None:
        if self._pending_pane_width > 0:
            with AgentChatSettings() as cfg:
                cfg.sessions_pane_width = self._pending_pane_width

    def _current_supports_sessions(self) -> bool:
        session = self._sessions.get(self._current)
        return bool(session and session.backend.supports_sessions)

    def _restore_pane_state(self) -> None:
        cfg = AgentChatSettings()
        self._sessions_toggle.blockSignals(True)
        self._sessions_toggle.setChecked(cfg.sessions_pane_visible)
        self._sessions_toggle.blockSignals(False)
        width = max(120, int(cfg.sessions_pane_width))
        self._h_splitter.setSizes([width, max(width, 600)])
        self._session_panel.setVisible(cfg.sessions_pane_visible)

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
        if not session.alignment_sent:
            prompt = f"{_AGENT_ALIGNMENT}\n{prompt}"
            session.alignment_sent = True
        if session.version_reminder:
            prompt = f"{session.version_reminder}{prompt}"
            session.version_reminder = None
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
            session_id = session.backend.current_session_id()
            if session_id is not None:
                AgentSessionMeta().set_sciqlop_version(
                    session.backend.display_name, session_id, _SCIQLop_VERSION)
            self._set_status("Ready.")
            self._spawn(self._usage_refresher.refresh())
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
            self._sessions_after_turn(session)

    def _sessions_after_turn(self, session: _AgentSession) -> None:
        """A new session reaches disk only once its first turn lands, so without
        a rebuild here the conversation in progress is missing from the panel —
        and a claimed session's archived copy would lag a turn behind."""
        if self._is_current(session):
            self._populate_session_list(session.backend)  # archives as it goes
            return
        try:
            self._archive_claimed(session.backend, session.backend.list_sessions())
        except Exception as error:
            log.warning("listing sessions for archiving failed: %r", error)

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
        if isinstance(block, (TextBlock, ThinkingBlock)):
            last = message.blocks[-1] if message.blocks else None
            if type(last) is type(block) and not last.complete:
                last.text += block.text
                last.complete = block.complete
            else:
                message.blocks.append(block)
        elif isinstance(block, ImageBlock):
            message.blocks.append(block)
        elif isinstance(block, ToolActivityBlock):
            # a result-only block (tool_use_id set, result filled) merges into the
            # matching tool call; otherwise it's a new call to append.
            if block.result is not None and block.tool_use_id:
                match = next(
                    (b for b in message.blocks
                     if isinstance(b, ToolActivityBlock)
                     and b.tool_use_id == block.tool_use_id), None)
                if match is not None:
                    match.result = block.result
                    return
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

    async def _ask_question(self, questions: list) -> dict:
        """Render the model's AskUserQuestion inline and await the user's answers."""
        from .chat.question_card import QuestionCard

        card = QuestionCard(questions, self)
        future: asyncio.Future = asyncio.Future()

        def _on_answered(answers: dict) -> None:
            if not future.done():
                future.set_result(answers)

        card.answered.connect(_on_answered)
        self.layout().addWidget(card)
        try:
            return await future
        finally:
            card.setParent(None)
            card.deleteLater()

    def _on_export(self) -> None:
        if self._current is None:
            return
        messages = self._sessions[self._current].messages
        if not messages:
            QMessageBox.information(self, "Export transcript", "Nothing to export yet.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export transcript", f"{self._current}.md", "Markdown (*.md)")
        if not path:
            return
        from .chat.export_md import transcript_to_markdown
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(transcript_to_markdown(messages, title=self._current))
        except OSError as e:
            QMessageBox.warning(self, "Export failed", str(e))

    def _init_tool_verbosity(self) -> None:
        level = AgentChatSettings().tool_verbosity
        self._verbosity_combo.blockSignals(True)
        self._verbosity_combo.setCurrentIndex(max(0, min(2, level - 1)))
        self._verbosity_combo.blockSignals(False)
        self._transcript.set_tool_verbosity(level)

    def _on_verbosity_changed(self, index: int) -> None:
        level = index + 1
        self._transcript.set_tool_verbosity(level)
        with AgentChatSettings() as s:
            s.tool_verbosity = level

    async def _refresh_completions_then_usage(self) -> None:
        """Ask for usage only after the backend has had a reason to connect.

        `list_slash_commands` is what first brings the SDK client up, and a
        backend can only report context once connected. Spawning both at bind
        let the usage refresh win the race and report nothing, leaving the strip
        blank until the first turn finished.
        """
        await self._refresh_completions()
        await self._usage_refresher.refresh()

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
        task.add_done_callback(self._retire_task)
        return task

    def _retire_task(self, task: asyncio.Task) -> None:
        """Drop the strong reference and consume the task's exception.

        Background tasks are fire-and-forget (effort/model pushes, usage
        refreshes); an unretrieved exception would only surface as a bare
        "Task exception was never retrieved" at GC time.
        """
        self._bg_tasks.discard(task)
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            log.error("agent chat background task failed: %r", error)

    def closeEvent(self, event):
        # Continuations touch widgets (settings popup, info strip, breakdown
        # popup); once the dock is gone those are deleted C++ objects and any
        # late write raises RuntimeError from Shiboken.
        for task in list(self._bg_tasks):
            task.cancel()
        shutil.rmtree(self._tempdir, ignore_errors=True)
        super().closeEvent(event)


_DOCK_ATTR = "_sciqlop_agent_dock"
_UI_READY_ATTR = "_sciqlop_agent_ui_ready"
_DOCK_TITLE = "Agents"


def ensure_agent_dock(main_window) -> AgentChatDock:
    """Return the single shared agent chat dock, creating it and registering
    its whole UI (docked panel, toolbar button, Tools-menu entry) on first
    call.

    Backend plugins (sciqlop_claude, sciqlop_albert, sciqlop_copilot,
    sciqlop_opencode, …) must only ``register_agent_backend(...)`` and call
    this — they must NOT register any UI themselves. The chat UI is central
    and owned by core, so it appears exactly once no matter how many backends
    are installed.
    """
    dock = getattr(main_window, _DOCK_ATTR, None)
    if dock is None:
        dock = AgentChatDock(main_window=main_window)
        setattr(main_window, _DOCK_ATTR, dock)
    else:
        dock.refresh_backends()
    _register_agent_ui(main_window, dock)
    return dock


def _register_agent_ui(main_window, dock) -> None:
    """Register the shared chat UI exactly once, idempotently across repeated
    ``ensure_agent_dock`` calls from every installed backend plugin."""
    if getattr(main_window, _UI_READY_ATTR, False):
        return
    if _dock_agent_panel(main_window, dock) is None:
        return
    setattr(main_window, _UI_READY_ATTR, True)


def _dock_agent_panel(main_window, dock):
    """Add the chat panel as a left auto-hide side panel — wired exactly like
    the product tree, catalogs, settings and plot-properties panels (a left
    sidebar tab plus a View-menu toggle). The ``assistant`` window icon set on
    the panel becomes the tab icon."""
    dock_manager = getattr(main_window, "dock_manager", None)
    if dock_manager is None:
        return None
    main_window.add_side_pan(dock)
    return dock_manager.findDockWidget(_DOCK_TITLE)
