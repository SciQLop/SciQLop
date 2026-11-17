"""Where the projects show in SciQLop's catalogue tree, and how their state shows there.

The person's own project is My catalogues itself; projects shared with others go to Shared; public
catalogues to Reference. Signed out, the first project kept on this computer is My catalogues. A
project's state is an icon and its tooltip, not part of its name."""
from __future__ import annotations

from SciQLop.components.catalogs.backend.provider import Placement, Section

from .public import PUBLIC

SIGN_IN_NOTE = "Sign in to see shared projects"
ON_THIS_COMPUTER = "On this computer"  # a project kept here, next to the account's own
OWNER_ROLES = frozenset({"owner", "editor"})


class Placing:
    """Mixed into the provider: its rooms, infos and session are used as they are."""

    def placement(self, folder: str | None) -> Placement | None:
        if folder is None:
            return None  # each project is placed on its own
        if folder == PUBLIC:
            return Placement(Section.REFERENCE, can_create=False)
        info = self._room_infos.get(folder)
        if info is None:
            return Placement(Section.SHARED, can_create=False)
        if self._is_my_catalogues(folder):
            return Placement(Section.MINE, inline=True)
        if folder in self._local_ids:
            return Placement(Section.MINE)
        return Placement(Section.SHARED, can_create=info.role in OWNER_ROLES)

    def folders(self) -> list[list[str]]:
        return [[room_id] for room_id in self._room_infos if room_id not in self._public_ids]

    def _is_my_catalogues(self, room_id: str) -> bool:
        own = next((r for r, i in self._room_infos.items() if i.personal and r not in self._public_ids), None)
        if own is not None:
            return room_id == own
        return room_id == next((r for r in self._room_infos if r in self._local_ids), None)

    def folder_display_name(self, path: list[str]) -> str | None:
        from .public import PUBLIC_FOLDER
        from .provider import MY_CATALOGUES
        if path == [PUBLIC]:
            return PUBLIC_FOLDER
        info = self._room_infos.get(path[0]) if len(path) == 1 else None
        if info is None:
            return None
        if info.name == MY_CATALOGUES and info.id in self._local_ids and not self._is_my_catalogues(info.id):
            return ON_THIS_COMPUTER
        return info.name

    def section_note(self, section: Section) -> str | None:
        if section == Section.SHARED and self._session is not None and not self._session.signed_in:
            return SIGN_IN_NOTE
        if section == Section.MINE:
            return self._my_catalogues_note()
        return None

    def _my_catalogues_note(self) -> str | None:
        mine = next((r for r in self._room_infos if self._is_my_catalogues(r)), None)
        if mine is None or mine in self._rooms or mine not in self._local_ids:
            return None
        if mine in self._elsewhere:
            return ("Open in another SciQLop window: release it there, then right-click "
                    "My catalogues > Open here")
        return "Released: right-click My catalogues > Open here"

    def project_state(self, room_id: str) -> str:
        """The word its icon and tooltip show."""
        if room_id in self._elsewhere:
            return "elsewhere"
        if room_id in self._local_ids:
            return "on this computer" if room_id in self._rooms else "released"
        if room_id not in self._rooms:
            return "not joined"
        if self._room_infos[room_id].role not in OWNER_ROLES:
            return "read-only"
        return self.room_status(room_id)
