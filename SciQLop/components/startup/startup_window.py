"""Startup window shown by the launcher during workspace preparation."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_SPLASH_PATH = ":/splash.png"


class StartupWindow(QWidget):
    """Frameless startup window with progress, warning, and error states."""

    warning_acknowledged = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.SplashScreen | Qt.FramelessWindowHint)
        self._background = QPixmap(_SPLASH_PATH)
        self._show_background = True
        self._build_ui()
        self._enter_progress_state()
        self._apply_size()

    @staticmethod
    def _screen_dpr() -> float:
        screen = QApplication.primaryScreen()
        return screen.devicePixelRatio() if screen else 1.0

    def _apply_size(self) -> None:
        dpr = self._screen_dpr()
        # Scale so the splash is legible on HiDPI — at least 1.5x on >2x DPR
        scale = max(1.0, dpr * 0.75)
        if not self._background.isNull():
            w = int(self._background.width() * scale)
            h = int(self._background.height() * scale)
        else:
            w, h = int(600 * scale), int(316 * scale)
        self.setFixedSize(w, h)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        layout.addStretch()

        self._warning_banner = QLabel()
        self._warning_banner.setWordWrap(True)
        self._warning_banner.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._warning_banner.setStyleSheet(
            "background: #e6a817; color: #222; padding: 8px; font-weight: bold;"
        )
        layout.addWidget(self._warning_banner)

        self._phase_label = QLabel()
        self._phase_label.setStyleSheet(
            "color: white; font-size: 14px; font-weight: bold;"
            "background: rgba(0, 0, 0, 120); padding: 4px;"
        )
        layout.addWidget(self._phase_label)

        self._detail_label = QLabel()
        self._detail_label.setStyleSheet(
            "color: #ccc; font-size: 11px;"
            "background: rgba(0, 0, 0, 80); padding: 2px;"
        )
        layout.addWidget(self._detail_label)

        btn_row = QHBoxLayout()
        self._continue_btn = QPushButton("Continue")
        self._continue_btn.clicked.connect(self._on_continue)
        btn_row.addWidget(self._continue_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._error_text = QPlainTextEdit()
        self._error_text.setReadOnly(True)
        self._error_text.setStyleSheet(
            "background: #1e1e1e; color: #f44; font-family: monospace;"
        )
        layout.addWidget(self._error_text)

        error_btn_row = QHBoxLayout()
        self._copy_btn = QPushButton("Copy to clipboard")
        self._copy_btn.clicked.connect(self._copy_error)
        self._quit_btn = QPushButton("Quit")
        self._quit_btn.clicked.connect(QApplication.quit)
        error_btn_row.addWidget(self._copy_btn)
        error_btn_row.addWidget(self._quit_btn)
        error_btn_row.addStretch()
        layout.addLayout(error_btn_row)

    def paintEvent(self, event) -> None:
        if self._show_background and not self._background.isNull():
            painter = QPainter(self)
            painter.drawPixmap(self.rect(), self._background)
            painter.end()
        super().paintEvent(event)

    def _enter_progress_state(self) -> None:
        self._phase_label.setVisible(True)
        self._detail_label.setVisible(True)
        self._warning_banner.setVisible(False)
        self._continue_btn.setVisible(False)
        self._error_text.setVisible(False)
        self._copy_btn.setVisible(False)
        self._quit_btn.setVisible(False)

    def set_phase(self, text: str) -> None:
        self._phase_label.setText(text)

    def set_detail(self, text: str) -> None:
        self._detail_label.setText(text)

    def show_warning(self, message: str) -> None:
        self._warning_banner.setText(message)
        self._warning_banner.setVisible(True)
        self._continue_btn.setVisible(True)

    def _on_continue(self) -> None:
        self._warning_banner.setVisible(False)
        self._continue_btn.setVisible(False)
        self.warning_acknowledged.emit()

    def show_error(self, traceback_text: str) -> None:
        self._show_background = False
        self._enter_progress_state()
        self._phase_label.setVisible(False)
        self._detail_label.setVisible(False)
        self._error_text.setPlainText(traceback_text)
        self._error_text.setVisible(True)
        self._copy_btn.setVisible(True)
        self._quit_btn.setVisible(True)
        scale = max(1.0, self._screen_dpr() * 0.75)
        self.setFixedSize(int(700 * scale), int(500 * scale))
        self.setStyleSheet(
            "StartupWindow { background: #2d2d2d; }"
            "QPushButton { background: #444; color: #eee; border: 1px solid #666;"
            "  padding: 6px 16px; }"
            "QPushButton:hover { background: #555; }"
        )
        self.center_on_screen()
        self.update()

    def _copy_error(self) -> None:
        QApplication.clipboard().setText(self._error_text.toPlainText())

    def center_on_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(
                geo.x() + (geo.width() - self.width()) // 2,
                geo.y() + (geo.height() - self.height()) // 2,
            )
