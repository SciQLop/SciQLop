"""The person's tscat catalogues in CoCat: brought in once, at the first start, and again from the
menu. At the first start they go to the account's own project, which is private (the server refuses
to share it). Signed out they go to a project kept on this computer, and the offer to move local
catalogues brings them to the account at the next sign-in."""
from __future__ import annotations

import uuid
from pathlib import Path

import cocat_rs

from SciQLop.components.sciqlop_logging import getLogger

from .locks import lock_on
from .sharing_dialog import describe
from .tscat_import import Imported, TscatBusy, tscat_content

log = getLogger(__name__)

TSCAT_CATALOGUES = "tscat catalogues"  # the project made for them when none is kept on this computer
IMPORT_LOCK = "tscat_import.lock"  # held by the window bringing the tscat catalogues in at its start


class ImportingTscat:
    async def import_tscat_once(self) -> None:
        """Once for the person, not once per window: two windows starting together share the
        folders, and the one that finds the other at it leaves it the work."""
        if self._read_tscat is None or self._local is None:
            return
        only_one_window = lock_on(Path(self._local_dir) / IMPORT_LOCK)
        if not only_one_window.tryLock(0):
            return
        try:
            await self._import_tscat_unless_done()
        finally:
            only_one_window.unlock()

    async def _import_tscat_unless_done(self) -> None:
        if self._local.tscat_imported:
            return
        try:
            await self._bring_tscat_in(None)
        except TscatBusy as error:
            return self._held_elsewhere(error)
        except Exception as error:
            return self._cannot_import_tscat(describe(error))
        self._local.note_tscat_imported()

    def _held_elsewhere(self, error: TscatBusy) -> None:
        """Said once: it lasts as long as the other program runs, and is tried again at each start."""
        if self._local.tscat_busy_told:
            log.info("tscat import postponed: %s", error)
            return
        self._local.note_tscat_busy_told()
        self._cannot_import_tscat(describe(error))

    async def import_tscat_into(self, room_id: str) -> None:
        try:
            imported = await self._bring_tscat_in(room_id)
        except Exception as error:
            return self._cannot_import_tscat(describe(error))
        if not imported:
            self._cannot_import_tscat("there is no tscat catalogue on this computer")

    def _cannot_import_tscat(self, why: str) -> None:
        self.error_occurred.emit(f"Cannot import your tscat catalogues: {why}")

    async def _bring_tscat_in(self, room_id: str | None) -> Imported:
        """Into the given project, else the account's own, else the one kept on this computer.
        Nothing is made or told when tscat holds nothing."""
        text = await self._read_tscat()
        content = tscat_content(text) if text is not None else None
        if not content:
            return Imported()
        room_id = room_id or self._account_project() or await self._room_on_this_computer()
        if room_id in self._local_ids:
            self._local.offer_move_again()
        self.flush_ranges()
        imported = content.write_into(self._rooms[room_id])
        self._rewrap_room(room_id)
        for note in imported.notes:
            log.warning("tscat import: %s", note)
        self._tell(imported.summary(self.folder_display_name([room_id])))
        return imported

    async def _room_on_this_computer(self) -> str:
        """The first project kept on this computer, joined; one is made when there is none."""
        room_id = next((r for r in self._room_infos if r in self._local_ids), None)
        if room_id is None:
            room_id = self._show_new_local_project(TSCAT_CATALOGUES)
        await self.join_room(room_id)
        if room_id in self._elsewhere:
            raise RuntimeError(f"{self._room_infos[room_id].name} is open in another SciQLop window")
        if room_id not in self._rooms:
            raise RuntimeError("the project kept on this computer cannot be opened")
        return room_id

    def _show_new_local_project(self, name: str) -> str:
        info = cocat_rs.ProjectInfo(str(uuid.uuid4()), name, "owner")
        self._local.add_project(info)
        self._local_ids.add(info.id)
        self._room_infos[info.id] = info
        self.folder_added.emit([info.id])
        return info.id
