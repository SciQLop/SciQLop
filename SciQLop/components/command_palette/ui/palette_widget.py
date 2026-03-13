from __future__ import annotations
from enum import Enum, auto
from PySide6 import QtCore, QtGui, QtWidgets
from SciQLop.components.command_palette.backend.fuzzy import fuzzy_match, fuzzy_score
from SciQLop.components.command_palette.backend.history import LRUHistory
from SciQLop.components.command_palette.backend.registry import CommandRegistry, Completion, PaletteCommand
from SciQLop.components.command_palette.ui.delegate import PaletteItemDelegate

HISTORY_SCORE_BONUS = 10
MAX_VISIBLE_RESULTS = 50
DEBOUNCE_MS = 150


class _State(Enum):
    COMMAND_SELECT = auto()
    ARG_SELECT = auto()


class CommandPalette(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget, registry: CommandRegistry, history: LRUHistory):
        super().__init__(parent)
        self._registry = registry
        self._history = history
        self._state = _State.COMMAND_SELECT
        self._selected_command: PaletteCommand | None = None
        self._arg_step = 0
        self._resolved_args: dict[str, str] = {}
        self._cached_completions: list[Completion] | None = None
        self.setWindowFlags(QtCore.Qt.WindowType.Widget)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.hide()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._input = QtWidgets.QLineEdit(self)
        self._input.setPlaceholderText("Search commands...")
        self._input.textChanged.connect(self._on_text_changed)
        self._input.installEventFilter(self)
        layout.addWidget(self._input)

        self._list = QtWidgets.QListView(self)
        self._model = QtGui.QStandardItemModel(self)
        self._list.setModel(self._model)
        self._list.setItemDelegate(PaletteItemDelegate())
        self._list.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        layout.addWidget(self._list)

        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QtGui.QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)
        self.setStyleSheet("CommandPalette { border: 1px solid palette(mid); border-radius: 6px; }")
        parent.installEventFilter(self)

        self._debounce_timer = QtCore.QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(DEBOUNCE_MS)
        self._debounce_timer.timeout.connect(self._refresh_list)

    def toggle(self):
        if self.isVisible():
            self._close()
        else:
            self._open()

    def _open(self):
        self._reset_state()
        self._reposition()
        parent = self.parentWidget()
        if parent is not None and not parent.isVisible():
            parent.show()
        self.show()
        self.raise_()
        self._input.setFocus()
        self._refresh_list()

    def _close(self):
        self._debounce_timer.stop()
        self.hide()
        self._input.clear()

    def _reset_state(self):
        self._state = _State.COMMAND_SELECT
        self._selected_command = None
        self._arg_step = 0
        self._resolved_args = {}
        self._cached_completions = None
        self._input.clear()
        self._input.setPlaceholderText("Search commands...")

    def _reposition(self):
        parent = self.parentWidget()
        if parent is None:
            return
        pw = parent.width()
        w = int(pw * 0.55)
        x = (pw - w) // 2
        y = 60
        max_h = min(400, parent.height() - y - 20)
        self.setGeometry(x, y, w, max_h)

    def _refresh_list(self):
        query = self._input.text()
        self._model.clear()
        if self._state == _State.COMMAND_SELECT:
            self._populate_command_list(query)
        elif self._state == _State.ARG_SELECT:
            self._populate_arg_list(query)
        if self._model.rowCount() > 0:
            self._list.setCurrentIndex(self._model.index(0, 0))

    def _populate_command_list(self, query: str):
        scored_items: list[tuple[int, str, dict]] = []
        for entry in self._history.entries():
            cmd = self._registry.get(entry.command_id)
            if cmd is None:
                continue
            chain_parts = [cmd.name] + list(entry.resolved_args.values())
            display = " \u2192 ".join(chain_parts)
            score, positions = fuzzy_match(query, display)
            if score > 0:
                scored_items.append((score + HISTORY_SCORE_BONUS, display, {
                    "description": cmd.description, "match_positions": positions,
                    "category": "Recent", "command_id": cmd.id, "history_args": entry.resolved_args,
                }))
        for cmd in self._registry.commands():
            match_text = " ".join([cmd.name] + cmd.keywords)
            score, positions = fuzzy_match(query, match_text)
            if score > 0:
                scored_items.append((score, cmd.name, {
                    "description": cmd.description, "match_positions": positions,
                    "category": "Command", "command_id": cmd.id,
                }))
        scored_items.sort(key=lambda t: t[0], reverse=True)
        for _, display, data in scored_items[:MAX_VISIBLE_RESULTS]:
            item = QtGui.QStandardItem(display)
            item.setData(data, QtCore.Qt.ItemDataRole.UserRole)
            cmd = self._registry.get(data["command_id"])
            if cmd and cmd.icon:
                item.setIcon(cmd.icon)
            item.setEditable(False)
            self._model.appendRow(item)

    def _populate_arg_list(self, query: str):
        if self._selected_command is None:
            return
        arg = self._selected_command.args[self._arg_step]
        if self._cached_completions is None:
            self._cached_completions = arg.completions(self._resolved_args)
        # Two-pass: fast score-only filter, then full match only for top results
        scored = []
        for c in self._cached_completions:
            s = fuzzy_score(query, c.display)
            if s > 0:
                scored.append((s, c))
        scored.sort(key=lambda t: t[0], reverse=True)
        for _, c in scored[:MAX_VISIBLE_RESULTS]:
            _, positions = fuzzy_match(query, c.display)
            item = QtGui.QStandardItem(c.display)
            item.setData({
                "description": c.description or "", "match_positions": positions,
                "category": arg.name, "completion_value": c.value,
            }, QtCore.Qt.ItemDataRole.UserRole)
            if c.icon:
                item.setIcon(c.icon)
            item.setEditable(False)
            self._model.appendRow(item)

    def _on_text_changed(self, _text: str):
        self._debounce_timer.start()

    def _select_current(self):
        index = self._list.currentIndex()
        if not index.isValid():
            if self._state == _State.ARG_SELECT and self._input.text().strip():
                arg_name = self._selected_command.args[self._arg_step].name
                self._resolved_args[arg_name] = self._input.text().strip()
                self._advance_arg_step()
            return
        data = index.data(QtCore.Qt.ItemDataRole.UserRole) or {}
        if self._state == _State.COMMAND_SELECT:
            self._handle_command_select(data)
        elif self._state == _State.ARG_SELECT:
            self._handle_arg_select(data)

    def _handle_command_select(self, data: dict):
        command_id = data.get("command_id")
        if not command_id:
            return
        cmd = self._registry.get(command_id)
        if not cmd:
            return
        history_args = data.get("history_args")
        if history_args is not None:
            self._execute(cmd, history_args)
            return
        if not cmd.args:
            self._execute(cmd, {})
        else:
            self._selected_command = cmd
            self._arg_step = 0
            self._resolved_args = {}
            self._cached_completions = None
            self._state = _State.ARG_SELECT
            self._input.clear()
            self._input.setPlaceholderText(f"Select {cmd.args[0].name}...")
            self._refresh_list()

    def _handle_arg_select(self, data: dict):
        value = data.get("completion_value", "")
        arg_name = self._selected_command.args[self._arg_step].name
        self._resolved_args[arg_name] = value
        self._advance_arg_step()

    def _advance_arg_step(self):
        self._arg_step += 1
        self._cached_completions = None
        if self._arg_step >= len(self._selected_command.args):
            self._execute(self._selected_command, self._resolved_args)
        else:
            self._input.clear()
            next_arg = self._selected_command.args[self._arg_step]
            self._input.setPlaceholderText(f"Select {next_arg.name}...")
            self._refresh_list()

    def _go_back(self):
        if self._state == _State.ARG_SELECT:
            self._cached_completions = None
            if self._arg_step > 0:
                prev_arg = self._selected_command.args[self._arg_step - 1]
                self._resolved_args.pop(prev_arg.name, None)
                self._arg_step -= 1
                self._input.clear()
                self._input.setPlaceholderText(f"Select {self._selected_command.args[self._arg_step].name}...")
                self._refresh_list()
            else:
                self._reset_state()
                self._refresh_list()
        else:
            self._close()

    def _execute(self, cmd: PaletteCommand, args: dict[str, str]):
        self._close()
        self._history.add(cmd.id, args)
        if args:
            cmd.callback(**args)
        else:
            cmd.callback()

    def eventFilter(self, obj, event):
        if obj is self.parentWidget() and event.type() == QtCore.QEvent.Type.Resize:
            if self.isVisible():
                self._reposition()
            return False
        if obj is self._input and event.type() == QtCore.QEvent.Type.KeyPress:
            key = event.key()
            if key == QtCore.Qt.Key.Key_Escape:
                self._go_back()
                return True
            if key == QtCore.Qt.Key.Key_Return:
                self._debounce_timer.stop()
                self._refresh_list()
                self._select_current()
                return True
            if key == QtCore.Qt.Key.Key_Down:
                idx = self._list.currentIndex()
                next_row = idx.row() + 1 if idx.isValid() else 0
                if next_row < self._model.rowCount():
                    self._list.setCurrentIndex(self._model.index(next_row, 0))
                return True
            if key == QtCore.Qt.Key.Key_Up:
                idx = self._list.currentIndex()
                prev_row = idx.row() - 1 if idx.isValid() else 0
                if prev_row >= 0:
                    self._list.setCurrentIndex(self._model.index(prev_row, 0))
                return True
            if key == QtCore.Qt.Key.Key_Backspace and not self._input.text():
                self._go_back()
                return True
        return super().eventFilter(obj, event)

    def showEvent(self, event):
        super().showEvent(event)
        self._reposition()
