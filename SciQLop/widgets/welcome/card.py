from PySide6.QtWidgets import QFrame, QLabel, QGraphicsDropShadowEffect
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtCore import QPropertyAnimation, Signal, Qt, QSize
import os
from typing import Optional


class ImageWidget(QLabel):
    def __init__(self, image_path: Optional[str] = None, icon: Optional[QIcon] = None, width: int = 200,
                 height: int = 200, parent=None):
        super().__init__(parent)
        if image_path:
            self._load_image_from_file(image_path, width, height)
        elif icon:
            self.setPixmap(icon.pixmap(icon.actualSize(QSize(width, height))))

    def _load_image_from_file(self, image_path: str, width: int, height: int):
        if os.path.exists(image_path):
            self.setPixmap(QPixmap(image_path).scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.setText(f"Error: {image_path} not found")


class Card(QFrame):
    clicked = Signal()

    def __init__(self, parent=None, width=200, height=220, tooltip=None):
        super().__init__(parent)
        # Style must be applied to the actual class not the base class, like this all derived classes will have the
        # same style
        self.setStyleSheet(f".{self.__class__.__name__}{{background-color: white; border-radius: 5px;}}")
        self._shadow = QGraphicsDropShadowEffect()
        self._shadow.setBlurRadius(5)
        self._shadow.setOffset(2)
        self._shadow.setColor(Qt.gray)
        self.setGraphicsEffect(self._shadow)
        self.setMaximumSize(width, height)
        self.setMinimumSize(width, height)
        self._initial_geometry = None
        self._destination_geometry = None
        if tooltip is not None:
            self.setToolTip(tooltip)

    def enterEvent(self, event):
        self._shadow.setOffset(5)
        self._shadow.setColor(Qt.darkGray)
        self.setGraphicsEffect(self._shadow)
        self._animation = QPropertyAnimation(self, b"geometry")
        if self._initial_geometry is None:
            self._initial_geometry = self.geometry()
            self._destination_geometry = self.geometry().adjusted(-5, -5, 5, 5)
        self._animation.setStartValue(self._initial_geometry)
        self._animation.setDuration(100)
        self._animation.setEndValue(self._destination_geometry)
        self._animation.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._shadow.setOffset(2)
        self._shadow.setColor(Qt.gray)
        self.setGraphicsEffect(self._shadow)
        self._animation = QPropertyAnimation(self, b"geometry")
        self._animation.setDuration(100)
        self._animation.setStartValue(self._destination_geometry)
        self._animation.setEndValue(self._initial_geometry)
        self._animation.start()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
