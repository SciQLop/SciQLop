from typing import List, Optional
from datetime import datetime, timedelta, timezone
from PySide6.QtCore import QObject
from SciQLop.components.sciqlop_logging import getLogger
from cocat import DB
from wire_websocket import AsyncWebSocketClient
from wire_file import AsyncFileClient
from SciQLop.components.storage import user_data_dir
from SciQLop.core.sciqlop_application import sciqlop_event_loop, sciqlop_app
import asyncio
import httpx
import traceback
from urllib.parse import urlparse
import jwt

log = getLogger(__name__)


def _ensure_logged_in(self):
    if not self.logged_in:
        if not self.login():
            log.error("Cannot perform action, not logged in")
            return False
    return True


def ensure_login(func):
    if asyncio.iscoroutinefunction(func):
        async def wrapper(self, *args, **kwargs):
            if not _ensure_logged_in(self):
                return None
            return await func(self, *args, **kwargs)

        return wrapper
    else:
        def wrapper(self, *args, **kwargs):
            if not _ensure_logged_in(self):
                return None
            return func(self, *args, **kwargs)

        return wrapper


def _ensure_room_joined(self):
    if self._client is None:
        return False
    return True


def ensure_room_joined(func):
    if asyncio.iscoroutinefunction(func):
        async def wrapper(self, *args, **kwargs):
            if not _ensure_room_joined(self):
                log.error("Cannot perform action, you must join a room first")
                return None
            return await func(self, *args, **kwargs)

        return wrapper
    else:
        def wrapper(self, *args, **kwargs):
            if not _ensure_room_joined(self):
                log.error("Cannot perform action, you must join a room first")
                return None
            return func(self, *args, **kwargs)

        return wrapper


class Client(QObject):

    def __init__(self, url: str = "https://sciqlop.lpp.polytechnique.fr/cocat/", room_id: Optional[str] = None,
                 parent: Optional[QObject] = None):
        super().__init__(parent)
        self._url = url[:-1] if url.endswith("/") else url
        p = urlparse(self._url)
        self._host = f"{p.scheme}://{p.hostname}"
        self._port = p.port or (443 if p.scheme == "https" else 80)
        self._prefix = p.path[1:] + "/" if p.path else ""
        self._db = DB()
        self._room_id = room_id
        self._client: Optional[AsyncWebSocketClient] = None
        self._cookies = httpx.Cookies()
        self._task: Optional[asyncio.Task] = None
        self._close_event = asyncio.Event()
        self._connecting_event = asyncio.Event()
        self._connected = False

    @property
    def logged_in(self) -> bool:
        token = self._cookies.get("fastapiusersauth")
        if token is None:
            return False
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            exp = payload.get("exp")
            if exp is None:
                return False
            exp_datetime = datetime.fromtimestamp(exp, tz=timezone.utc)
            if exp_datetime < datetime.now(tz=timezone.utc) + timedelta(minutes=5):
                return False
            return True
        except jwt.PyJWTError:
            return False

    def login(self):
        if self.logged_in:
            return True
        from .settings import CollaborativeCatalogsSettings
        settings = CollaborativeCatalogsSettings()
        username, password = settings.username, settings.password
        if not username or not password:
            log.info("No credentials configured for %s", self._url)
            return False
        if self._room_id is None:
            self._room_id = username.split("@")[0]
        data = {"username": username, "password": password}
        try:
            response = httpx.post(f"{self._url}/auth/jwt/login", data=data)
        except Exception as e:
            log.error("Cannot reach CoCat server at %s: %s", self._url, e)
            return False
        cookie = response.cookies.get("fastapiusersauth")
        if cookie:
            self._cookies.set("fastapiusersauth", cookie)
            log.info("Successfully logged in to %s", self._url)
            return True
        log.info("Login rejected by %s", self._url)
        return False

    def logout(self):
        self._cookies.delete("fastapiusersauth")

    @property
    @ensure_login
    @ensure_room_joined
    def db(self):
        return self._db

    @property
    def room_id(self):
        return self._room_id

    @ensure_login
    def list_rooms(self) -> List[str]:
        response = httpx.get(f"{self._url}/rooms", cookies=self._cookies)
        if response.status_code == 200:
            data = response.json()
            return data.get("rooms", [])
        return []

    @ensure_login
    async def join_room(self, room_id: Optional[str] = None) -> bool:
        if room_id:
            self._room_id = room_id
        if self._connected:
            await self.leave_room()
        self._connecting_event.clear()
        self._task = asyncio.create_task(self._join())
        await self._connecting_event.wait()
        if not self._connected:
            log.error("Failed to join room")
            return False
        return True

    async def leave_room(self):
        if self._task:
            self._close_event.set()
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
                pass
            self._task = None
            self._close_event = asyncio.Event()

    @ensure_login
    async def _join(self):
        local_file = user_data_dir("collaborative_catalogs") / self._room_id
        try:
            async with (AsyncWebSocketClient(f"/{self._prefix}room/{self._room_id}", doc=self._db.doc,
                                             host=self._host, port=self._port,
                                             cookies=self._cookies) as client,
                        AsyncFileClient("file",
                                        doc=self._db.doc,
                                        path=local_file) as file):
                self._client = client
                self._file = file
                log.info('Connected to websocket')
                self._connected = True
                self._connecting_event.set()
                await self._close_event.wait()
        except Exception as e:
            log.error(e)
            log.error(traceback.format_exc())
            self._connecting_event.set()
        finally:
            self._client = None
            self._file = None
            self._task = None
            self._connected = False
            self._connecting_event.clear()
