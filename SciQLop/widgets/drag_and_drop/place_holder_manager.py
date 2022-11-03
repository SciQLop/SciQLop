from enum import Enum
from PySide6.QtWidgets import QWidget, QMainWindow, QVBoxLayout, QTabBar
from PySide6.QtGui import QDropEvent, QDragEnterEvent, QDragMoveEvent
from PySide6.QtCore import Qt, QPointF, QMimeData, QTimer
from typing import List, Optional, Protocol, Union
from .drop_handler import DropHandler
from .placeholder import PlaceHolder, PlaceHolderPosition


def _place_holder_zone(widget: QWidget, position: QPointF) -> PlaceHolderPosition:
    y = position.y()
    if y < (widget.height() * 0.25):
        return PlaceHolderPosition.TOP
    if y > (widget.height() * 0.75):
        return PlaceHolderPosition.BOTTOM
    return PlaceHolderPosition.NONE


class LayoutLikeWidget(Protocol):
    def indexOf(self, widget: QWidget) -> int:
        ...

    def insertWidget(self, index: int, widget: QWidget) -> None:
        ...

    def count(self) -> int:
        ...


class PlaceHolderManager:
    def __init__(self, widget: LayoutLikeWidget, handlers: List[DropHandler]):
        self._handlers = {h.mime_type: h for h in handlers}
        self._place_holder: Optional[PlaceHolder] = None
        self._current_handler: Optional[DropHandler] = None
        self._place_holder_delay = QTimer()
        self._place_holder_delay.setSingleShot(True)
        self._place_holder_delay.timeout.connect(self._leave_drag)
        self._widget: Union[LayoutLikeWidget, QWidget] = widget
        # assert hasattr(widget, 'indexOf')
        # assert hasattr(widget, 'insertWidget')

    def accepts(self, mime_type: str):
        return mime_type in self._handlers and self._place_holder is None

    def _leave_drag(self):
        self._current_handler = None
        self._place_holder = None

    def leave_drag(self):
        self._place_holder_delay.start(200)

    def create_place_holder_if_needed(self, mime_type: str, child_widget: QWidget, position: QPointF) -> bool:
        if self.accepts(mime_type=mime_type):
            zone = _place_holder_zone(child_widget, position)
            if zone != PlaceHolderPosition.NONE:
                index = self._widget.indexOf(child_widget)
                if zone == PlaceHolderPosition.BOTTOM:
                    index += 1
                place_holder = PlaceHolder(self._widget)
                place_holder.setMinimumHeight(int(self._widget.height() / (self._widget.count() + 1)))
                self._widget.insertWidget(index, place_holder)
                self.register_place_holder(mime_type, place_holder)
                return True
        return False

    def register_place_holder(self, mime_type: str, place_holder: PlaceHolder):
        self._place_holder = place_holder
        self._current_handler = self._handlers.get(mime_type, None)
        place_holder.gotDrop.connect(self.complete_drop_action)
        place_holder.closed.connect(self.leave_drag)

    def complete_drop_action(self, mime_data: QMimeData):
        if self._place_holder is not None and self._current_handler is not None:
            result = self._current_handler.callback(mime_data, self._place_holder)
            self._place_holder.leave()
            return result
