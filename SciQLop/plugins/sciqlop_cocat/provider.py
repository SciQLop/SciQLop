"""SciQLop catalog provider backed by cocat-rs rooms.

Each joined room is a folder (``path[0]`` is the room id). Signed out, it shows "My catalogues": the
last account's own project from its cache, else a project kept on this computer only. The first sign-in
that finds catalogues on this computer offers to move them into the account's own project. A project
kept on this computer is open in one SciQLop window at a time: the window holds its lock. The caches
of the server's projects belong to the first window; a later one keeps its own while it runs. Local edits are written to the room by
uuid; they do not come back from the room, so every edit updates the SciQLop side itself too.
Remote changes are applied by ``remote.RoomListener`` inside :meth:`remote_changes`.
"""
from __future__ import annotations

import asyncio
import json
from html import escape
import shutil
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import cocat_rs
from PySide6.QtCore import QObject, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox

from SciQLop.components.catalogs import Capability, Catalog, CatalogEvent, CatalogProvider, ProviderAction
from SciQLop.components.catalogs.backend.provider import _SENTINEL, NodeType
from SciQLop.components.sciqlop_logging import getLogger
from speasy.core import make_utc_datetime

from .history import when_text
from . import tips
from .history_dialog import ask_text, show_history_dialog
from . import questions
from .icons import status_badge
from .transfer import NeedsValueRange, export_catalogue, import_file, tscat_available
from .locks import lock_on
from .remembered import Remembered
from .public import PUBLIC, PUBLIC_FOLDER, Following, as_info
from .links import Linking
from .searches import Searching
from .all_events import ShowingAllEvents
from .submission import Submitting
from .tscat_first_start import ImportingTscat
from .sections import Placing
from .rereading import Rereading, Snapshot
from .sharing_dialog import describe, show_sharing_dialog
from .convert import (
    SCHEMA_ATTR_PREFIX,
    SUBPATH_ATTR,
    TSCAT_PATH_ATTR,
    subpath_of,
    encode_subpath,
    schema_specs,
    rows_of,
    split_typed_meta,
    typed_fields,
    typed_meta,
)

log = getLogger(__name__)

PROVIDER_NAME = "Catalogs (cocat-rs)"
MY_CATALOGUES = "My catalogues"
RANGE_DEBOUNCE_MS = 100
SYNC_STALL_MS = 30_000  # a joined room not synced by then is reported once
SAVE_TIMEOUT_S = 10  # how long a version waits for local changes to reach the server
SMART_REFRESH_MS = 200  # smart catalogues are re-read this long after the last edit in their room
PUBLIC_REFRESH_MS = 5 * 60 * 1000  # the public catalogues change on the server with no sign here
SIGN_IN_TO_SEARCH = "sign in to search the public catalogues: only the events picked here show"
LOCK_SUFFIX = ".lock"  # next to a project kept on this computer: held by the window that has it open
CACHE_LOCK = "sciqlop_cache.lock"  # held by the window that uses the shared caches of the server's projects
OTHER_WINDOWS = "other_windows"  # in the cache folder: one folder per later window
LEAVE_SAVE_S = 2  # how long a later window waits, per project it closes, for the server to have its changes

open_room = cocat_rs.Project.open  # module-level so tests can keep projects off the network


def open_url(url: str) -> None:
    QDesktopServices.openUrl(QUrl(url))


def show_sign_in_box(sign_in) -> QMessageBox:
    """Non-modal: SciQLop stays usable while the person answers in the browser. Cancel stops waiting."""
    box = QMessageBox(QMessageBox.Icon.Information, "Sign in to CoCat",
                      f"Your browser shows the CoCat sign-in page. Check that it shows the code "
                      f"<b>{sign_in.code}</b>, then press Allow there.<br><br>"
                      f"If no page opened, go to:<br>{sign_in.url}",
                      QMessageBox.StandardButton.Cancel, QApplication.activeWindow())
    box.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    box.rejected.connect(sign_in.cancel)
    box.show()
    return box


def ask_project_name() -> str | None:
    name, ok = QInputDialog.getText(QApplication.activeWindow(), "New CoCat project", "Project name:")
    return name.strip() if ok and name.strip() else None


def action(name: str, callback, tooltip: str | None = None, group: str | None = None) -> ProviderAction:
    return ProviderAction(name=name, callback=callback, tooltip=tooltip or tips.ACTIONS.get(name), group=group)


EVENT_CAPABILITIES = frozenset({Capability.EDIT_EVENTS, Capability.CREATE_EVENTS, Capability.DELETE_EVENTS})
CAPABILITIES = frozenset({
    Capability.EDIT_EVENTS,
    Capability.CREATE_EVENTS,
    Capability.DELETE_EVENTS,
    Capability.CREATE_CATALOGS,
    Capability.DELETE_CATALOGS,
    Capability.RENAME_CATALOG,
    Capability.MOVE_CATALOG,
    Capability.SEARCHES,
})
# The server ignores a viewer's writes, so the UI must not offer them.
WRITE_ROLES = frozenset({"owner", "editor"})


class CocatRsEvent(CatalogEvent):
    """Never given a Qt parent: a parent would keep every event ever shown alive until exit, and
    public catalogues hold tens of thousands. Python's references decide when it goes."""

    def apply_remote_range(self, start, stop) -> None:
        start, stop = make_utc_datetime(start), make_utc_datetime(stop)
        if (start, stop) == (self._start, self._stop):
            return
        self._start, self._stop = start, stop
        self.range_changed.emit()


def _stored_event(room, uuid: str):
    """The room's event, or None when it is gone, trashed, or a smart catalogue's derived interval."""
    try:
        event = room.event(uuid)
    except cocat_rs.NotFound:
        event = None
    if event is None or event.status == "deleted":
        log.debug("Event %s is not in the room; edit dropped", uuid)
        return None
    return event


TYPED_KEYS = ("tags", "rating")  # what a bulk read tells about an event besides its attributes


def _store_meta(stored, key: str, value: Any):
    """Writes one meta value where a read finds it again: tags and rating in cocat-rs's own fields,
    the rest as attributes. Returns the value as a read shows it, _SENTINEL when a read shows none."""
    typed = typed_fields(key, value)
    if not typed:
        stored.set_attributes(**{key: value})
        return value
    for field, field_value in typed.items():
        setattr(stored, field, field_value)
    if key in stored.attributes:  # written as a plain attribute by older SciQLop: it would show again
        stored.remove_attributes([key])
    return typed_meta(typed.get("tags"), typed.get("confidence")).get(key, _SENTINEL)


def _with_typed_fields(event: CocatRsEvent, meta: dict) -> CocatRsEvent:
    """An event already shown takes the tags and rating a new read gives (they change elsewhere too:
    a public event, another window)."""
    shown = event.meta
    for key in TYPED_KEYS:
        if shown.get(key) == meta.get(key):
            continue
        if key in meta:
            event.set_meta(key, meta[key])
        else:
            event.remove_meta(key)
    return event


def _default_project(infos) -> str | None:
    """The user's own project, else the first one."""
    return next((i.id for i in infos if i.personal), infos[0].id if infos else None)


class CocatRsProvider(Placing, Rereading, Searching, ShowingAllEvents, Following, Linking, Submitting, ImportingTscat, CatalogProvider):
    NAME = PROVIDER_NAME
    DESCRIPTION = "Your catalogues, and the projects shared with you, through cocat-rs."

    def __init__(self, author: str = "SciQLop", session=None, cache_dir: Path | None = None,
                 local_dir: Path | None = None, read_tscat=None, parent: QObject | None = None):
        self._author = author
        self._session = session
        self._cache_dir = cache_dir
        self._room_infos: dict = {}            # room id -> cocat_rs.ProjectInfo, the default first
        self._connected = False
        self._rooms: dict = {}                 # room id -> cocat_rs.Project
        self._catalogs: dict[str, Catalog] = {}
        # simplify: an event leaves this map only when deleted or when its room is left, even if
        # it no longer sits in any loaded catalogue; fine until rooms hold huge orphan sets.
        self._wrappers: dict[str, dict[str, CocatRsEvent]] = {}  # room id -> uuid -> event
        self._default_room_id: str | None = None
        self._remote_depth = 0
        self._pending_ranges: dict[tuple[str, str], CocatRsEvent] = {}  # (room id, uuid) -> event
        self._listen_handles: dict = {}        # room id -> cocat_rs ListenHandle
        self._status: dict[str, str] = {}      # room id -> cocat_rs room status
        self._roles: dict[str, str] = {}       # room id -> the user's role in it
        self._windows: dict = {}               # (kind, room id or uuid) -> its open window, kept alive here
        self._sign_in = None                   # the browser sign-in under way, cancelled on close
        self._starting = None                  # the start under way, cancelled on close
        self._stall_timers: dict[str, QTimer] = {}
        self._smart: set[str] = set()          # uuids of catalogues that have a rule
        self._public_smart: set[str] = set()   # those whose rule searches the public catalogues
        self._read_notes: dict[str, str] = {}  # uuid -> why its members may be incomplete (signed out)
        self._unreadable: dict[str, str] = {}  # uuid -> why its rule cannot be used (invalid, or a newer form)
        self._smart_dirty: set[str] = set()    # room ids whose smart catalogues need a re-read
        self._remembered = Remembered(cache_dir)
        self._local_dir = local_dir            # projects kept on this computer only
        self._local = Remembered(local_dir) if local_dir is not None else None
        self._local_ids: set[str] = set()      # the shown projects that are kept on this computer
        self._held: dict = {}                  # room id -> the lock of a project kept on this computer, open here
        self._elsewhere: set[str] = set()      # the projects only another SciQLop window could open when last tried
        self._cache_lock = None                # taken, or found held, when the first server project is opened
        self._own_cache: Path | None = None    # a later window's folder for the server projects' caches
        self._unsent: set[str] = set()         # projects closed from it before the server had their changes
        self._read_tscat = read_tscat          # tscat_import.read_tscat_database; None: tscat is left alone
        self._public_ids: set[str] = set()     # the joined projects that are followed public catalogues
        self._public_views: dict[str, dict] = {}  # a listed public catalogue's uuid in SciQLop -> its row
        self._public_loading: set[str] = set()  # uuids of the listed ones being opened
        self._links: dict[str, dict] = {}      # a link's uuid in SciQLop -> the link, as cocat-rs lists it
        self._offline = False                  # the projects shown are the last session's
        self._versions_provider = None         # past versions, made on the first View
        super().__init__(name=self.NAME, parent=parent, description=self.DESCRIPTION)
        self._range_timer = QTimer(self)
        self._range_timer.setSingleShot(True)
        self._range_timer.setInterval(RANGE_DEBOUNCE_MS)
        self._range_timer.timeout.connect(self.flush_ranges)
        self._smart_timer = QTimer(self)
        self._smart_timer.setSingleShot(True)
        self._smart_timer.setInterval(SMART_REFRESH_MS)
        self._smart_timer.timeout.connect(self.refresh_smart_catalogs)
        self._public_timer = QTimer(self)
        self._public_timer.setInterval(PUBLIC_REFRESH_MS)
        self._public_timer.timeout.connect(self._reread_public_smart)
        self._start_rereading()

    # ---- rooms ----

    def attach_room(self, room_id: str, room, role: str = "editor") -> None:
        self._rooms[room_id] = room
        self._roles[room_id] = role
        self._wrappers.setdefault(room_id, {})
        if room_id in self._public_ids:  # shown under Public catalogues, through its listed view
            return
        for cocat_cat in room.catalogues():
            self._wrap_catalogue(room_id, cocat_cat)
        self._show_all_events(room_id)
        if room_id not in self._room_infos:  # a listed project's folder is shown from the listing
            self.folder_added.emit([room_id])
        self.capabilities_changed.emit(None)  # the tree placed it from the listing, before it was writable

    def listen_room(self, room_id: str) -> None:
        """Must run on the qasync loop: cocat-rs calls the listener back on the loop running now."""
        from .remote import RoomListener
        self._listen_handles[room_id] = self._rooms[room_id].listen(RoomListener(self, room_id))

    def detach_room(self, room_id: str):
        self.flush_ranges()
        self._roles.pop(room_id, None)
        handle = self._listen_handles.pop(room_id, None)
        if handle is not None:
            handle.close()
        timer = self._stall_timers.pop(room_id, None)
        if timer is not None:
            timer.stop()
        for catalog in self._catalogs_of(room_id):
            self._forget_catalog(catalog)
        self._wrappers.pop(room_id, None)
        self._status.pop(room_id, None)
        self._smart_dirty.discard(room_id)
        room = self._rooms.pop(room_id, None)
        self.capabilities_changed.emit(None)  # its creation rows go, and the provider's with the last writable one
        return room

    def _watch_for_stall(self, room_id: str) -> None:
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(SYNC_STALL_MS)
        timer.timeout.connect(lambda: self._report_stall(room_id))
        self._stall_timers[room_id] = timer
        timer.start()

    def _report_stall(self, room_id: str) -> None:
        self._stall_timers.pop(room_id, None)
        if room_id not in self._rooms or self.room_status(room_id) == "synced":
            return
        info = self._room_infos.get(room_id)
        self.error_occurred.emit(
            f"Project '{info.name if info else room_id}' is still not synced after {SYNC_STALL_MS // 1000} s "
            f"(status: {self.room_status(room_id)}). Check the server URL and your network.")

    def room_status(self, room_id: str) -> str:
        return self._status.get(room_id, "offline")

    def room_status_changed(self, room_id: str, value: str) -> None:
        previous, self._status[room_id] = self._status.get(room_id), value
        self.status_changed.emit()
        if value == previous:
            return
        if value == "synced":
            self.room_role_changed(room_id, self._rooms[room_id].role)
            self.catalogues_may_have_changed(room_id)
        elif value == "no_access":
            self._lose_project(room_id)
        elif value == "unauthorized":
            asyncio.ensure_future(self._sign_in_ended())

    def room_role_changed(self, room_id: str, role: str | None) -> None:
        """An owner changed the person's role: cocat-rs reconnected and learned it. SciQLop reads
        capabilities only when a catalogue appears, so the project's catalogues are wrapped again."""
        if room_id not in self._rooms or role is None or role == self._roles.get(room_id):
            return
        self._roles[room_id] = role
        info = self._room_infos.get(room_id)
        if info is not None:
            self._room_infos[room_id] = cocat_rs.ProjectInfo(
                info.id, info.name, role, personal=info.personal,
                editors_can_share=info.editors_can_share)
        self.capabilities_changed.emit(None)
        self.sections_changed.emit()  # a viewer made editor gets creation rows, and the reverse
        self.status_changed.emit()

    def _tell(self, text: str) -> None:
        """Information, not a failure."""
        self.notice.emit(text)

    def _rewrap_room(self, room_id: str) -> None:
        """Shows the room afresh: for changes made here in bulk (an import), which cocat-rs does not
        report back, and for a new role, which SciQLop reads only when a catalogue appears."""
        if room_id in self._public_ids:
            return self.public_may_have_changed(room_id)
        for catalog in self._catalogs_of(room_id):
            self._forget_catalog(catalog)
        self._wrappers[room_id] = {}
        for cocat_cat in self._rooms[room_id].catalogues():
            self._wrap_catalogue(room_id, cocat_cat)
        if room_id == self._links_home():
            self.show_links()

    def _lose_project(self, room_id: str) -> None:
        name = self.folder_display_name([room_id])
        if room_id in self._public_ids:
            self.lose_public(room_id)
        else:
            self.leave_room(room_id)
            self.show_links()
            self._room_infos.pop(room_id, None)
            self.folder_removed.emit([room_id])
        self._tell(f"You no longer have access to the CoCat project {name}")

    async def _sign_in_ended(self) -> None:
        self.error_occurred.emit(f"CoCat ended the sign-in to {self._session.url}: "
                                 f"right-click {PROVIDER_NAME} > Sign in…")
        await self.sign_out()

    # ---- server connection ----

    async def sign_in(self) -> bool:
        """Signs in through the browser, then connects."""
        try:
            self._sign_in = await self._session.start_sign_in()
        except Exception as error:
            self.error_occurred.emit(f"Cannot sign in to CoCat at {self._session.url}: {describe(error)}")
            return False
        box = show_sign_in_box(self._sign_in)
        open_url(self._sign_in.url)
        try:
            await asyncio.to_thread(self._sign_in.wait)
        except cocat_rs.NotSignedIn as error:
            if box.isVisible():  # hidden: the person pressed Cancel, nothing to report
                self.error_occurred.emit(describe(error))
            return False
        finally:
            self._sign_in = None
            box.done(0)
        return await self.connect()

    async def sign_out(self) -> None:
        self.disconnect()
        await self._session.sign_out()
        await self.show_signed_out()

    async def _signed_in_email(self) -> str | None:
        try:
            return await self._session.email()
        except Exception as error:
            log.warning("Cannot read the CoCat account's email: %s", error)
            return None

    def start(self) -> None:
        """At SciQLop start: connect when a sign-in from an earlier session is still kept."""
        self._starting = asyncio.ensure_future(self._start())

    async def _stop_starting(self) -> None:
        """A start still under way (the tscat catalogues being read) ends with SciQLop."""
        if self._starting is not None and not self._starting.done():
            self._starting.cancel()
            await asyncio.wait([self._starting])
        self._starting = None

    async def _start(self) -> None:
        if not (self._session is not None and self._session.signed_in and await self.connect()):
            await self.show_signed_out()
        await self.import_tscat_once()

    def _account_copy(self):
        """The last account's own project, whose cache stays usable signed out."""
        return next((i for i in self._remembered.projects if i.personal), None)

    def _local_infos(self) -> list:
        """The projects kept on this computer; the first one is made while no account was ever used."""
        if self._local is None:
            return []
        if self._account_copy() is not None:
            return self._local.projects
        return self._local.projects_with_a_first(
            lambda: cocat_rs.ProjectInfo(str(uuid.uuid4()), MY_CATALOGUES, "owner"))

    async def show_signed_out(self) -> None:
        """My catalogues without a server: the last account's copy, and what is kept on this computer."""
        self._author = self._remembered.author or self._author
        copy, local = self._account_copy(), self._local_infos()
        self._local_ids = {i.id for i in local}
        shown = ([copy] if copy else []) + local
        await self._show_projects(shown, shown[0].id if shown else None)

    async def _show_projects(self, infos, default_id) -> None:
        self._default_room_id = default_id
        infos = sorted(infos, key=lambda i: i.id != default_id)
        self._room_infos = {info.id: info for info in infos}
        for room_id in self._room_infos:
            if room_id not in self._public_ids:
                self.folder_added.emit([room_id])
        left = self._remembered.left
        for room_id in self._room_infos:
            if room_id not in left:
                await self.join_room(room_id)
        self.show_links()
        self.status_changed.emit()

    async def _list_projects(self):
        """The server's list, else the last session's while the server cannot be reached."""
        infos = await self._session.projects()
        self._offline = infos is None and self._session.signed_in and bool(self._remembered.projects)
        if self._offline:
            self._tell(
                f"CoCat at {self._session.url} cannot be reached: showing your projects from the last "
                f"session. Your changes are sent once it is back.")
            return self._remembered.projects
        if infos is not None:
            self._remembered.projects = infos
        return infos

    async def _learn_author(self) -> None:
        email = None if self._offline else await self._signed_in_email()
        if email is not None:
            self._remembered.author = email
        self._author = email or self._remembered.author or self._author

    async def connect(self) -> bool:
        if not self._session.signed_in:
            self.error_occurred.emit(f"Not signed in to CoCat at {self._session.url}: "
                                     f"right-click {PROVIDER_NAME} > Sign in…")
            return False
        infos = await self._list_projects()
        if infos is None:
            if self._session.signed_in:
                self.error_occurred.emit(f"Cannot list CoCat projects at {self._session.url}")
            return False
        self._clear_shown()  # the signed-out view, if shown
        await self._learn_author()
        local = self._local_with_catalogues()
        self._local_ids = {i.id for i in local}
        followed = [as_info(row) for row in self._remembered.followed]
        self._public_ids = {info.id for info in followed}
        self._connected = True
        await self._show_projects([*infos, *local, *followed], _default_project(infos))
        self.show_public(await self._public_rows())
        await self._offer_move()
        return True

    def _local_with_catalogues(self) -> list:
        """An empty project kept on this computer has nothing to move: forgotten at sign-in."""
        return [info for info in self._local_infos() if not self._dropped_as_empty(info.id)]

    def _dropped_as_empty(self, room_id: str) -> bool:
        """Never one that another SciQLop window has open."""
        if not self._hold(room_id):
            return False
        try:
            room = open_room(str(self._local_dir), room_id)
            try:
                empty = not room.catalogues()
            finally:
                room.close()
            if empty:
                self._delete_local(room_id)
            return empty
        finally:
            self._let_go(room_id)

    def _server_cache(self) -> Path | None:
        """Where this window keeps the caches of the server's projects. Two windows writing one
        cache file cut each other's records, so only the first window has the shared folder."""
        if self._cache_dir is None:
            return None
        if self._cache_lock is None:
            self._cache_lock = lock_on(Path(self._cache_dir) / CACHE_LOCK)
            if not self._cache_lock.tryLock(0):
                self._own_cache = Path(self._cache_dir) / OTHER_WINDOWS / str(uuid.uuid4())
        return self._own_cache or Path(self._cache_dir)

    def _give_cache_back(self) -> None:
        if self._own_cache is not None and self._unsent:
            log.warning("Changes to %s did not reach the CoCat server: they are kept in %s",
                        ", ".join(sorted(self._unsent)), self._own_cache)
        elif self._own_cache is not None:
            shutil.rmtree(self._own_cache, ignore_errors=True)
        if self._cache_lock is not None:
            self._cache_lock.unlock()
        self._cache_lock = self._own_cache = None

    def _check_sent(self, room_id: str, room) -> None:
        """A later window's cache goes when it closes: what the server does not have yet must stay."""
        try:
            room.save(LEAVE_SAVE_S)
        except Exception as error:
            self._unsent.add(room_id)
            log.warning("Project %s closed before the CoCat server had its changes: %s", room_id, describe(error))
        else:
            self._unsent.discard(room_id)

    def _may_open(self, room_id: str) -> bool:
        """False for a project that only another SciQLop window can have open now."""
        if room_id in self._local_ids:
            return self._hold(room_id)
        self._server_cache()
        if self._own_cache is not None and not self._online():  # no copy of its own without the server
            self._elsewhere.add(room_id)
            return False
        self._elsewhere.discard(room_id)
        return True

    def _hold(self, room_id: str) -> bool:
        """Takes the lock of a project kept on this computer; False while another window holds it."""
        lock = lock_on(Path(self._local_dir) / f"{room_id}{LOCK_SUFFIX}")
        if not lock.tryLock(0):
            self._elsewhere.add(room_id)
            return False
        self._elsewhere.discard(room_id)
        self._held[room_id] = lock
        return True

    def _let_go(self, room_id: str) -> None:
        lock = self._held.pop(room_id, None)
        if lock is not None:
            lock.unlock()

    def _account_project(self) -> str | None:
        """The account's own project, when joined and writable: where local catalogues move to."""
        info = self._room_infos.get(self._default_room_id)
        if info is None or not info.personal or not self._can_write(info.id) or not self._online():
            return None
        return info.id

    async def _offer_move(self) -> None:
        target = self._account_project()
        local = [r for r in self._local_ids if r in self._rooms]
        if target is None or not local or self._local.move_offered:
            return
        self._local.note_move_offered()
        if questions.ask_move([self._room_infos[r].name for r in local], self._room_infos[target].name):
            for room_id in local:
                self.move_to_account(room_id)

    def move_to_account(self, room_id: str) -> bool:
        """Brings a local project's catalogues into the account's own project, uuids kept, then
        deletes it from this computer."""
        target = self._account_project()
        self.flush_ranges()
        name = self.folder_display_name([room_id])
        try:
            moved = self._rooms[target].merge(self._rooms[room_id])
        except Exception as error:
            self.error_occurred.emit(f"Cannot move {self.folder_display_name([room_id])} into your "
                                     f"account: {describe(error)}")
            return False
        self.leave_room(room_id)
        self._room_infos.pop(room_id, None)
        self._local_ids.discard(room_id)
        self._delete_local(room_id)
        self.folder_removed.emit([room_id])
        self._rewrap_room(target)
        self.status_changed.emit()
        self._tell(f"{name}: {moved['catalogues']} catalogue(s) and {moved['events']} event(s) moved into "
                   f"{self._room_infos[target].name}")
        return True

    def _delete_local(self, room_id: str) -> None:
        self._local.remove_project(room_id)
        for path in Path(self._local_dir).glob(f"{room_id}.*"):
            if path.suffix != LOCK_SUFFIX:  # held here, and gone when let go
                path.unlink()

    async def reconnect(self) -> bool:
        self.disconnect()
        return await self.connect()

    def _choose_to_leave(self, room_id: str) -> None:
        self._remembered.set_left(room_id, True)
        self.leave_room(room_id)
        self.show_links()
        self.status_changed.emit()

    async def _choose_to_join(self, room_id: str) -> None:
        self._remembered.set_left(room_id, False)
        await self.join_room(room_id)
        if room_id in self._elsewhere:
            self._tell(f"{self._room_infos[room_id].name} is open in another SciQLop window, and this "
                       f"window is not connected to the CoCat server: it cannot be shown here for now.")
        self.show_links()
        self.status_changed.emit()

    def disconnect(self) -> None:
        self._clear_shown()
        self._connected = False
        self._offline = False
        self.status_changed.emit()

    def _clear_shown(self) -> None:
        for room_id in list(self._rooms):
            self.leave_room(room_id)
        for room_id in self._room_infos:
            if room_id not in self._public_ids:
                self.folder_removed.emit([room_id])
        self._hide_public()
        self._room_infos = {}
        self._local_ids = set()
        self._elsewhere = set()
        self._public_ids = set()
        self._default_room_id = None

    async def join_room(self, room_id: str) -> None:
        if room_id in self._rooms or not self._may_open(room_id):
            return
        try:
            room = open_room(str(self._local_dir if room_id in self._local_ids else self._server_cache()), room_id)
        except Exception as error:
            self._let_go(room_id)
            self.error_occurred.emit(f"Cannot open project '{room_id}': {error}")
            return
        try:
            self._give_server(room)
            self._set_identity(room, self._room_infos[room_id])
            self.attach_room(room_id, room, self._room_infos[room_id].role)
            self.listen_room(room_id)
            self._go_online(room_id, room)
        except Exception as error:
            self.detach_room(room_id)
            room.close()
            self._let_go(room_id)
            self.error_occurred.emit(f"Cannot join project '{room_id}': {error}")

    def _give_server(self, room) -> None:
        """Before the first read: a smart catalogue may search the public catalogues on the server,
        even in a project kept on this computer, which never syncs."""
        if self._session is not None and self._session.signed_in:
            room.use_server(self._session.url, self._session.cookie)

    def _set_identity(self, room, info) -> None:
        """Names the project and the person in what cocat-rs writes there (links, comments)."""
        try:
            room.set_identity(info.name, self._author, personal=info.personal)
        except TypeError:  # cocat-rs 0.8.0: no `personal` yet
            room.set_identity(info.name, self._author)

    def _go_online(self, room_id: str, room) -> None:
        if room_id in self._local_ids or not self._session.signed_in:
            return
        room.connect(self._session.url, self._session.cookie)
        if not self._offline:  # offline, the message about the last session already says why
            self._watch_for_stall(room_id)

    def leave_room(self, room_id: str) -> None:
        only_copy = self._own_cache is not None and room_id not in self._local_ids and self._can_write(room_id)
        room = self.detach_room(room_id)
        if room is not None:
            if only_copy:
                self._check_sent(room_id, room)
            room.close()
        self._let_go(room_id)

    def release(self, room_id: str) -> None:
        """Closes a project kept on this computer in this window: another window can open it."""
        self.leave_room(room_id)
        self.show_links()
        self.status_changed.emit()

    async def open_here(self, room_id: str) -> None:
        await self.join_room(room_id)
        if room_id in self._elsewhere:
            self.error_occurred.emit(
                f"{self._room_infos[room_id].name} is still open in another SciQLop window: "
                f"right-click it there > Release, or close that window, then try again.")
        self.show_links()
        self.status_changed.emit()

    async def close(self) -> None:
        await self._stop_starting()
        if self._sign_in is not None:
            self._sign_in.cancel()
        if self._versions_provider is not None:
            await self._versions_provider.close()
        self._stop_rereading()
        for room_id in list(self._rooms):
            self.leave_room(room_id)
        self._give_cache_back()

    # ---- tree decorations and actions ----

    def _app_url(self) -> str:
        return f"{self._session.url.rstrip('/')}/ui/"

    def _project_url(self, room_id: str, share: bool = False) -> str:
        return cocat_rs.raw.project_url(self._session.url, room_id, share=share)

    async def create_project(self, name: str):
        """A new project on the server, owned by the user, listed and joined."""
        try:
            info = await self._session.call(cocat_rs.raw.create_project, name)
        except Exception as error:
            self.error_occurred.emit(f"Cannot create project '{name}': {describe(error)}")
            return None
        await self.add_project(info)
        return info

    async def add_project(self, info) -> None:
        """A project the person just got (created, or copied from a version): listed and joined."""
        self._room_infos[info.id] = info
        self._remembered.add_project(info)
        self.folder_added.emit([info.id])
        await self.join_room(info.id)
        self.status_changed.emit()

    async def save_version(self, room_id: str, name: str | None) -> bool:
        """Sends what is still local, then has the server save the project as a version."""
        self.flush_ranges()
        try:
            await asyncio.to_thread(self._rooms[room_id].save, SAVE_TIMEOUT_S)
            await self._session.call(cocat_rs.raw.commit, room_id, name=name or None)
        except Exception as error:
            self.error_occurred.emit(f"Cannot save a version of {self.folder_display_name([room_id])}: "
                                     f"{describe(error)}")
            return False
        self._refresh_histories()
        return True

    def _refresh_histories(self) -> None:
        """An open History window shows the version just saved."""
        for (kind, _), window in list(self._windows.items()):
            if kind == "history" and window.isVisible():
                window.refresh()

    async def copy_public_catalogue(self, row: dict) -> None:
        """Asks into which project: a new one, or one the person can edit."""
        targets = [room_id for room_id in self._rooms if self._can_write(room_id)]
        target = questions.ask_choice(
            f"Copy {row['name']}", "Copy into:",
            ["A new project", *(self._room_infos[r].name for r in targets)])
        if target is not None:
            await self._copy_public(row, targets[target - 1] if target else None)

    async def _copy_public(self, row: dict, project_id: str | None) -> None:
        """Into `project_id`, or a new project when None."""
        try:
            copied = await self._session.call(cocat_rs.raw.copy_public_catalogue, row["id"], project_id)
        except Exception as error:
            self.error_occurred.emit(f"Cannot copy '{row['name']}': {describe(error)}")
            return
        if project_id is None:
            await self.add_project(cocat_rs.ProjectInfo(copied["project_id"], copied["name"], "owner"))

    def _ask_and_save_version(self, room_id: str, catalog: Catalog | None = None) -> None:
        """From a catalogue, the version is still the whole project's: its name says which catalogue it
        was saved for, and the catalogue's History lists it when the version changed it."""
        label, default = "Version name (optional):", ""
        if catalog is not None:
            label = (f"A version saves the whole project. It shows in the History of “{catalog.name}” "
                     f"when it changed this catalogue.\n\n{label}")
            default = catalog.name
        name = ask_text(QApplication.activeWindow(), "Save version", label, text=default)
        if name is not None:
            asyncio.ensure_future(self.save_version(room_id, name))

    def _ask_and_create_project(self) -> None:
        name = ask_project_name()
        if name:
            asyncio.ensure_future(self.create_project(name))

    def _show_window(self, key: tuple, make) -> None:
        """One window per thing: asking again brings the open one forward."""
        window = self._windows.get(key)
        if window is not None and window.isVisible():
            window.raise_()
            window.activateWindow()
            return
        self._windows[key] = make()

    def _show_sharing(self, room_id: str) -> None:
        self._show_window(("sharing", room_id), lambda: show_sharing_dialog(
            self._session, room_id, self._room_infos[room_id].name, self._project_url(room_id, share=True),
            open_url, QApplication.activeWindow()))

    def _show_history(self, room_id: str, catalog: Catalog | None = None) -> None:
        title = catalog.name if catalog is not None else self._room_infos[room_id].name
        on_copied = lambda project_id, name: asyncio.ensure_future(
            self.add_project(cocat_rs.ProjectInfo(project_id, name, "owner")))
        self._show_window(("history", catalog.uuid if catalog else room_id), lambda: show_history_dialog(
            self._session, room_id, title, catalog.uuid if catalog else None, on_copied,
            QApplication.activeWindow()))

    async def view_version(self, room_id: str, version) -> None:
        """The project as it was, read-only, under Past versions: one download, nothing synced.
        Not in the UI yet: kept for a future diff view."""
        from .versions import VersionsProvider
        try:
            past = await self._session.call(cocat_rs.Project.at, room_id, version.id)
        except Exception as error:
            self.error_occurred.emit(f"Cannot fetch that version: {describe(error)}")
            return
        if self._versions_provider is None:
            self._versions_provider = VersionsProvider(parent=self)
        name = self._room_infos[room_id].name if room_id in self._room_infos else room_id
        self._versions_provider.show(f"{room_id}@{version.id}", f"{name} as of {when_text(version.when)}", past)

    def _online(self) -> bool:
        return self._connected and not self._offline

    def actions(self, catalog: Catalog | None = None) -> list[ProviderAction]:
        if catalog is not None:
            return self._catalog_actions(catalog)
        sign_out = action("Sign out", lambda _: asyncio.ensure_future(self.sign_out()))
        reconnect = action("Reconnect", lambda _: asyncio.ensure_future(self.reconnect()))
        if self._connected:
            actions = [reconnect] if self._offline else []
            actions += [sign_out,
                        action("New project…", lambda _: self._ask_and_create_project())]
        elif self._session is not None and self._session.signed_in:
            actions = [action("Connect", lambda _: asyncio.ensure_future(self.connect())),
                       sign_out]
        else:
            actions = [action("Sign in…", lambda _: asyncio.ensure_future(self.sign_in()))]
        if self._session is not None:
            actions.append(action("Open CoCat in browser",
                                          lambda _: open_url(self._app_url())))
        return actions

    def folder_actions(self, path: list[str]) -> list[ProviderAction]:
        if len(path) != 1:
            return []
        presets = self._preset_actions(path[0])
        return [*presets, *self._project_actions(path)] if path[0] in self._room_infos else presets

    def _project_actions(self, path: list[str]) -> list[ProviderAction]:
        if path[0] in self._local_ids:
            return self._local_actions(path[0])
        if path[0] in self._rooms:
            membership = action("Leave", lambda p: self._choose_to_leave(p[0]))
        else:
            membership = action("Join",
                                        lambda p: asyncio.ensure_future(self._choose_to_join(p[0])))
        browse = action("Open in browser", lambda p: open_url(self._project_url(p[0])))
        if not self._online():
            return [membership, *self._import_actions(path[0]), browse]
        server = [action("History…", lambda p: self._show_history(p[0]))]
        if not self._room_infos[path[0]].personal:  # the server refuses to share it
            server.append(action("Sharing…", lambda p: self._show_sharing(p[0])))
        if path[0] in self._rooms and self._can_write(path[0]):
            server.insert(0, action("Save version of the whole project…", lambda p: self._ask_and_save_version(p[0])))
        return [membership, *server, *self._import_actions(path[0]), browse]

    def _local_actions(self, room_id: str) -> list[ProviderAction]:
        if room_id not in self._rooms:
            return [action("Open here", lambda p: asyncio.ensure_future(self.open_here(p[0])))]
        return [*self._move_actions(room_id), *self._import_actions(room_id),
                action("Release", lambda p: self.release(p[0]))]

    def _move_actions(self, room_id: str) -> list[ProviderAction]:
        target = self._account_project()
        if target is None or room_id not in self._rooms:
            return []
        name = self._room_infos[target].name
        return [action(f"Move into {name}", lambda p: self.move_to_account(p[0]),
                       f"Move these catalogues into {name}, saved with your account; the copy here goes")]

    def _catalog_actions(self, catalog: Catalog) -> list[ProviderAction]:
        if self._is_all_events(catalog):
            return []
        if catalog.uuid in self._public_views:
            return self._public_actions(catalog)
        if not catalog.path or catalog.path[0] not in self._rooms:
            return []
        export = action("Export…", self._ask_and_export)
        if catalog.uuid in self._links:
            return [action("Unlink", self.unlink), export] if self._can_write(catalog.path[0]) else [export]
        searches = self._search_catalog_actions(catalog)
        link = [action("Link into My catalogues", self.link_into_personal)] if self._can_link(catalog) else []
        if not self._online() or catalog.path[0] in self._local_ids:
            return [*searches, export, *link]
        submit = [action("Submit as a public catalogue…", lambda c: self.offer_submission(c))] \
            if self._cannot_submit(catalog) is None else []
        save = [action("Save version…", lambda c: self._ask_and_save_version(c.path[0], c))] \
            if self._can_write(catalog.path[0]) else []
        return [*searches, *save, action("History…", lambda c: self._show_history(c.path[0], c)), export, *link,
                *submit]

    def _public_actions(self, catalog: Catalog) -> list[ProviderAction]:
        row = self._public_views[catalog.uuid]
        copy = action("Copy into a project…", lambda c: asyncio.ensure_future(self.copy_public_catalogue(row)))
        online = [copy] if self._online() else []
        if row["id"] not in self._rooms:
            return online
        unfollow = action("Unfollow", lambda c: self.unfollow(row["id"]))
        history = [action("History…", lambda c: self._show_history(row["id"]))] if self._online() else []
        return [unfollow, *history, action("Export…", self._ask_and_export), *online]

    def _import_actions(self, room_id: str) -> list[ProviderAction]:
        if room_id not in self._rooms or not self._can_write(room_id):
            return []
        actions = [action("Import…", lambda p: self._ask_and_import(p[0]))]
        if tscat_available():
            actions.append(action("Import tscat catalogues",
                                  lambda p: asyncio.ensure_future(self.import_tscat_into(p[0]))))
        return actions

    # ---- import and export ----

    def import_into(self, room_id: str, read, what: str) -> bool:
        """`read(project)` adds catalogues to the room; they are then shown, as no listener reports them."""
        self.flush_ranges()
        try:
            imported = read(self._rooms[room_id])
        except Exception as error:
            imported, problem = None, describe(error)
        else:
            problem = None if imported else "no catalogue found"
        if problem is not None:
            self.error_occurred.emit(f"Cannot import {what} into {self.folder_display_name([room_id])}: "
                                     f"{problem}")
            return False
        self._rewrap_room(room_id)
        return True

    def _ask_and_import(self, room_id: str) -> None:
        chosen = questions.ask_import_path()
        if chosen is not None:
            fmt, path = chosen
            self.import_into(room_id, lambda project: import_file(fmt, project, path), path.name)

    def _ask_and_export(self, catalog: Catalog) -> None:
        chosen = questions.ask_export_path(catalog.name)
        cocat_cat = self._cocat_catalogue(catalog)
        if chosen is None or cocat_cat is None:
            return
        fmt, path = chosen
        self.flush_ranges()
        try:
            try:
                export_catalogue(fmt, self._room_of(catalog), cocat_cat, path)
            except NeedsValueRange:
                value_range = questions.ask_value_range(cocat_cat.shape_axis)
                if value_range is not None:
                    export_catalogue(fmt, self._room_of(catalog), cocat_cat, path, value_range)
        except Exception as error:
            self.error_occurred.emit(f"Cannot export '{catalog.name}' to {path.name}: {describe(error)}")

    def node_tooltip(self, node_type, path=None, catalog=None) -> str | None:
        if node_type == NodeType.PROVIDER:
            signed_in = self._session is not None and self._session.signed_in
            return tips.provider_tip(self.DESCRIPTION, self._author if signed_in else None, self._offline,
                                     server=getattr(self._session, "url", "") or "",
                                     projects=len(set(self._room_infos) - self._public_ids))
        if node_type == NodeType.CATALOG and catalog is not None and catalog.uuid in self._links:
            return self.link_tip(catalog)
        if node_type == NodeType.CATALOG and catalog is not None and catalog.uuid in self._public_views:
            room_id = self._public_room_id(catalog)
            return tips.public_tip(self._public_views[catalog.uuid], events=self._events.get(catalog.uuid, []),
                                   state=self.room_status(room_id) if room_id in self._rooms else None)
        if node_type == NodeType.FOLDER and path == [PUBLIC]:
            return tips.public_folder_tip(len(self._public_views))
        if node_type == NodeType.CATALOG and catalog is not None:
            if catalog.uuid in self._unreadable:
                return tips.unreadable_tip(catalog.name, self._unreadable[catalog.uuid])
            cocat_cat = self._cocat_catalogue(catalog)
            if cocat_cat is None:
                return None
            tip = tips.catalogue_tip(cocat_cat, self._events.get(catalog.uuid, []))
            note = self._read_notes.get(catalog.uuid)
            return f"{tip}<br><i>{escape(note)}</i>" if note else tip
        if node_type == NodeType.FOLDER and path and len(path) == 1 and path[0] in self._room_infos:
            return self._project_tip(path[0])
        return None

    def _project_tip(self, room_id: str) -> str:
        joined = room_id in self._rooms
        if room_id in self._local_ids and not joined:
            return tips.closed_local_tip(self._room_infos[room_id].name, room_id in self._elsewhere)
        catalogs = [c for c in self._catalogs_of(room_id) if not self._is_all_events(c)]
        own = [c for c in catalogs if c.uuid not in self._links]
        tip = tips.project_tip(self._room_infos[room_id], state=self.room_status(room_id) if joined else None,
                               local=room_id in self._local_ids, default=room_id == self._default_room_id,
                               catalogues=len(catalogs), smart=sum(c.uuid in self._smart for c in own),
                               linked=len(catalogs) - len(own),
                               events=len({e.uuid for c in own for e in self._events.get(c.uuid, [])}))
        return tip + self._account_tip() if self._is_my_catalogues(room_id) else tip

    def _account_tip(self) -> str:
        """My catalogues is where the account shows: there is no provider node any more."""
        signed_in = self._session is not None and self._session.signed_in
        return "<hr>" + tips.provider_tip(self.DESCRIPTION, self._author if signed_in else None, self._offline,
                                          server=getattr(self._session, "url", "") or "",
                                          projects=len(set(self._room_infos) - self._public_ids))

    def node_icon(self, node_type, path=None):
        if node_type == NodeType.FOLDER:
            return self._project_icon(path)
        if node_type != NodeType.PROVIDER:
            return None
        from SciQLop.components.theming import get_icon
        synced = any(status == "synced" for status in self._status.values())
        return get_icon("link" if synced else "link_off")

    def catalog_icon(self, catalog: Catalog):
        if catalog.uuid not in self._smart:
            return None
        from SciQLop.components.catalogs.backend.color_palette import catalog_swatch_icon
        return catalog_swatch_icon(catalog.uuid, shape="funnel")

    def _project_icon(self, path):
        if not path or len(path) != 1 or path[0] not in self._room_infos:
            return None
        return status_badge(self.project_state(path[0]))

    @contextmanager
    def remote_changes(self):
        self._remote_depth += 1
        try:
            yield
        finally:
            self._remote_depth -= 1

    # ---- lookups and wrapping ----

    def _catalogs_of(self, room_id: str) -> list[Catalog]:
        return [c for c in self._catalogs.values() if c.path and c.path[0] == room_id]

    def _events_room_id(self, catalog: Catalog) -> str | None:
        """The project whose events the catalogue shows: a link's original project, a listed public
        catalogue's own."""
        if catalog.uuid in self._links:
            return self._links[catalog.uuid]["project"]
        if catalog.uuid in self._public_views:
            return self._public_room_id(catalog)
        return catalog.path[0] if catalog.path else None

    def _room_of(self, catalog: Catalog):
        return self._rooms.get(self._events_room_id(catalog))

    def _cocat_catalogue(self, catalog: Catalog):
        if self._is_all_events(catalog):
            return self._all_events_source(catalog)
        if catalog.uuid in self._links:
            return self._linked_catalogue(catalog)
        if catalog.uuid in self._public_views:
            return self._public_source(catalog)
        room = self._room_of(catalog)
        if room is None:
            return None
        try:
            return room.catalogue(catalog.uuid)
        except cocat_rs.NotFound:
            return None

    def _wrapper(self, room_id: str, uuid: str, start, stop, meta: dict) -> CocatRsEvent:
        wrappers = self._wrappers.setdefault(room_id, {})
        if uuid not in wrappers:
            wrappers[uuid] = CocatRsEvent(uuid=uuid, start=start, stop=stop, meta=meta)
        return wrappers[uuid]

    def _row_event(self, room_id: str, row, shown: dict) -> CocatRsEvent:
        if not row.derived:
            return _with_typed_fields(self._wrapper(room_id, row.uuid, row.start, row.stop, row.meta), row.meta)
        meta = self._named_public(row.meta)
        kept = shown.get(row.uuid)
        if kept is not None and (kept.start, kept.stop, kept.meta) == (row.start, row.stop, meta):
            return kept
        return CocatRsEvent(uuid=row.uuid, start=row.start, stop=row.stop, meta=meta)

    def _read_now(self, catalog: Catalog, cocat_cat) -> tuple:
        """(rows, snapshot, error), read here, on the Qt thread: a link or public catalogue's first
        read, an explicit reload."""
        try:
            self._note_rule(catalog, cocat_cat)
            arrays = cocat_cat.event_arrays(attributes=True)
        except Exception as error:
            return None, None, error
        return rows_of(arrays), Snapshot.of(arrays), None

    def _members_from(self, catalog: Catalog, rows, error) -> list[CocatRsEvent]:
        """The rows of a read as events; none when this cocat-rs cannot read the catalogue: one such
        catalogue must not close the whole project, and any rule form added later reaches older
        clients the same way. Qt thread only: it uses _wrappers. Derived rows reuse the event
        already shown for them, so a re-read creates only what changed."""
        if error is not None:
            log.warning("Cannot read catalogue '%s': %s", catalog.name, error)
            if self._unreadable.get(catalog.uuid) != str(error):  # once, not at every re-read
                self.error_occurred.emit(f"Smart catalogue '{catalog.name}' shows no events: its rule is "
                                         f"invalid ({error})")
            self._unreadable[catalog.uuid] = str(error)
            return []
        self._unreadable.pop(catalog.uuid, None)
        self._note_sign_in(catalog)
        shown = {e.uuid: e for e in self._events.get(catalog.uuid, [])}
        room_id = self._events_room_id(catalog)
        return [self._row_event(room_id, r, shown) for r in rows]

    def _note_sign_in(self, catalog: Catalog) -> None:
        """Signed out, a catalogue searching the public catalogues shows only its picked events:
        its tooltip says why. (cocat-rs warns too, but recording warnings is not thread-safe here.)"""
        signed_in = self._session is not None and self._session.signed_in
        if catalog.uuid in self._public_smart and not signed_in:
            self._read_notes[catalog.uuid] = SIGN_IN_TO_SEARCH
        else:
            self._read_notes.pop(catalog.uuid, None)

    def _wrap_catalogue(self, room_id: str, cocat_cat) -> Catalog:
        attributes = cocat_cat.attributes
        catalog = Catalog(uuid=cocat_cat.uuid, name=cocat_cat.name, provider=self,
                          path=[room_id, *subpath_of(attributes)])
        self._catalogs[catalog.uuid] = catalog
        specs = schema_specs(attributes)
        if specs:
            self._attribute_specs[catalog.uuid] = specs
        self._set_events(catalog, self._first_members(catalog, cocat_cat))
        self.catalog_added.emit(catalog)
        return catalog

    def _first_members(self, catalog: Catalog, cocat_cat) -> list[CocatRsEvent]:
        """A smart catalogue is read once used, in the background (it may pick 100 000 events): only
        its rule is noted now. Any other is read here: it lists its own events."""
        try:
            self._note_rule(catalog, cocat_cat)
        except Exception as error:
            return self._members_from(catalog, None, error)
        if catalog.uuid in self._smart:
            self._unread.add(catalog.uuid)
            return []
        return self._readable_members(catalog, cocat_cat)

    def _readable_members(self, catalog: Catalog, cocat_cat) -> list[CocatRsEvent]:
        """A first read, here. (Its snapshot is not kept: the first re-read rebuilds once.)"""
        rows, _, error = self._read_now(catalog, cocat_cat)
        return self._members_from(catalog, rows, error)

    def _note_rule(self, catalog: Catalog, cocat_cat) -> None:
        if cocat_cat.rule is None:
            self._smart.discard(catalog.uuid)
        else:
            self._smart.add(catalog.uuid)
        if cocat_cat.searches_public:
            self._public_smart.add(catalog.uuid)
        else:
            self._public_smart.discard(catalog.uuid)
        self._sync_public_timer()

    def _sync_public_timer(self) -> None:
        if self._public_smart and not self._public_timer.isActive():
            self._public_timer.start()
        elif not self._public_smart:
            self._public_timer.stop()

    def reload_catalog(self, catalog: Catalog) -> None:
        """Re-read a catalogue's members now, here, on the Qt thread (links, public catalogues, an
        explicit reload); signals only when they changed. Smart catalogues are re-read with reread()."""
        cocat_cat = self._cocat_catalogue(catalog)
        if cocat_cat is None:
            return
        self._unread.discard(catalog.uuid)
        self._show_rows(catalog, *self._read_now(catalog, cocat_cat))

    def _show_rows(self, catalog: Catalog, rows, snapshot, error) -> None:
        """Shows a read made here; signals only when it differs from the read shown."""
        shown = self._snapshots.get(catalog.uuid)
        if error is None and shown is not None and snapshot.same_as(shown):
            self._unreadable.pop(catalog.uuid, None)
            self._note_sign_in(catalog)
            return
        members = self._members_from(catalog, rows, error)
        with self.remote_changes():
            self._set_events(catalog, members)
        if error is None:  # after: _set_events forgets them
            self._snapshots[catalog.uuid] = snapshot
            self._members[catalog.uuid] = {event.uuid: event for event in members}
        self._emit_events_changed(catalog)  # _set_events is silent; the browser waits for this

    def _set_events(self, catalog: Catalog, events) -> None:
        self._forget_shown_read(catalog)  # shown otherwise than by a read: the next one rebuilds
        super()._set_events(catalog, events)

    def _add_event(self, catalog: Catalog, event) -> None:
        self._forget_shown_read(catalog)
        super()._add_event(catalog, event)

    def _remove_event(self, catalog: Catalog, event) -> None:
        self._forget_shown_read(catalog)
        super()._remove_event(catalog, event)

    def _forget_shown_read(self, catalog: Catalog) -> None:
        self._snapshots.pop(catalog.uuid, None)
        self._members.pop(catalog.uuid, None)

    def catalogues_may_have_changed(self, room_id: str) -> None:
        """After a sync or a batch of remote changes: what cocat-rs does not report one by one."""
        self.links_may_have_changed(room_id)
        self.public_may_have_changed(room_id)

    def _forget_catalog(self, catalog: Catalog) -> None:
        self._smart.discard(catalog.uuid)
        self._public_smart.discard(catalog.uuid)
        self._read_notes.pop(catalog.uuid, None)
        self._forget_reads_of(catalog.uuid)
        self._sync_public_timer()
        self._unreadable.pop(catalog.uuid, None)
        self._catalogs.pop(catalog.uuid, None)
        self._attribute_specs.pop(catalog.uuid, None)
        CatalogProvider.remove_catalog(self, catalog)

    def _warn_unavailable(self, action: str, catalog: Catalog) -> None:
        log.warning("Cannot %s in catalog '%s': its project is not joined", action, catalog.name)

    # ---- CatalogProvider: catalogues ----

    def catalogs(self) -> list[Catalog]:
        return list(self._catalogs.values())

    def _can_write(self, room_id: str) -> bool:
        return self._roles.get(room_id) in WRITE_ROLES

    def _writable_rooms(self) -> list[str]:
        return [room_id for room_id in self._rooms if self._can_write(room_id)]

    def capabilities(self, catalog: Catalog | None = None) -> set[str]:
        if catalog is None:
            return set(CAPABILITIES) if self._writable_rooms() else set()
        if catalog.uuid in self._links or self._is_all_events(catalog):  # simplify: links are read-only; editing
            return set()                                                  # through one writes to the original
        if not catalog.path or not self._can_write(catalog.path[0]):
            return set()
        if catalog.uuid in self._smart or catalog.uuid in self._unreadable:
            return set(CAPABILITIES - EVENT_CAPABILITIES)
        return set(CAPABILITIES)

    def _room_for_new_catalog(self, path: list[str] | None) -> str:
        if path:
            if path[0] == PUBLIC:
                raise PermissionError(f"{PUBLIC_FOLDER} are read-only: put the catalogue in one of your "
                                      f"projects, then drag it onto {PUBLIC_FOLDER} to submit it")
            if path[0] not in self._rooms:
                raise KeyError(f"Project '{path[0]}' is not joined")
            if not self._can_write(path[0]):
                raise PermissionError(f"Project '{self.folder_display_name(path[:1])}' is read-only for you")
            return path[0]
        if not self._rooms:
            raise RuntimeError("No projects joined")
        writable = self._writable_rooms()
        if not writable:
            raise PermissionError("No project you can edit is joined")
        return self._default_room_id if self._default_room_id in writable else writable[0]

    def default_folder(self) -> list[str]:
        """Every catalogue is in a project: a notebook path without one means where new
        catalogues go (the account's own project, or My catalogues signed out)."""
        try:
            return [self._room_for_new_catalog(None)]
        except (RuntimeError, PermissionError):
            return []

    def create_catalog(self, name: str, path: list[str] | None = None) -> Catalog:
        room_id = self._room_for_new_catalog(path)
        sub_path = list(path[1:]) if path else []
        attributes = {SUBPATH_ATTR: encode_subpath(sub_path)} if sub_path else None
        cocat_cat = self._rooms[room_id].create_catalogue(name=name, author=self._author,
                                                          attributes=attributes)
        return self._wrap_catalogue(room_id, cocat_cat)

    def rename_catalog(self, catalog: Catalog, new_name: str) -> None:
        cocat_cat = self._cocat_catalogue(catalog)
        if cocat_cat is None:
            return self._warn_unavailable("rename", catalog)
        cocat_cat.name = new_name
        catalog.name = new_name
        self.catalog_renamed.emit(catalog)

    def remove_catalog(self, catalog: Catalog) -> None:
        cocat_cat = self._cocat_catalogue(catalog)
        if cocat_cat is None:
            return self._warn_unavailable("remove", catalog)
        cocat_cat.delete()
        self._forget_catalog(catalog)

    def can_move_catalog(self, catalog: Catalog, path: list[str]) -> bool:
        """Within a project, onto Public catalogues (a submission), or a public catalogue into a
        project (a copy): all through move_catalog. Across projects, the tree copies."""
        if catalog.uuid in self._public_views or (path and path[0] == PUBLIC):
            return True
        return bool(path) and bool(catalog.path) and path[0] == catalog.path[0]

    def move_catalog(self, catalog: Catalog, new_path: list[str]) -> None:
        """SciQLop's tree calls it for every drop inside this provider: a public catalogue dropped
        on a project is copied there, a catalogue dropped on Public catalogues is submitted."""
        if catalog.uuid in self._public_views:
            return self._drop_public(catalog, new_path)
        if new_path and new_path[0] == PUBLIC:
            return self.offer_submission(catalog, "/".join(new_path[1:]) or None)
        if list(catalog.path) == list(new_path):
            return
        if not new_path or new_path[0] != catalog.path[0]:
            raise ValueError("Moving catalogs across CoCat projects is not supported")
        cocat_cat = self._cocat_catalogue(catalog)
        if cocat_cat is None:
            raise KeyError(f"Catalog {catalog.name!r} not found in project {new_path[0]!r}")
        if len(new_path) > 1:
            cocat_cat.set_attributes(**{SUBPATH_ATTR: encode_subpath(list(new_path[1:]))})
        elif TSCAT_PATH_ATTR in cocat_cat.attributes:  # an empty folder of ours outranks tscat's
            cocat_cat.set_attributes(**{SUBPATH_ATTR: ""})
        elif SUBPATH_ATTR in cocat_cat.attributes:
            cocat_cat.remove_attributes([SUBPATH_ATTR])
        super().move_catalog(catalog, new_path)

    def _drop_public(self, catalog: Catalog, new_path: list[str]) -> None:
        row = self._public_views[catalog.uuid]
        if new_path and new_path[0] == PUBLIC:
            return
        if new_path and not self._can_write(new_path[0]):
            raise PermissionError(f"{self.folder_display_name(new_path[:1]) or new_path[0]} is read-only: "
                                  f"drop {row['name']} on a project you can edit, or on {PROVIDER_NAME} "
                                  f"for a new project")
        asyncio.ensure_future(self._copy_public(row, new_path[0] if new_path else None))

    def _persist_attribute_spec(self, catalog: Catalog, key: str, spec) -> None:
        from SciQLop.core.knobs import spec_to_dict
        cocat_cat = self._cocat_catalogue(catalog)
        if cocat_cat is not None:
            cocat_cat.set_attributes(**{SCHEMA_ATTR_PREFIX + key: json.dumps(spec_to_dict(spec))})

    def _persist_attribute_spec_removal(self, catalog: Catalog, key: str) -> None:
        cocat_cat = self._cocat_catalogue(catalog)
        if cocat_cat is not None:
            cocat_cat.remove_attributes([SCHEMA_ATTR_PREFIX + key])

    # ---- CatalogProvider: events ----

    def add_event(self, catalog: Catalog, event: CatalogEvent) -> None:
        room, cocat_cat = self._room_of(catalog), self._cocat_catalogue(catalog)
        if cocat_cat is None:
            return self._warn_unavailable("add an event", catalog)
        room_id = catalog.path[0]
        typed, attributes = split_typed_meta(event.meta)
        known = event.uuid in self._wrappers[room_id]
        with room.transaction():
            if not known:
                room.create_event(start=event.start, stop=event.stop, author=self._author,
                                  uuid=event.uuid, attributes=attributes or None, **typed)
            cocat_cat.add_events([event.uuid])
        shown = {**attributes, **typed_meta(typed.get("tags"), typed.get("confidence"))}  # as a re-read gives
        self._add_event(catalog, self._wrapper(room_id, event.uuid, event.start, event.stop, shown))
        self.mark_smart_dirty(room_id)

    def remove_event(self, catalog: Catalog, event: CatalogEvent) -> None:
        room, cocat_cat = self._room_of(catalog), self._cocat_catalogue(catalog)
        if cocat_cat is None:
            return self._warn_unavailable("remove an event", catalog)
        room_id = catalog.path[0]
        self._remove_event(catalog, event)
        with room.transaction():
            cocat_cat.remove_events([event.uuid])
            stored = _stored_event(room, event.uuid)
            if stored is not None and set(stored.catalogues) <= {catalog.uuid}:
                stored.delete()
                self._wrappers[room_id].pop(event.uuid, None)
                self._pending_ranges.pop((room_id, event.uuid), None)
        self.mark_smart_dirty(room_id)

    def set_event_meta(self, catalog: Catalog, event: CatalogEvent, key: str, value: Any) -> None:
        room = self._room_of(catalog)
        if room is None:
            return self._warn_unavailable("edit an event", catalog)
        stored = _stored_event(room, event.uuid)
        if stored is None or event.meta.get(key, _SENTINEL) == value:
            return
        shown = _store_meta(stored, key, value)
        event.set_meta(key, shown) if shown is not _SENTINEL else event.remove_meta(key)
        self.event_meta_changed.emit(catalog, event, key)
        self.mark_smart_dirty(catalog.path[0])

    def remove_event_meta(self, catalog: Catalog, event: CatalogEvent, key: str) -> None:
        room = self._room_of(catalog)
        if room is None:
            return self._warn_unavailable("edit an event", catalog)
        stored = _stored_event(room, event.uuid)
        if stored is None or key not in event.meta:
            return
        _store_meta(stored, key, None) if typed_fields(key, None) else stored.remove_attributes([key])
        event.remove_meta(key)
        self.event_meta_changed.emit(catalog, event, key)
        self.mark_smart_dirty(catalog.path[0])

    def set_events_meta(self, catalog: Catalog, events: list[CatalogEvent], key: str, value: Any) -> None:
        room = self._room_of(catalog)
        if room is None:
            return self._warn_unavailable("edit events", catalog)
        with room.transaction():
            super().set_events_meta(catalog, events, key, value)

    def _on_event_range_changed(self, event: CatalogEvent, catalog: Catalog) -> None:
        super()._on_event_range_changed(event, catalog)
        if self._remote_depth or not catalog.path:
            return
        self._pending_ranges[(self._events_room_id(catalog), event.uuid)] = event
        self._range_timer.start()

    def flush_ranges(self) -> None:
        self._range_timer.stop()
        pending, self._pending_ranges = self._pending_ranges, {}
        for room_id in {room_id for room_id, _ in pending}:
            room = self._rooms.get(room_id)
            if room is None:
                continue
            with room.transaction():
                for (rid, uuid), event in pending.items():
                    if rid == room_id:
                        self._write_range(room, event)
            self.mark_smart_dirty(room_id)

    def _write_range(self, room, event: CatalogEvent) -> None:
        """A stop before the start is refused alone (cocat-rs 0.11 raises, which would undo the whole
        batch): the event goes back to its stored times, and the status bar says why."""
        stored = _stored_event(room, event.uuid)
        if stored is None:
            return
        if event.stop < event.start:
            self.error_occurred.emit(f"Not saved: the event's stop ({event.stop:%Y-%m-%d %H:%M:%S}) is before "
                                     f"its start ({event.start:%Y-%m-%d %H:%M:%S})")
            with self.remote_changes():
                event.apply_remote_range(stored.start, stored.stop)
            return
        stored.range = (event.start, event.stop)
