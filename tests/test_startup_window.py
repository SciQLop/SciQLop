"""Tests for StartupWindow widget."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from SciQLop.components.startup.startup_window import StartupWindow


@pytest.fixture
def window(qtbot):
    w = StartupWindow()
    qtbot.addWidget(w)
    w.show()
    return w


class TestProgressState:
    def test_initial_state_shows_progress(self, window):
        assert window._phase_label.isVisible()
        assert window._detail_label.isVisible()
        assert not window._warning_banner.isVisible()
        assert not window._error_text.isVisible()

    def test_set_phase_updates_label(self, window):
        window.set_phase("Installing dependencies...")
        assert window._phase_label.text() == "Installing dependencies..."

    def test_set_detail_updates_label(self, window):
        window.set_detail("Resolved 42 packages")
        assert window._detail_label.text() == "Resolved 42 packages"


class TestWarningState:
    def test_show_warning_displays_banner(self, window, qtbot):
        window.show_warning("Missing libxcb-cursor0")
        assert window._warning_banner.isVisible()
        assert "libxcb-cursor0" in window._warning_banner.text()
        assert window._continue_btn.isVisible()

    def test_continue_button_resumes_progress(self, window, qtbot):
        window.show_warning("test warning")
        qtbot.mouseClick(window._continue_btn, Qt.LeftButton)
        assert not window._warning_banner.isVisible()
        assert not window._continue_btn.isVisible()
        assert window._phase_label.isVisible()

    def test_continue_emits_signal(self, window, qtbot):
        window.show_warning("test warning")
        with qtbot.waitSignal(window.warning_acknowledged):
            qtbot.mouseClick(window._continue_btn, Qt.LeftButton)


class TestErrorState:
    def test_show_error_displays_traceback(self, window):
        window.show_error("Traceback (most recent call last):\n  File ...")
        assert window._error_text.isVisible()
        assert "Traceback" in window._error_text.toPlainText()
        assert window._quit_btn.isVisible()
        assert window._copy_btn.isVisible()
        assert not window._phase_label.isVisible()
        assert not window._show_background

    def test_copy_button_copies_to_clipboard(self, window, qtbot):
        window.show_error("some error text")
        qtbot.mouseClick(window._copy_btn, Qt.LeftButton)
        clipboard = QApplication.clipboard()
        assert clipboard.text() == "some error text"


class TestWindowFlags:
    def test_frameless_splash_flags(self, window):
        flags = window.windowFlags()
        assert flags & Qt.SplashScreen
        assert flags & Qt.FramelessWindowHint
