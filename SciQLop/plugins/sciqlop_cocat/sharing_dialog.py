"""The "Sharing…" window of a CoCat project: who has access, and, for those the server lets share,
roles, removal and invitations."""
from __future__ import annotations

import asyncio

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .sharing import ASSIGNABLE_ROLES, ProjectSharing, SharingState

ANYONE = "anyone with the link"


async def _settle(coroutine):
    try:
        return await coroutine
    except Exception as error:  # shown in the dialog, which must stay usable
        return error


def describe(error: Exception) -> str:
    return getattr(error, "detail", None) or str(error) or type(error).__name__


def _table(headers: list[str]) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().hide()
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
    table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    return table


def _row(*widgets) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    for widget in widgets:
        layout.addWidget(widget)
    return row


def _roles_combo(current: str | None = None) -> QComboBox:
    combo = QComboBox()
    combo.addItems(ASSIGNABLE_ROLES)
    if current:
        combo.setCurrentText(current)
    return combo


class SharingDialog(QDialog):
    def __init__(self, sharing: ProjectSharing, project_name: str, web_url: str, open_url=None, parent=None):
        super().__init__(parent)
        self._sharing = sharing
        self._state = SharingState(members=[], invitations=[], groups=[], can_manage=False,
                                   editors_can_share=None)
        self.setWindowTitle(f"Sharing: {project_name}")
        self.resize(560, 480)

        self._members = _table(["Member", "Role", ""])
        self._groups = QLabel()
        self._note = QLabel("Only people allowed to share this project can change who has access.")
        self._status = QLabel()
        self._editors_share = QCheckBox("Editors can share this project too")
        self._editors_share.toggled.connect(self.allow_editors_to_share)
        for label in (self._groups, self._note, self._status):
            label.setWordWrap(True)

        self._email = QLineEdit(placeholderText="Email, or leave empty for a link")
        self._invite_role = _roles_combo("viewer")
        invite = QPushButton("Invite")
        invite.clicked.connect(lambda: self.invite_as(self._invite_role.currentText(), self._email.text().strip()))
        self._link = QLineEdit(readOnly=True)
        copy = QPushButton("Copy link")
        copy.clicked.connect(lambda: QGuiApplication.clipboard().setText(self._link.text()))
        self._link_row = _row(self._link, copy)
        self._link_row.hide()
        self._invite_box = QGroupBox("Invite")
        invite_layout = QVBoxLayout(self._invite_box)
        invite_layout.addWidget(_row(self._email, self._invite_role, invite))
        invite_layout.addWidget(self._link_row)

        self._invitations = _table(["Invitation", "Role", "Expires", ""])
        self._invitations_box = QGroupBox("Pending invitations")
        QVBoxLayout(self._invitations_box).addWidget(self._invitations)

        browser = QPushButton("Open in browser")
        browser.clicked.connect(lambda: open_url(web_url) if open_url else None)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        for widget in (self._members, self._groups, self._note, self._editors_share, self._invite_box, self._invitations_box,
                       self._status, _row(browser, refresh, close)):
            layout.addWidget(widget)

    # ---- running server calls ----

    def _run(self, coroutine, then=None, on_error=None) -> None:
        task = asyncio.ensure_future(_settle(coroutine))
        task.add_done_callback(lambda done: self._finish(done.result(), then, on_error))

    def _finish(self, result, then, on_error) -> None:
        if isinstance(result, Exception):
            self._status.setText(f"Refused: {describe(result)}")
            if on_error is not None:
                on_error()
        elif then is not None:
            then(result)

    def _change(self, coroutine, then=None) -> None:
        """A change, then a reload; a refused change reloads too, so the window shows the server's truth."""
        self._status.clear()
        self._run(coroutine, then or (lambda _: self.refresh()), on_error=self.refresh)

    def refresh(self) -> None:
        self._run(self._sharing.load(), self.show_state)

    # ---- actions ----

    def _user_id(self, email: str) -> str:
        return next(m["user_id"] for m in self._state.members if m["email"] == email)

    def choose_role(self, email: str, role: str) -> None:
        self._change(self._sharing.set_role(self._user_id(email), role))

    def remove_member(self, email: str) -> None:
        answer = QMessageBox.question(self, "Remove member", f"Remove {email} from this project?")
        if answer == QMessageBox.StandardButton.Yes:
            self._change(self._sharing.remove(self._user_id(email)))

    def invite_as(self, role: str, email: str) -> None:
        self._change(self._sharing.invite(role, email), self._show_invitation)

    def _show_invitation(self, created: dict) -> None:
        self._email.clear()
        self._link.setText(created.get("link") or created.get("token", ""))
        self._link_row.show()
        self.refresh()

    def revoke_invitation(self, invitation_id: int) -> None:
        self._change(self._sharing.revoke(invitation_id))

    def allow_editors_to_share(self, allowed: bool) -> None:
        self._change(self._sharing.set_editors_can_share(allowed))

    # ---- showing a state ----

    def show_state(self, state: SharingState) -> None:
        self._state = state
        self._fill_members(state)
        self._fill_invitations(state)
        groups = ", ".join(f"{g['name']} ({g['role']})" for g in state.groups)
        self._groups.setText(f"Also shared with groups: {groups}" if groups else "")
        self._groups.setVisible(bool(groups))
        self._note.setVisible(not state.can_manage)
        self._invite_box.setVisible(state.can_manage)
        self._invitations_box.setVisible(state.can_manage)
        self._show_editors_can_share(state.editors_can_share)

    def _show_editors_can_share(self, allowed: bool | None) -> None:
        self._editors_share.setVisible(allowed is not None)
        self._editors_share.blockSignals(True)
        self._editors_share.setChecked(bool(allowed))
        self._editors_share.blockSignals(False)

    def _fill_members(self, state: SharingState) -> None:
        self._members.setRowCount(len(state.members))
        for row, member in enumerate(state.members):
            email, role = member["email"], member["role"]
            self._members.setItem(row, 0, QTableWidgetItem(email))
            self._members.removeCellWidget(row, 1)
            self._members.removeCellWidget(row, 2)
            if state.can_manage and role != "owner":
                combo = _roles_combo(role)
                combo.currentTextChanged.connect(lambda new, e=email: self.choose_role(e, new))
                self._members.setCellWidget(row, 1, combo)
                remove = QPushButton("Remove")
                remove.clicked.connect(lambda _=False, e=email: self.remove_member(e))
                self._members.setCellWidget(row, 2, remove)
            else:
                self._members.setItem(row, 1, QTableWidgetItem(role))
                self._members.setItem(row, 2, QTableWidgetItem(""))

    def _fill_invitations(self, state: SharingState) -> None:
        self._invitations.setRowCount(len(state.invitations))
        for row, invitation in enumerate(state.invitations):
            cells = (invitation.get("email") or ANYONE, invitation["role"], invitation["expires_at"][:10])
            for column, text in enumerate(cells):
                self._invitations.setItem(row, column, QTableWidgetItem(text))
            revoke = QPushButton("Revoke")
            revoke.clicked.connect(lambda _=False, i=invitation["id"]: self.revoke_invitation(i))
            self._invitations.setCellWidget(row, 3, revoke)

    # ---- reading what is shown ----

    def member_rows(self) -> list[tuple[str, str, bool]]:
        rows = []
        for row in range(self._members.rowCount()):
            combo = self._members.cellWidget(row, 1)
            role = combo.currentText() if combo is not None else self._members.item(row, 1).text()
            rows.append((self._members.item(row, 0).text(), role, combo is not None))
        return rows

    def invitation_rows(self) -> list[tuple[str, str, str]]:
        return [tuple(self._invitations.item(row, column).text() for column in range(3))
                for row in range(self._invitations.rowCount())]

    def groups_text(self) -> str:
        return self._groups.text()

    def can_invite(self) -> bool:
        return not self._invite_box.isHidden()

    def invitation_link(self) -> str:
        return self._link.text()

    def editors_can_share(self) -> bool | None:
        return None if self._editors_share.isHidden() else self._editors_share.isChecked()

    def status_text(self) -> str:
        return self._status.text()


def show_sharing_dialog(session, project_id: str, project_name: str, web_url: str, open_url, parent=None):
    dialog = SharingDialog(ProjectSharing(session, project_id), project_name, web_url, open_url, parent)
    dialog.show()
    dialog.refresh()
    return dialog
