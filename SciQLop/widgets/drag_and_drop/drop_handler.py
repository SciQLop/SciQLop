from PySide6.QtCore import QMimeData

from typing import Callable


class DropHandler:
    __slots__ = ["mime_type", "callback"]

    def __init__(self, mime_type: str, callback: Callable[[QMimeData, ...], bool]):
        self.mime_type = mime_type
        self.callback = callback
