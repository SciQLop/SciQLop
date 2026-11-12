"""Deleting a workspace erases its folder: the question must say so, and
answering Cancel must leave the folder alone."""
import pytest
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QMessageBox

from SciQLop.components.welcome import backend as welcome_backend
from SciQLop.components.welcome.backend import WelcomeBackend


class _Manager:
    def __init__(self):
        self.deleted = []

    def delete_workspace(self, directory):
        self.deleted.append(directory)


@pytest.fixture
def manager(monkeypatch):
    stub = _Manager()
    monkeypatch.setattr(welcome_backend, "workspaces_manager_instance", lambda: stub)
    return stub


@pytest.fixture
def backend(qapp):
    instance = WelcomeBackend.__new__(WelcomeBackend)
    QObject.__init__(instance)
    return instance


def _answer(monkeypatch, confirmed: bool):
    monkeypatch.setattr(welcome_backend, "_confirm_workspace_deletion", lambda name: confirmed)


def test_cancel_keeps_the_workspace(backend, manager, monkeypatch):
    _answer(monkeypatch, False)
    changes = []
    backend.workspace_list_changed.connect(lambda: changes.append(True))
    assert backend.delete_workspace("/ws/study", "study") is False
    assert manager.deleted == [] and changes == []


def test_delete_removes_the_workspace(backend, manager, monkeypatch):
    _answer(monkeypatch, True)
    changes = []
    backend.workspace_list_changed.connect(lambda: changes.append(True))
    assert backend.delete_workspace("/ws/study", "study") is True
    assert manager.deleted == ["/ws/study"] and changes == [True]


def test_the_question_says_the_folder_is_erased_and_defaults_to_cancel(qapp):
    box = welcome_backend._workspace_deletion_question("study")
    text = box.text() + " " + box.informativeText()
    assert "study" in text and "notebooks" in text and "cannot be undone" in text
    assert box.defaultButton().text() == "Cancel"
    delete = [b for b in box.buttons() if b.text() == "Delete"]
    assert delete and box.buttonRole(delete[0]) == QMessageBox.ButtonRole.DestructiveRole
