from .client import Client
from PySide6.QtCore import QObject, Signal
from typing import Optional, List


class Room(QObject):
    event_added = Signal(object)  # Event
    event_removed = Signal(str)  # event UUID

    def __init__(self, url: str = "https://sciqlop.lpp.polytechnique.fr/cocat/", room_id: Optional[str] = None,
                 parent: Optional[QObject] = None):
        super().__init__(parent)
        self._client = Client(url=url, room_id=room_id, parent=self)
        self._room_id = room_id

    async def join(self) -> bool:
        return await self._client.join_room(self._room_id)

    @property
    def catalogues(self) -> List[str]:
        return [
            cat.name for cat in self._client.db.catalogues
        ]

    def get_catalogue(self, name: str):
        return self._client.db.get_catalogue(name)

    async def close(self):
        await self._client.leave_room()

    @property
    def db(self):
        return self._client.db
