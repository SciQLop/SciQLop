"""Submitting a catalogue as a public one: the server's curators review it, and what they accept is
a copy of the catalogue as it is when submitted; the person's own catalogue stays as it is."""
from __future__ import annotations

import asyncio

import cocat_rs
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel,
                               QLineEdit, QPlainTextEdit, QVBoxLayout)

from SciQLop.components.catalogs import Catalog

from .sharing_dialog import describe

SAVE_TIMEOUT_S = 10  # how long a submission waits for local changes to reach the server


def ask_submission(name: str, folders: list[str], folder: str | None = None) -> dict | None:
    """The filled form, {title, folder, description, note} with None for what was left empty."""
    dialog = QDialog(QApplication.activeWindow())
    dialog.setWindowTitle("Submit as a public catalogue")
    intro = QLabel("The server's curators review it before it is listed under Public catalogues. "
                   "They publish a copy of it as it is now; yours stays as it is.")
    intro.setWordWrap(True)
    title = QLineEdit(name)
    chosen_folder = folder
    folder = QComboBox(editable=True)
    folder.addItems(["", *folders])
    folder.setCurrentText(chosen_folder or "")
    description, note = QPlainTextEdit(), QPlainTextEdit()
    description.setMaximumHeight(90)
    note.setMaximumHeight(70)
    note.setPlaceholderText("For the curators only: where it comes from, how it was made…")
    form = QFormLayout()
    for label, field in (("Title", title), ("Folder", folder), ("Description", description),
                         ("Note to curators", note)):
        form.addRow(label, field)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
    submit = buttons.addButton("Submit", QDialogButtonBox.ButtonRole.AcceptRole)
    title.textChanged.connect(lambda text: submit.setEnabled(bool(text.strip())))
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout = QVBoxLayout(dialog)
    layout.addWidget(intro)
    layout.addLayout(form)
    layout.addWidget(buttons)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    texts = {"title": title.text(), "folder": folder.currentText(),
             "description": description.toPlainText(), "note": note.toPlainText()}
    return {key: text.strip() or None for key, text in texts.items()}


class Submitting:
    """Mixed into the provider: its rooms, catalogues and listed public catalogues are used as they are."""

    def _cannot_submit(self, catalog: Catalog) -> str | None:
        """Why the catalogue cannot be submitted, or None."""
        room_id = self._events_room_id(catalog)
        if catalog.uuid in self._public_views:
            return "it is already public"
        if room_id in self._local_ids:
            return "it is kept on this computer only: move it into your account first"
        if not self._online():
            return "the server cannot be reached"
        if self._cocat_catalogue(catalog) is None:
            return "its project is not loaded"
        return None

    def offer_submission(self, catalog: Catalog, folder: str | None = None) -> None:
        asyncio.ensure_future(self.submit(catalog, folder))

    async def submit(self, catalog: Catalog, folder: str | None = None) -> None:
        reason = self._cannot_submit(catalog)
        if reason is not None:
            self.error_occurred.emit(f"Cannot submit '{catalog.name}' as a public catalogue: {reason}")
            return
        folders = sorted({row["folder"] for row in self._public_views.values() if row.get("folder")})
        filled = ask_submission(catalog.name, folders, folder)
        if filled is None:
            return
        room_id, cocat_cat = self._events_room_id(catalog), self._cocat_catalogue(catalog)
        self.flush_ranges()
        try:
            await asyncio.to_thread(self._rooms[room_id].save, SAVE_TIMEOUT_S)  # submitted as the server has it
            await self._session.call(cocat_rs.raw.submit_catalogue, room_id, cocat_cat.uuid, **filled)
        except Exception as error:
            self.error_occurred.emit(f"Cannot submit '{catalog.name}': {describe(error)}")
            return
        self._tell(f"'{filled['title']}' is submitted: it is listed under Public catalogues once a "
                   f"curator accepts it.")
