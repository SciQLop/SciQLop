from enum import Enum
from PySide6.QtWidgets import QWidget, QMainWindow, QVBoxLayout, QTabBar
from PySide6.QtGui import QDropEvent, QDragEnterEvent, QDragMoveEvent
from PySide6.QtCore import Qt, QPointF
from typing import List, Optional
from .drop_handler import DropHandler
from .placeholder import PlaceHolder, PlaceHolderPosition
from .place_holder_manager import PlaceHolderManager


def _get_parent_ph_manager(widget: QWidget) -> Optional[PlaceHolderManager]:
    if hasattr(widget, "parent_place_holder_manager"):
        return widget.parent_place_holder_manager
    elif hasattr(widget.parent(), "place_holder_manager"):
        return widget.parent().place_holder_manager


class DropHelper:
    def __init__(self, widget: QWidget, handlers: List[DropHandler]):
        self._widget = widget
        self._place_holder_manager: Optional[PlaceHolderManager] = _get_parent_ph_manager(widget)
        self._handlers = {h.mime_type: h for h in handlers}
        self._current_handler: Optional[DropHandler] = None
        self._widget.setAcceptDrops(True)
        self._widget.dragEnterEvent = lambda e: self.dragEnterEvent(e)
        self._widget.dragMoveEvent = lambda e: self.dragMoveEvent(e)
        self._widget.dropEvent = lambda e: self.dropEvent(e)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        self._current_handler = None
        formats = event.mimeData().formats()
        for f in formats:
            if f in self._handlers:
                self._current_handler = self._handlers[f]
                event.acceptProposedAction()
                return
        if isinstance(self._widget, QMainWindow):
            event.accept()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if self._current_handler is not None:
            event.acceptProposedAction()
            if self._place_holder_manager is not None:
                self._place_holder_manager.create_place_holder_if_needed(self._current_handler.mime_type, self._widget,
                                                                         event.position())
        if isinstance(self._widget, QMainWindow):
            child = self._widget.childAt(event.position().toPoint())
            if child is not None and isinstance(child, QTabBar):
                child.setCurrentIndex(child.tabAt(child.mapFromParent(event.position().toPoint())))

    def dropEvent(self, event: QDropEvent) -> None:
        if self._current_handler is not None:
            if self._current_handler.callback(event.mimeData()):
                event.acceptProposedAction()
