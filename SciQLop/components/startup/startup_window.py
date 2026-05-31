"""Startup window shown by the launcher during workspace preparation."""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from SciQLop.resources import resource_path

_SPLASH_PATH = resource_path("splash.png")
_SPLASH_PREFERRED_WIDTH = 720  # logical px; Qt scales for DPR automatically
_SPLASH_FALLBACK_ASPECT = 316 / 600  # height / width when the image is missing
_SPLASH_MAX_SCREEN_FRACTION = 0.5  # never cover more than half the screen
_CAPTION_STRIP_PX = 52  # dark strip reserved BELOW the image for one status line
_CAPTION_BG = QColor(15, 17, 22)  # caption background; matches the text bar


class StartupWindow(QWidget):
    """Frameless startup window with progress, warning, and error states."""

    warning_acknowledged = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.SplashScreen | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self._background = QPixmap(_SPLASH_PATH)
        self._show_background = True
        self._build_ui()
        self._enter_progress_state()
        self._apply_size()

    def _apply_size(self) -> None:
        image = self._fit_within_screen(self._preferred_size())
        self.setFixedSize(image.width(), image.height() + _CAPTION_STRIP_PX)

    def _preferred_size(self) -> QSize:
        width = _SPLASH_PREFERRED_WIDTH
        return QSize(width, round(width * self._background_aspect()))

    def _background_aspect(self) -> float:
        if self._background.isNull():
            return _SPLASH_FALLBACK_ASPECT
        return self._background.height() / self._background.width()

    @staticmethod
    def _fit_within_screen(size: QSize) -> QSize:
        """Shrink *size* (keeping aspect) so it never exceeds half the screen
        in either dimension. Logical px throughout — Qt applies the DPR."""
        screen = QApplication.primaryScreen()
        if screen is None:
            return size
        avail = screen.availableGeometry()
        max_w = avail.width() * _SPLASH_MAX_SCREEN_FRACTION
        max_h = avail.height() * _SPLASH_MAX_SCREEN_FRACTION
        ratio = min(max_w / size.width(), max_h / size.height(), 1.0)
        return QSize(round(size.width() * ratio), round(size.height() * ratio))

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addStretch()

        self._warning_banner = QLabel()
        self._warning_banner.setWordWrap(True)
        self._warning_banner.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._warning_banner.setStyleSheet(
            "background: #e6a817; color: #222;"
            "padding: 10px 16px; font-size: 14px; font-weight: bold;"
        )
        layout.addWidget(self._warning_banner)

        # Status text lives in a dark caption strip BELOW the image, so a
        # one-line message never covers the picture. The detail line is hidden
        # when empty; when it has content the bar grows upward over the image
        # bottom — i.e. the picture is only covered when there is more than one
        # line to show.
        self._text_bar = QWidget(self)
        self._text_bar.setStyleSheet(
            "QWidget { background: rgb(15, 17, 22); }"
        )
        text_layout = QVBoxLayout(self._text_bar)
        text_layout.setContentsMargins(16, 10, 16, 12)
        text_layout.setSpacing(4)

        self._phase_label = QLabel()
        self._phase_label.setStyleSheet(
            "color: #ffffff; font-size: 17px; font-weight: bold; background: transparent;"
        )
        text_layout.addWidget(self._phase_label)

        self._detail_label = QLabel()
        self._detail_label.setWordWrap(True)
        self._detail_label.setStyleSheet(
            "color: #f0f2f5; font-size: 14px; background: transparent;"
        )
        text_layout.addWidget(self._detail_label)

        layout.addWidget(self._text_bar)

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
        if self._show_background:
            painter = QPainter(self)
            image_h = self.height() - _CAPTION_STRIP_PX
            if not self._background.isNull():
                painter.drawPixmap(QRect(0, 0, self.width(), image_h), self._background)
            # Fill the strip below the image so a one-line caption sits on a
            # dark band without covering the picture.
            painter.fillRect(QRect(0, image_h, self.width(), _CAPTION_STRIP_PX), _CAPTION_BG)
            painter.end()
        super().paintEvent(event)

    def _enter_progress_state(self) -> None:
        self._text_bar.setVisible(True)
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
        text = text.strip()
        self._detail_label.setText(text)
        # Hide the label entirely when there's nothing to show so the dark bar
        # collapses to just the phase line instead of leaving a blank slot.
        self._detail_label.setVisible(bool(text))

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
        self._text_bar.setVisible(False)
        self._phase_label.setVisible(False)
        self._detail_label.setVisible(False)
        self._error_text.setPlainText(traceback_text)
        self._error_text.setVisible(True)
        self._copy_btn.setVisible(True)
        self._quit_btn.setVisible(True)
        self.setFixedSize(self._fit_within_screen(QSize(700, 500)))
        self.setStyleSheet(
            "StartupWindow { background: #2d2d2d; }"
            "QPushButton { background: #444; color: #eee; border: 1px solid #666;"
            "  padding: 6px 16px; }"
            "QPushButton:hover { background: #555; }"
        )
        # Splash-screen windows have no taskbar entry and don't accept focus,
        # so a hidden splash showing an error is invisible to users.  Switch
        # to a regular top-level window with a title and force it to the
        # front so failed launches can't disappear silently.
        self.hide()
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setWindowTitle("SciQLop — startup failed")
        self.center_on_screen()
        self.show()
        self.raise_()
        self.activateWindow()
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
