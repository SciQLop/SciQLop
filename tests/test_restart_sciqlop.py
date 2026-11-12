"""Restart and Switch workspace quit through the main window's close, so its
questions (unsaved catalogs, running jobs) are asked and plugins are closed."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from .fixtures import *


class _Window:
    def __init__(self):
        self.codes = []

    def close_then_exit(self, code):
        self.codes.append(code)


@pytest.fixture
def no_window(qapp, monkeypatch):
    monkeypatch.setattr(qapp, "main_window", None, raising=False)
    yield
    qapp._sciqlop_exit_code = 0


@pytest.fixture
def window(qapp, monkeypatch):
    stub = _Window()
    monkeypatch.setattr(qapp, "main_window", stub, raising=False)
    return stub


def test_restart_without_a_window_exits_with_the_launcher_restart_code(qapp, no_window):
    from SciQLop.sciqlop_app import restart_sciqlop
    from SciQLop.sciqlop_launcher import EXIT_RESTART
    with patch("PySide6.QtWidgets.QApplication.exit") as exit_:
        restart_sciqlop()
    exit_.assert_called_once_with(EXIT_RESTART)
    assert qapp._sciqlop_exit_code == EXIT_RESTART


def test_restart_closes_the_window_instead_of_quitting_directly(window):
    from SciQLop.sciqlop_app import restart_sciqlop
    from SciQLop.sciqlop_launcher import EXIT_RESTART
    with patch("PySide6.QtWidgets.QApplication.exit") as exit_:
        restart_sciqlop()
    exit_.assert_not_called()
    assert window.codes == [EXIT_RESTART]


def test_switch_workspace_closes_the_window_instead_of_quitting_directly(window, tmp_path, monkeypatch):
    from SciQLop.sciqlop_app import switch_workspace
    from SciQLop.sciqlop_launcher import EXIT_SWITCH_WORKSPACE, SWITCH_WORKSPACE_FILE
    monkeypatch.setenv("SCIQLOP_WORKSPACE_DIR", str(tmp_path))
    with patch("PySide6.QtWidgets.QApplication.exit") as exit_:
        switch_workspace("other")
    exit_.assert_not_called()
    assert window.codes == [EXIT_SWITCH_WORKSPACE]
    assert (tmp_path / SWITCH_WORKSPACE_FILE).read_text() == "other"


def test_answering_no_to_unsaved_catalogs_keeps_sciqlop_open(qapp, main_window, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from SciQLop.sciqlop_app import restart_sciqlop
    from SciQLop.sciqlop_launcher import EXIT_RESTART
    monkeypatch.setattr("SciQLop.core.ui.mainwindow._dirty_catalog_names", lambda: ["My events"])
    asked = []
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: asked.append(a[1]) or QMessageBox.No)
    with patch("PySide6.QtWidgets.QApplication.exit") as exit_:
        restart_sciqlop()
    exit_.assert_not_called()
    assert "Unsaved catalog changes" in asked
    assert not getattr(main_window, "_closing", False)
    assert getattr(qapp, "_sciqlop_exit_code", 0) != EXIT_RESTART
    main_window.close()  # still refused: the restart request must not linger
    exit_.assert_not_called()


def test_the_window_quits_with_the_requested_code_once_closed(qapp):
    from SciQLop.core.ui.mainwindow import SciQLopMainWindow
    with patch("PySide6.QtWidgets.QApplication.exit") as exit_:
        SciQLopMainWindow._exit_with_requested_code(SimpleNamespace(_exit_code_after_close=64))
        SciQLopMainWindow._exit_with_requested_code(SimpleNamespace(_exit_code_after_close=None))
    exit_.assert_called_once_with(64)
    assert qapp._sciqlop_exit_code == 64
    qapp._sciqlop_exit_code = 0


def test_the_welcome_page_can_restart_sciqlop(monkeypatch):
    from PySide6.QtCore import QObject
    from SciQLop.components.welcome.backend import WelcomeBackend
    calls = []
    monkeypatch.setattr("SciQLop.sciqlop_app.restart_sciqlop", lambda: calls.append(True))
    backend = WelcomeBackend.__new__(WelcomeBackend)
    QObject.__init__(backend)
    backend.restart_sciqlop()
    assert calls == [True]
