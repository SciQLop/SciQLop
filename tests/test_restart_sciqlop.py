"""restart_sciqlop(): quit with the launcher's restart code so it reopens the same workspace."""
from unittest.mock import patch


def test_restart_exits_with_the_launcher_restart_code(qapp):
    from SciQLop.sciqlop_app import restart_sciqlop
    from SciQLop.sciqlop_launcher import EXIT_RESTART
    with patch("PySide6.QtWidgets.QApplication.exit") as exit_:
        restart_sciqlop()
    exit_.assert_called_once_with(EXIT_RESTART)
    assert qapp._sciqlop_exit_code == EXIT_RESTART
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
