from PySide6.QtWidgets import QFrame, QLabel, QGraphicsDropShadowEffect, QSizePolicy, QPushButton, QFileDialog
from PySide6.QtGui import QPixmap, QIcon, QImageReader, QPalette
from PySide6.QtCore import QPropertyAnimation, Signal, Qt, QSize
from SciQLop.backend.sciqlop_application import sciqlop_app
import os
from typing import Optional


class FixedSizeImageWidget(QLabel):
    def __init__(self, image_path: Optional[str] = None, icon: Optional[QIcon] = None, width: int = 200,
                 height: int = 200, parent=None):
        super().__init__(parent)
        self._width = width
        self._height = height
        self.set_image(image_path, icon)

    def _load_image_from_file(self, image_path: str, width: int, height: int):
        if os.path.exists(image_path):
            self.setPixmap(QPixmap(image_path).scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.setText(f"Error: {image_path} not found")

    def set_image(self, image_path: Optional[str] = None, icon: Optional[QIcon] = None):
        if image_path:
            self._load_image_from_file(image_path, self._width, self._height)
        elif icon:
            self.setPixmap(icon.pixmap(icon.actualSize(QSize(self._width, self._height))))


class ImageSelector(QPushButton):
    image_selected = Signal(str)

    def __init__(self, current_image: str, parent=None):
        super().__init__(parent)
        self._dialog = None
        self.clicked.connect(self._select_image)
        self.load_image(current_image)
        self.setText("Select Image")

    def _select_image(self):
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.ExistingFile)
        dialog.setNameFilter("Images (*.png *.jpg *.svg *.jpeg)")
        dialog.setViewMode(QFileDialog.Detail)
        dialog.finished.connect(lambda: self.load_image(next(iter(dialog.selectedFiles()), "")))
        dialog.open()
        self._dialog = dialog

    def load_image(self, image_path: str):
        if self._dialog:
            self._dialog.close()
            self._dialog.deleteLater()
            self._dialog = None
        if not os.path.exists(image_path):
            self.setText("Select Image")
        else:
            self.setIcon(QIcon(QPixmap(image_path).scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
            self.setToolTip(f"<img src='{image_path}' width='{sciqlop_app().screens()[0].size().width() // 2}'>")
            self.image_selected.emit(image_path)


class Card(QFrame):
    clicked = Signal()

    def __init__(self, parent=None, width=200, height=220, tooltip=None):
        super().__init__(parent)
        # Style must be applied to the actual class not the base class, like this all derived classes will have the
        # same style
        self.setProperty("selected", False)
        self.setFrameShape(QFrame.Shape.Panel)
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

    @property
    def tooltip(self):
        return self.toolTip()

    @tooltip.setter
    def tooltip(self, value):
        self.setToolTip(value)

    def enterEvent(self, event):
        self._shadow.setOffset(5)
        self._shadow.setColor(Qt.darkGray)
        self.setGraphicsEffect(self._shadow)
        self._animation = QPropertyAnimation(self, b"geometry")
        if self._initial_geometry is None:
            self._initial_geometry = self.geometry()
            factor = 5
            self._destination_geometry = self.geometry().adjusted(-factor, -factor, factor, factor)
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

    def set_selected(self, selected: bool):
        self.setProperty("selected", selected)
        self.style().polish(self)


    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
